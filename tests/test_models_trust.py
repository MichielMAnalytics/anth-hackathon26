from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from server.db.identity import NGO
from server.db.trust import BadActor


async def test_bad_actor_with_expiry(db):
    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()

    ba = BadActor(
        phone="+972500000099",
        ngo_id=ngo.ngo_id,
        reason="repeated false sightings",
        marked_by="agent",
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db.add(ba)
    await db.flush()

    fetched = (
        await db.execute(select(BadActor).where(BadActor.phone == "+972500000099"))
    ).scalar_one()
    assert fetched.reason == "repeated false sightings"
