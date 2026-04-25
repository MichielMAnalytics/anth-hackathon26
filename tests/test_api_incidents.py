from datetime import UTC, datetime, timedelta

import pytest_asyncio
from sqlalchemy import delete, select

from server.db.alerts import Alert
from server.db.identity import NGO, Account
from server.db.messages import InboundMessage

_TEST_NGO_NAMES = ["Warchild-inc-test", "Warchild-msg-test", "Warchild-msg-auth"]
_TEST_PHONES = ["+9647001112233", "+9647009998877"]


@pytest_asyncio.fixture(autouse=True)
async def _isolate_alerts(test_session_maker):
    """Ensure no alerts/accounts/NGOs leak between tests."""
    async with test_session_maker() as s:
        # 1. inbound messages referencing our test alerts
        await s.execute(
            delete(InboundMessage).where(
                InboundMessage.sender_phone.in_(_TEST_PHONES)
            )
        )
        # 2. alerts belonging to test NGOs
        ngo_ids = (
            await s.execute(
                select(NGO.ngo_id).where(NGO.name.in_(_TEST_NGO_NAMES))
            )
        ).scalars().all()
        if ngo_ids:
            await s.execute(
                delete(Alert).where(Alert.ngo_id.in_(ngo_ids))
            )
            # 3. accounts referencing test NGOs
            await s.execute(
                delete(Account).where(Account.ngo_id.in_(ngo_ids))
            )
            # 4. finally the NGOs themselves
            await s.execute(
                delete(NGO).where(NGO.ngo_id.in_(ngo_ids))
            )
        await s.commit()
    yield


async def test_incidents_empty(client, test_session_maker):
    # Purge ALL active alerts so we get a clean slate for the empty-list assertion.
    async with test_session_maker() as s:
        await s.execute(delete(Alert).where(Alert.status == "active"))
        await s.commit()

    resp = await client.get("/api/incidents", headers={"X-Operator-Id": "op-senior"})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_incidents_returns_mapped_alert(client, db):
    ngo = NGO(name="Warchild-inc-test")
    db.add(ngo)
    await db.flush()
    alert = Alert(
        ngo_id=ngo.ngo_id,
        person_name="Amira Hassan",
        status="active",
        category="missing_person",
        urgency_tier="high",
        urgency_score=0.9,
        region_geohash_prefix="sv8d",
        last_seen_geohash="sv8du",
        description="8-year-old girl, last seen near market",
        expires_at=datetime.now(UTC) + timedelta(days=2),
    )
    db.add(alert)
    await db.flush()
    acc = Account(phone="+9647001112233", ngo_id=ngo.ngo_id)
    db.add(acc)
    await db.flush()
    db.add(InboundMessage(
        ngo_id=ngo.ngo_id,
        channel="sms",
        sender_phone="+9647001112233",
        in_reply_to_alert_id=alert.alert_id,
        body="I saw her near the bridge",
        media_urls=[],
        raw={},
    ))
    await db.commit()

    resp = await client.get("/api/incidents", headers={"X-Operator-Id": "op-senior"})
    assert resp.status_code == 200
    items = resp.json()
    inc = next(i for i in items if i["id"] == alert.alert_id)
    assert inc["category"] == "missing_person"
    assert inc["title"] == "Amira Hassan"
    assert inc["severity"] == "high"
    assert inc["region"] == "IRQ_BAGHDAD"
    assert inc["messageCount"] == 1
    assert inc["lastActivity"] is not None


async def test_incidents_requires_auth(client):
    resp = await client.get("/api/incidents")
    assert resp.status_code == 401


async def test_incident_messages_returns_inbound(client, db):
    ngo = NGO(name="Warchild-msg-test")
    db.add(ngo)
    await db.flush()
    alert = Alert(ngo_id=ngo.ngo_id, person_name="Khalid", status="active", region_geohash_prefix="sv8d")
    db.add(alert)
    await db.flush()
    acc = Account(phone="+9647009998877", ngo_id=ngo.ngo_id)
    db.add(acc)
    await db.flush()
    db.add(InboundMessage(
        ngo_id=ngo.ngo_id, channel="sms", sender_phone="+9647009998877",
        in_reply_to_alert_id=alert.alert_id, body="Spotted near checkpoint",
        media_urls=[], raw={},
    ))
    db.add(InboundMessage(
        ngo_id=ngo.ngo_id, channel="app", sender_phone="+9647009998877",
        in_reply_to_alert_id=alert.alert_id, body="Heading north now",
        media_urls=[], raw={},
    ))
    await db.commit()

    resp = await client.get(
        f"/api/incidents/{alert.alert_id}/messages",
        headers={"X-Operator-Id": "op-senior"},
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    assert all(m["outbound"] is False for m in items)
    assert items[0]["ts"] <= items[1]["ts"]
    assert items[0]["via"] in ("sms", "app", "fallback", None)


async def test_incident_messages_404_for_unknown(client):
    resp = await client.get(
        "/api/incidents/00000000000000000000000000/messages",
        headers={"X-Operator-Id": "op-senior"},
    )
    assert resp.status_code == 404


async def test_incident_messages_requires_auth(client, db):
    ngo = NGO(name="Warchild-msg-auth")
    db.add(ngo)
    await db.flush()
    alert = Alert(ngo_id=ngo.ngo_id, person_name="X", status="active")
    db.add(alert)
    await db.commit()

    resp = await client.get(f"/api/incidents/{alert.alert_id}/messages")
    assert resp.status_code == 401
