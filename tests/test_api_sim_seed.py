import pytest_asyncio
from sqlalchemy import delete, select

from server.db.alerts import Alert, AlertDelivery
from server.db.identity import NGO, Account
from server.db.messages import InboundMessage

_SEED_NGO_NAME = "Warchild"


async def _purge_warchild(test_session_maker) -> None:
    async with test_session_maker() as s:
        ngo_ids = (
            await s.execute(select(NGO.ngo_id).where(NGO.name == _SEED_NGO_NAME))
        ).scalars().all()
        if ngo_ids:
            alert_ids = (
                await s.execute(select(Alert.alert_id).where(Alert.ngo_id.in_(ngo_ids)))
            ).scalars().all()
            if alert_ids:
                await s.execute(
                    delete(InboundMessage).where(
                        InboundMessage.in_reply_to_alert_id.in_(alert_ids)
                    )
                )
                await s.execute(
                    delete(AlertDelivery).where(AlertDelivery.alert_id.in_(alert_ids))
                )
            await s.execute(delete(Alert).where(Alert.ngo_id.in_(ngo_ids)))
            await s.execute(delete(Account).where(Account.ngo_id.in_(ngo_ids)))
            await s.execute(delete(NGO).where(NGO.ngo_id.in_(ngo_ids)))
        await s.commit()


@pytest_asyncio.fixture(autouse=True)
async def _isolate_seed(test_session_maker):
    """Purge the Warchild seed NGO and all its dependents before AND after each test."""
    await _purge_warchild(test_session_maker)
    yield
    await _purge_warchild(test_session_maker)


async def test_seed_creates_expected_rows(client):
    resp = await client.post("/api/sim/seed")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "ngo_id" in body
    assert "alert_id" in body
    assert body["seeded"]["accounts"] == 6
    assert body["seeded"]["alert_deliveries"] == 6
    assert body["seeded"]["inbound_messages"] >= 3


async def test_seed_is_idempotent(client, db):
    r1 = await client.post("/api/sim/seed")
    r2 = await client.post("/api/sim/seed")
    assert r1.json()["ngo_id"] == r2.json()["ngo_id"]
    assert r1.json()["alert_id"] == r2.json()["alert_id"]
    rows = (await db.execute(select(NGO).where(NGO.name == "Warchild"))).scalars().all()
    assert len(rows) == 1


async def test_seed_inbound_messages_tied_to_alert(client, db):
    body = (await client.post("/api/sim/seed")).json()
    msgs = (
        await db.execute(
            select(InboundMessage).where(InboundMessage.in_reply_to_alert_id == body["alert_id"])
        )
    ).scalars().all()
    assert len(msgs) >= 3
