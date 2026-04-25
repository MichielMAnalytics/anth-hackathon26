import asyncio

import pytest
from sqlalchemy import delete, select

from server.db.alerts import Alert
from server.db.identity import NGO, Account
from server.db.messages import Bucket, InboundMessage, TriagedMessage


@pytest.fixture(autouse=True)
def stub_llm(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")


_TRIAGE_PHONE = "+972500000042"
_TRIAGE_NGO_NAME = "TriageNGO"


async def _cleanup_triage_fixtures(session_maker) -> None:
    """Delete any leftover rows from prior triage-worker test runs."""
    async with session_maker() as s:
        # Resolve ngo_id for our test NGO (may not exist).
        from sqlalchemy import select as sa_select
        ngo_ids = (
            await s.execute(sa_select(NGO.ngo_id).where(NGO.name == _TRIAGE_NGO_NAME))
        ).scalars().all()
        msg_ids = (
            await s.execute(
                sa_select(InboundMessage.msg_id).where(
                    InboundMessage.sender_phone == _TRIAGE_PHONE
                )
            )
        ).scalars().all()
        if msg_ids:
            await s.execute(delete(TriagedMessage).where(TriagedMessage.msg_id.in_(msg_ids)))
        if ngo_ids:
            alert_ids = (
                await s.execute(sa_select(Alert.alert_id).where(Alert.ngo_id.in_(ngo_ids)))
            ).scalars().all()
            if alert_ids:
                await s.execute(delete(Bucket).where(Bucket.alert_id.in_(alert_ids)))
                await s.execute(
                    delete(InboundMessage).where(
                        InboundMessage.in_reply_to_alert_id.in_(alert_ids)
                    )
                )
                await s.execute(delete(Alert).where(Alert.alert_id.in_(alert_ids)))
        await s.execute(delete(Account).where(Account.phone == _TRIAGE_PHONE))
        if ngo_ids:
            await s.execute(delete(NGO).where(NGO.ngo_id.in_(ngo_ids)))
        await s.commit()


@pytest.fixture
async def seeded_inbound(test_session_maker):
    # Pre-clean any leftovers from previous runs.
    await _cleanup_triage_fixtures(test_session_maker)

    async with test_session_maker() as s:
        ngo = NGO(name=_TRIAGE_NGO_NAME)
        s.add(ngo)
        await s.flush()
        acc = Account(phone=_TRIAGE_PHONE, ngo_id=ngo.ngo_id)
        alert = Alert(
            ngo_id=ngo.ngo_id, person_name="Yael",
            description="Young girl, red jacket, last seen near central market",
            status="active",
        )
        s.add_all([acc, alert])
        await s.flush()
        msg = InboundMessage(
            ngo_id=ngo.ngo_id, channel="app", sender_phone=_TRIAGE_PHONE,
            in_reply_to_alert_id=alert.alert_id,
            body="saw a girl in red walking south near bakery",
            media_urls=[], raw={}, status="new",
        )
        s.add(msg)
        await s.flush()
        await s.commit()
        seed = {"ngo_id": ngo.ngo_id, "alert_id": alert.alert_id, "msg_id": msg.msg_id}

    yield seed

    # Post-test cleanup: remove worker-committed rows so they don't pollute other tests.
    await _cleanup_triage_fixtures(test_session_maker)


async def test_stub_classify_short_body():
    from server.llm.triage_client import classify
    r = await classify("hi", None)
    assert r["classification"] == "noise"


async def test_stub_classify_long_body():
    from server.llm.triage_client import classify
    r = await classify("saw a young girl near the bakery going south", None)
    assert r["classification"] == "sighting"
    assert len(r["dedup_hash"]) > 0


async def test_hash_to_vec_length():
    from server.llm.triage_client import hash_to_vec
    v = hash_to_vec("test body")
    assert len(v) == 512
    assert all(-1.0 <= x <= 1.0 for x in v)


async def test_triage_worker_consumes_event(seeded_inbound, test_engine, test_session_maker):
    from server.eventbus.postgres import PostgresEventBus
    from server.workers.triage import triage_worker_loop

    bus = PostgresEventBus(test_engine)
    task = asyncio.create_task(triage_worker_loop(bus, test_session_maker))
    await asyncio.sleep(0.4)

    await bus.publish("new_inbound", seeded_inbound["msg_id"])
    await asyncio.sleep(1.5)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    async with test_session_maker() as session:
        inbound = await session.get(InboundMessage, seeded_inbound["msg_id"])
        assert inbound.status == "triaged"

        triage_rows = (
            await session.execute(
                select(TriagedMessage).where(TriagedMessage.msg_id == seeded_inbound["msg_id"])
            )
        ).scalars().all()
        assert len(triage_rows) == 1
        tm = triage_rows[0]
        assert tm.classification in ("sighting", "question", "ack", "noise", "bad_actor")
        assert len(tm.body_embedding) == 512

        bucket_rows = (
            await session.execute(select(Bucket).where(Bucket.bucket_key == tm.bucket_key))
        ).scalars().all()
        assert len(bucket_rows) == 1
