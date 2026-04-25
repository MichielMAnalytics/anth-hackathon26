import json

from sqlalchemy import select

from server.db.alerts import Alert
from server.db.identity import NGO, Account
from server.db.messages import Bucket, InboundMessage, TriagedMessage


async def test_inbound_message_with_jsonb_columns(db):
    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()
    acc = Account(phone="+972500000001", ngo_id=ngo.ngo_id)
    alert = Alert(ngo_id=ngo.ngo_id, person_name="Maya", status="active")
    db.add_all([acc, alert])
    await db.flush()

    msg = InboundMessage(
        ngo_id=ngo.ngo_id,
        channel="app",
        sender_phone=acc.phone,
        in_reply_to_alert_id=alert.alert_id,
        body="saw a girl matching photo",
        media_urls=["https://example/photo.jpg"],
        raw={"jwt_sub": "abc"},
        status="new",
    )
    db.add(msg)
    await db.flush()

    fetched = (
        await db.execute(select(InboundMessage).where(InboundMessage.msg_id == msg.msg_id))
    ).scalar_one()
    assert fetched.media_urls == ["https://example/photo.jpg"]
    assert fetched.raw == {"jwt_sub": "abc"}


async def test_triaged_message_holds_embedding(db):
    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()
    acc = Account(phone="+972500000002", ngo_id=ngo.ngo_id)
    db.add(acc)
    await db.flush()

    inbound = InboundMessage(
        ngo_id=ngo.ngo_id,
        channel="app",
        sender_phone=acc.phone,
        body="x",
    )
    db.add(inbound)
    await db.flush()

    triaged = TriagedMessage(
        msg_id=inbound.msg_id,
        ngo_id=ngo.ngo_id,
        classification="sighting",
        geohash6="sv8d6r",
        geohash_source="app_gps",
        confidence=0.9,
        language="he",
        trust_score=0.7,
        bucket_key="A1|sv8d|2026-04-25T10:00:00",
        body_embedding=[0.0] * 512,
    )
    db.add(triaged)
    await db.flush()

    fetched = (
        await db.execute(select(TriagedMessage).where(TriagedMessage.msg_id == inbound.msg_id))
    ).scalar_one()
    assert len(fetched.body_embedding) == 512


async def test_bucket_is_unique_per_key(db):
    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()
    alert = Alert(ngo_id=ngo.ngo_id, person_name="Maya", status="active")
    db.add(alert)
    await db.flush()

    from datetime import UTC, datetime
    b = Bucket(
        bucket_key="A1|sv8d|2026-04-25T10:00:00",
        ngo_id=ngo.ngo_id,
        alert_id=alert.alert_id,
        geohash_prefix_4="sv8d",
        window_start=datetime.now(UTC),
        window_length_ms=3000,
        status="open",
    )
    db.add(b)
    await db.flush()
    fetched = (await db.execute(select(Bucket).where(Bucket.bucket_key == b.bucket_key))).scalar_one()
    assert fetched.status == "open"
