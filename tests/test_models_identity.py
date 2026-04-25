import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from server.db.identity import NGO, Account


async def test_ngo_can_be_inserted_and_queried(db):
    ngo = NGO(name="Warchild", region_geohash_prefix="sv")
    db.add(ngo)
    await db.flush()

    fetched = (await db.execute(select(NGO).where(NGO.ngo_id == ngo.ngo_id))).scalar_one()
    assert fetched.name == "Warchild"
    assert len(fetched.ngo_id) == 26


async def test_account_phone_is_unique(db):
    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()

    a = Account(phone="+972501234567", ngo_id=ngo.ngo_id, language="he")
    db.add(a)
    await db.flush()

    dup = Account(phone="+972501234567", ngo_id=ngo.ngo_id, language="ar")
    db.add(dup)
    with pytest.raises(IntegrityError):
        await db.flush()
