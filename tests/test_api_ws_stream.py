import asyncio
import random
import threading
import time

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.testclient import TestClient

from server.config import get_settings
from server.db.alerts import Alert
from server.db.identity import NGO, Account
from server.db.messages import InboundMessage


@pytest.fixture
def sync_seed():
    """Seed an InboundMessage row synchronously for TestClient WS tests.

    Uses fresh engines in isolated loops — avoids sharing asyncpg connections
    across event loops (the session-scoped test_engine cannot be reused here).
    """
    settings = get_settings()
    db_url = settings.test_database_url
    # Use a unique phone to avoid conflicts across test runs
    unique_phone = f"+9725{random.randint(10000000, 99999999)}"

    async def _seed():
        engine = create_async_engine(db_url, future=True)
        sm = async_sessionmaker(engine, expire_on_commit=False)
        async with sm() as s:
            ngo = NGO(name="WSNGO")
            s.add(ngo)
            await s.flush()
            acc = Account(phone=unique_phone, ngo_id=ngo.ngo_id)
            alert = Alert(ngo_id=ngo.ngo_id, person_name="Dana", status="active")
            s.add_all([acc, alert])
            await s.flush()
            msg = InboundMessage(
                ngo_id=ngo.ngo_id, channel="app", sender_phone=unique_phone,
                in_reply_to_alert_id=alert.alert_id, body="saw her near the park",
                media_urls=[], raw={}, status="new",
            )
            s.add(msg)
            await s.flush()
            await s.commit()
            result = {"alert_id": alert.alert_id, "msg_id": msg.msg_id, "ngo_id": ngo.ngo_id}
        await engine.dispose()
        return result

    loop = asyncio.new_event_loop()
    out = loop.run_until_complete(_seed())
    loop.close()
    yield out
    # teardown: purge committed test data
    async def _cleanup():
        engine = create_async_engine(db_url, future=True)
        sm = async_sessionmaker(engine, expire_on_commit=False)
        async with sm() as s:
            from sqlalchemy import delete
            await s.execute(delete(InboundMessage).where(InboundMessage.ngo_id == out["ngo_id"]))
            await s.execute(delete(Alert).where(Alert.ngo_id == out["ngo_id"]))
            await s.execute(delete(Account).where(Account.ngo_id == out["ngo_id"]))
            await s.execute(delete(NGO).where(NGO.ngo_id == out["ngo_id"]))
            await s.commit()
        await engine.dispose()
    loop = asyncio.new_event_loop()
    loop.run_until_complete(_cleanup())
    loop.close()


def test_ws_stream_receives_message(sync_seed, monkeypatch):
    import concurrent.futures

    settings = get_settings()
    test_db_url = settings.test_database_url

    # Create a fresh engine factory so each call within TestClient's event loop
    # gets an engine created in *that* loop — avoids "Future attached to different loop".
    def make_engine():
        return create_async_engine(test_db_url, future=True)

    def make_session_maker():
        return async_sessionmaker(make_engine(), expire_on_commit=False)

    # Patch both the module-level attribute AND each importing module's binding.
    # ws.py and main.py do `from server.db.engine import get_engine`, so the
    # monkeypatched module attribute alone doesn't reach those local names.
    monkeypatch.setattr("server.db.engine.get_engine", make_engine)
    monkeypatch.setattr("server.db.engine.get_session_maker", make_session_maker)
    monkeypatch.setattr("server.api.ws.get_engine", make_engine)
    monkeypatch.setattr("server.api.ws.get_session_maker", make_session_maker)
    monkeypatch.setattr("server.main.get_engine", make_engine)
    monkeypatch.setattr("server.main.get_session_maker", make_session_maker)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    from server.eventbus.postgres import PostgresEventBus
    from server.main import app

    received: list[dict] = []

    def publish_after_connect():
        time.sleep(1.0)

        async def _pub():
            engine = create_async_engine(test_db_url, future=True)
            bus = PostgresEventBus(engine)
            await bus.publish("new_inbound", sync_seed["msg_id"])
            await engine.dispose()

        loop = asyncio.new_event_loop()
        loop.run_until_complete(_pub())
        loop.close()

    t = threading.Thread(target=publish_after_connect, daemon=True)

    with TestClient(app) as client:
        t.start()
        with client.websocket_connect("/ws/stream") as ws:
            # receive_json blocks indefinitely; use a daemon thread with timeout.
            # Do NOT use ThreadPoolExecutor as a context manager — shutdown(wait=True)
            # would hang if receive_json never returns (timeout case).
            pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            future = pool.submit(ws.receive_json)
            try:
                data = future.result(timeout=6.0)
                received.append(data)
            except (concurrent.futures.TimeoutError, Exception):
                pass
            finally:
                pool.shutdown(wait=False, cancel_futures=True)

    assert len(received) >= 1
    evt = received[0]
    assert evt["type"] == "message"
    assert evt["message"]["body"] == "saw her near the park"
