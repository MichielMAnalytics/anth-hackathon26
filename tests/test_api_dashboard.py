import pytest_asyncio
from sqlalchemy import delete, select

from server.db.alerts import Alert
from server.db.identity import NGO, Account
from server.db.messages import InboundMessage


@pytest_asyncio.fixture(autouse=True)
async def _isolate_dashboard(test_session_maker):
    """Purge dashboard-test rows before AND after each test so committed data
    doesn't leak between runs. Order: messages → accounts → alerts → ngo to
    respect FK cascades."""
    async def _purge():
        async with test_session_maker() as s:
            ngo_ids = [
                row[0]
                for row in (
                    await s.execute(
                        select(NGO.ngo_id).where(NGO.name == "Warchild-dash-test")
                    )
                ).all()
            ]
            if ngo_ids:
                await s.execute(delete(InboundMessage).where(InboundMessage.ngo_id.in_(ngo_ids)))
                await s.execute(delete(Alert).where(Alert.ngo_id.in_(ngo_ids)))
                await s.execute(delete(Account).where(Account.ngo_id.in_(ngo_ids)))
                await s.execute(delete(NGO).where(NGO.ngo_id.in_(ngo_ids)))
            # Also defensively delete the specific account phone if any prior
            # leak happened under a different ngo_id.
            await s.execute(delete(Account).where(Account.phone == "+9647005556677"))
            await s.commit()

    await _purge()
    yield
    await _purge()


async def test_dashboard_shape_no_data(client):
    resp = await client.get("/api/dashboard", headers={"X-Operator-Id": "op-senior"})
    assert resp.status_code == 200
    body = resp.json()
    assert "windowMinutes" in body
    assert isinstance(body["regions"], list)
    assert len(body["regions"]) == 6
    for reg in body["regions"]:
        assert len(reg["sparkline"]) == 12
        assert reg["themes"] == []


async def test_dashboard_counts_messages_per_region(client, db):
    ngo = NGO(name="Warchild-dash-test")
    db.add(ngo)
    await db.flush()
    alert = Alert(
        ngo_id=ngo.ngo_id, person_name="DashPerson", status="active",
        urgency_tier="high", region_geohash_prefix="sv8d",
    )
    db.add(alert)
    await db.flush()
    acc = Account(phone="+9647005556677", ngo_id=ngo.ngo_id)
    db.add(acc)
    await db.flush()
    for i in range(3):
        db.add(InboundMessage(
            ngo_id=ngo.ngo_id, channel="sms", sender_phone="+9647005556677",
            in_reply_to_alert_id=alert.alert_id, body=f"distress {i}",
            media_urls=[], raw={},
        ))
    await db.commit()

    resp = await client.get("/api/dashboard", headers={"X-Operator-Id": "op-senior"})
    body = resp.json()
    baghdad = next(r for r in body["regions"] if r["region"] == "IRQ_BAGHDAD")
    assert baghdad["messageCount"] >= 3
    assert baghdad["openCases"] >= 1


async def test_dashboard_requires_auth(client):
    resp = await client.get("/api/dashboard")
    assert resp.status_code == 401
