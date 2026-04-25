from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from server.db.alerts import Alert, AlertDelivery
from server.db.identity import NGO, Account


async def test_alert_inserted_with_category_and_urgency(db):
    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()

    alert = Alert(
        ngo_id=ngo.ngo_id,
        person_name="Maya",
        last_seen_geohash="sv8d6",
        description="missing 8yo",
        region_geohash_prefix="sv8d",
        status="active",
        category="missing_child",
        urgency_tier="high",
        urgency_score=0.9,
        expires_at=datetime.now(UTC) + timedelta(days=2),
    )
    db.add(alert)
    await db.flush()

    fetched = (await db.execute(select(Alert).where(Alert.alert_id == alert.alert_id))).scalar_one()
    assert fetched.category == "missing_child"
    assert fetched.urgency_score == 0.9


async def test_alert_delivery_links_alert_and_recipient(db):
    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()
    acc = Account(phone="+972500000001", ngo_id=ngo.ngo_id)
    alert = Alert(ngo_id=ngo.ngo_id, person_name="X", status="active")
    db.add_all([acc, alert])
    await db.flush()

    delivery = AlertDelivery(
        ngo_id=ngo.ngo_id,
        alert_id=alert.alert_id,
        recipient_phone=acc.phone,
    )
    db.add(delivery)
    await db.flush()

    rows = (
        await db.execute(select(AlertDelivery).where(AlertDelivery.alert_id == alert.alert_id))
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].recipient_phone == "+972500000001"
