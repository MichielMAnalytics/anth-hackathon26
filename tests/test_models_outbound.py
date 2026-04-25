from sqlalchemy import select

from server.db.alerts import Alert
from server.db.identity import NGO, Account
from server.db.outbound import OutboundMessage, Sighting


async def test_outbound_with_attempt_chain(db):
    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()
    acc = Account(phone="+972500000003", ngo_id=ngo.ngo_id)
    db.add(acc)
    await db.flush()

    push = OutboundMessage(
        ngo_id=ngo.ngo_id,
        recipient_phone=acc.phone,
        channel="app",
        body="hello",
        status="sending",
        attempt=1,
    )
    db.add(push)
    await db.flush()

    sms_fallback = OutboundMessage(
        ngo_id=ngo.ngo_id,
        recipient_phone=acc.phone,
        channel="sms",
        body="hello",
        status="queued",
        attempt=2,
        previous_out_id=push.out_id,
    )
    db.add(sms_fallback)
    await db.flush()

    rows = (
        await db.execute(
            select(OutboundMessage).where(OutboundMessage.recipient_phone == acc.phone)
        )
    ).scalars().all()
    assert len(rows) == 2


async def test_sighting_holds_embedding_and_photo_urls(db):
    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()
    alert = Alert(ngo_id=ngo.ngo_id, person_name="Maya", status="active")
    db.add(alert)
    await db.flush()

    s = Sighting(
        ngo_id=ngo.ngo_id,
        alert_id=alert.alert_id,
        observer_phone="+972500000004",
        geohash="sv8d6r",
        notes="bakery, walking south, red jacket",
        confidence=0.85,
        photo_urls=["https://x/y.jpg"],
        notes_embedding=[0.1] * 512,
    )
    db.add(s)
    await db.flush()

    fetched = (await db.execute(select(Sighting).where(Sighting.sighting_id == s.sighting_id))).scalar_one()
    assert fetched.photo_urls == ["https://x/y.jpg"]
    assert len(fetched.notes_embedding) == 512
