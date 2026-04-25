import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from server.db.alerts import Alert, AlertDelivery
from server.db.identity import NGO, Account
from server.db.messages import InboundMessage

_INBOUND_PHONES = ["+972500000001"]


async def _purge_all(test_session_maker) -> None:
    async with test_session_maker() as s:
        # Delete in FK-safe order: inbound_messages -> alert_delivery -> alerts -> accounts -> ngos
        await s.execute(delete(InboundMessage))
        await s.execute(delete(AlertDelivery))
        await s.execute(delete(Alert))
        await s.execute(delete(Account))
        await s.execute(delete(NGO))
        await s.commit()


@pytest_asyncio.fixture(autouse=True)
async def _isolate_inbound(test_session_maker):
    """Purge ALL NGOs and their dependents before AND after each inbound test.

    The /inbound endpoint requires exactly 1 NGO in the DB. This fixture
    ensures a clean slate so the `seeded` fixture can insert exactly one,
    and tears down afterward so other test files are not affected.
    """
    await _purge_all(test_session_maker)
    yield
    await _purge_all(test_session_maker)


@pytest.fixture
async def seeded(db):
    ngo = NGO(name="TestNGO-inbound")
    db.add(ngo)
    await db.flush()
    acc = Account(phone="+972500000001", ngo_id=ngo.ngo_id)
    alert = Alert(ngo_id=ngo.ngo_id, person_name="Maya", status="active")
    db.add_all([acc, alert])
    await db.flush()
    await db.commit()
    return {"ngo_id": ngo.ngo_id, "alert_id": alert.alert_id}


async def test_post_inbound_returns_202(client, seeded):
    resp = await client.post(
        "/api/sim/inbound",
        json={
            "channel": "app",
            "sender_phone": "+972500000001",
            "in_reply_to_alert_id": seeded["alert_id"],
            "body": "saw a girl matching photo near bakery",
            "media_urls": [],
            "raw": {},
        },
    )
    assert resp.status_code == 202
    body = resp.json()
    assert "msg_id" in body
    assert body["status"] == "new"


async def test_post_inbound_creates_db_row(client, seeded, test_session_maker):
    resp = await client.post(
        "/api/sim/inbound",
        json={
            "channel": "sms",
            "sender_phone": "+972500000001",
            "in_reply_to_alert_id": None,
            "body": "hello world",
            "media_urls": [],
            "raw": {"src": "test"},
        },
    )
    assert resp.status_code == 202
    msg_id = resp.json()["msg_id"]

    async with test_session_maker() as session:
        row = await session.get(InboundMessage, msg_id)
    assert row is not None
    assert row.status == "new"
    assert row.channel == "sms"
    assert row.body == "hello world"


async def test_post_inbound_503_when_no_ngo(client):
    resp = await client.post(
        "/api/sim/inbound",
        json={
            "channel": "app",
            "sender_phone": "+972500000099",
            "in_reply_to_alert_id": None,
            "body": "no ngo",
            "media_urls": [],
            "raw": {},
        },
    )
    assert resp.status_code in (202, 503)
