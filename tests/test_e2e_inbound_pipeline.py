import asyncio
import concurrent.futures
import threading
import time

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.testclient import TestClient

from server.config import get_settings
from server.db.alerts import Alert
from server.db.identity import NGO, Account
from server.db.messages import Bucket, InboundMessage, TriagedMessage


@pytest.fixture(autouse=True)
def stub_llm_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")


@pytest.fixture
def sync_seed():
    """Seed exactly one NGO + Account + Alert synchronously for the e2e test.

    Uses a fresh event loop + engine to avoid sharing asyncpg connections
    with the session-scoped test_engine (different event loop).

    Also purges ALL pre-existing data so the /api/sim/inbound endpoint
    (which enforces exactly-1-NGO) does not see stale rows from other tests.
    """
    settings = get_settings()
    db_url = settings.test_database_url

    async def _purge_and_seed():
        engine = create_async_engine(db_url, future=True)
        sm = async_sessionmaker(engine, expire_on_commit=False)
        async with sm() as s:
            # Purge in FK-safe order so /inbound sees exactly 1 NGO.
            await s.execute(delete(TriagedMessage))
            await s.execute(delete(Bucket))
            await s.execute(delete(InboundMessage))
            await s.execute(delete(Alert))
            await s.execute(delete(Account))
            await s.execute(delete(NGO))
            await s.commit()

            ngo = NGO(name="E2ENGO")
            s.add(ngo)
            await s.flush()
            acc = Account(phone="+972500000099", ngo_id=ngo.ngo_id)
            alert = Alert(
                ngo_id=ngo.ngo_id,
                person_name="Shira",
                description="Young girl, brown hair, last seen near central market",
                status="active",
            )
            s.add_all([acc, alert])
            await s.flush()
            await s.commit()
            result = {
                "alert_id": alert.alert_id,
                "phone": "+972500000099",
                "ngo_id": ngo.ngo_id,
            }
        await engine.dispose()
        return result

    loop = asyncio.new_event_loop()
    out = loop.run_until_complete(_purge_and_seed())
    loop.close()
    yield out

    # Teardown: purge all data created by this test.
    async def _cleanup():
        engine = create_async_engine(db_url, future=True)
        sm = async_sessionmaker(engine, expire_on_commit=False)
        async with sm() as s:
            inbound_ids = [
                row[0]
                for row in (
                    await s.execute(
                        select(InboundMessage.msg_id).where(
                            InboundMessage.ngo_id == out["ngo_id"]
                        )
                    )
                ).all()
            ]
            if inbound_ids:
                await s.execute(
                    delete(TriagedMessage).where(TriagedMessage.msg_id.in_(inbound_ids))
                )
            await s.execute(delete(Bucket).where(Bucket.ngo_id == out["ngo_id"]))
            await s.execute(
                delete(InboundMessage).where(InboundMessage.ngo_id == out["ngo_id"])
            )
            await s.execute(delete(Alert).where(Alert.ngo_id == out["ngo_id"]))
            await s.execute(delete(Account).where(Account.ngo_id == out["ngo_id"]))
            await s.execute(delete(NGO).where(NGO.ngo_id == out["ngo_id"]))
            await s.commit()
        await engine.dispose()

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_cleanup())
    loop.close()


def test_full_inbound_pipeline(sync_seed, monkeypatch):
    """POST /api/sim/inbound -> triage worker -> bucket -> WS event."""
    settings = get_settings()
    test_db_url = settings.test_database_url

    # Create fresh engine factories so every call within the TestClient's
    # event loop gets an engine created in *that* loop — avoids
    # "Future attached to different loop" errors with asyncpg.
    def make_engine():
        return create_async_engine(test_db_url, future=True)

    def make_session_maker():
        return async_sessionmaker(make_engine(), expire_on_commit=False)

    # Patch every binding site that imports get_engine / get_session_maker.
    # Modules that do `from server.db.engine import get_engine` bind the name
    # locally at import time, so each local binding must be patched individually.
    #
    # server.db.session imports get_session_maker and exposes get_db — all API
    # routes using Depends(get_db) go through this path.  We must patch the
    # local name in server.db.session too, otherwise get_db falls back to the
    # lru_cache's previously-created session-loop engine.
    monkeypatch.setattr("server.db.engine.get_engine", make_engine)
    monkeypatch.setattr("server.db.engine.get_session_maker", make_session_maker)
    monkeypatch.setattr("server.db.session.get_session_maker", make_session_maker)
    monkeypatch.setattr("server.api.ws.get_engine", make_engine)
    monkeypatch.setattr("server.api.ws.get_session_maker", make_session_maker)
    monkeypatch.setattr("server.api.sim.get_engine", make_engine)
    monkeypatch.setattr("server.main.get_engine", make_engine)
    monkeypatch.setattr("server.main.get_session_maker", make_session_maker)

    from server.main import app

    received: list[dict] = []
    body_text = "saw a girl in red walking south near the old market"

    def post_inbound_after_delay(client: TestClient) -> None:
        """Run in a daemon thread: wait for WS to connect, then POST."""
        time.sleep(1.0)
        resp = client.post(
            "/api/sim/inbound",
            json={
                "channel": "app",
                "sender_phone": sync_seed["phone"],
                "in_reply_to_alert_id": sync_seed["alert_id"],
                "body": body_text,
                "media_urls": [],
                "raw": {},
            },
        )
        assert resp.status_code == 202, f"POST failed: {resp.status_code} {resp.text}"

    with TestClient(app) as client:
        t = threading.Thread(target=post_inbound_after_delay, args=(client,), daemon=True)
        t.start()

        with client.websocket_connect("/ws/stream") as ws:
            # Use ThreadPoolExecutor so we can apply a timeout without
            # blocking forever if no message arrives (matches WS test pattern).
            pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            future = pool.submit(ws.receive_json)
            try:
                data = future.result(timeout=12.0)
                received.append(data)
            except (concurrent.futures.TimeoutError, Exception) as exc:
                print(f"WS receive failed: {exc!r}")
            finally:
                pool.shutdown(wait=False, cancel_futures=True)

        t.join(timeout=5.0)
        # Give the triage worker time to finish processing BEFORE we exit
        # the TestClient context (which cancels the worker task).
        # The WS event fires on new_inbound (before triage), so triage may
        # still be running when we receive the WS notification.
        time.sleep(3.0)

    assert len(received) >= 1, "Expected at least one WS event — none received"
    evt = received[0]
    assert evt["type"] == "message", f"Unexpected event type: {evt.get('type')}"
    assert evt["message"]["body"] == body_text, (
        f"Body mismatch: {evt['message']['body']!r} != {body_text!r}"
    )

    # DB state verification — poll until triage worker completes.
    engine = create_async_engine(test_db_url, future=True)
    sm = async_sessionmaker(engine, expire_on_commit=False)

    async def _check_db():
        # Poll in separate sessions so SQLAlchemy's identity map doesn't hide
        # updates committed by the triage worker in the TestClient's loop.
        inbound_id = None
        for _ in range(20):
            async with sm() as s:
                rows = (
                    await s.execute(
                        select(InboundMessage).where(
                            InboundMessage.sender_phone == sync_seed["phone"],
                            InboundMessage.body == body_text,
                        )
                    )
                ).scalars().all()
            if rows and rows[-1].status == "triaged":
                inbound_id = rows[-1].msg_id
                break
            await asyncio.sleep(0.3)

        assert inbound_id is not None, (
            "InboundMessage never reached status='triaged' within timeout"
        )

        async with sm() as s:
            triaged_rows = (
                await s.execute(
                    select(TriagedMessage).where(TriagedMessage.msg_id == inbound_id)
                )
            ).scalars().all()
            assert len(triaged_rows) == 1, (
                f"Expected 1 TriagedMessage, got {len(triaged_rows)}"
            )
            assert len(triaged_rows[0].body_embedding) == 512, (
                f"Expected embedding length 512, got {len(triaged_rows[0].body_embedding)}"
            )

            bucket_rows = (
                await s.execute(
                    select(Bucket).where(Bucket.bucket_key == triaged_rows[0].bucket_key)
                )
            ).scalars().all()
            assert len(bucket_rows) == 1, (
                f"Expected 1 Bucket row, got {len(bucket_rows)}"
            )

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_check_db())
    loop.close()

    loop2 = asyncio.new_event_loop()
    loop2.run_until_complete(engine.dispose())
    loop2.close()
