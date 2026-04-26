"""Heartbeat scheduler tests.

We don't run the full loop (it sleeps for the full interval before its
first tick). We exercise _tick_once directly to validate the contract:
inserts one synthetic Bucket per active alert and publishes bucket_open.
"""
from __future__ import annotations

import asyncio

import pytest_asyncio
from sqlalchemy import delete, select

from server.db.alerts import Alert, AlertDelivery
from server.db.identity import NGO, Account
from server.db.messages import Bucket, InboundMessage, TriagedMessage


_NGO_NAME = "HeartbeatTestNGO"


async def _purge(test_session_maker) -> None:
    async with test_session_maker() as s:
        ngo_ids = (
            await s.execute(select(NGO.ngo_id).where(NGO.name == _NGO_NAME))
        ).scalars().all()
        if not ngo_ids:
            return
        alert_ids = (
            await s.execute(select(Alert.alert_id).where(Alert.ngo_id.in_(ngo_ids)))
        ).scalars().all()
        if alert_ids:
            await s.execute(delete(Bucket).where(Bucket.alert_id.in_(alert_ids)))
            await s.execute(
                delete(AlertDelivery).where(AlertDelivery.alert_id.in_(alert_ids))
            )
            await s.execute(delete(Alert).where(Alert.alert_id.in_(alert_ids)))
        await s.execute(delete(Account).where(Account.ngo_id.in_(ngo_ids)))
        await s.execute(delete(NGO).where(NGO.ngo_id.in_(ngo_ids)))
        await s.commit()


@pytest_asyncio.fixture
async def two_active_alerts(test_session_maker):
    await _purge(test_session_maker)
    async with test_session_maker() as s:
        ngo = NGO(name=_NGO_NAME)
        s.add(ngo)
        await s.flush()
        a1 = Alert(
            ngo_id=ngo.ngo_id, person_name="HB One", status="active",
            region_geohash_prefix="sv8d",
        )
        a2 = Alert(
            ngo_id=ngo.ngo_id, person_name="HB Two", status="active",
            region_geohash_prefix="sv3p",
        )
        # Inactive shouldn't get a bucket
        a3 = Alert(
            ngo_id=ngo.ngo_id, person_name="HB Done", status="resolved",
            region_geohash_prefix="sv9j",
        )
        s.add_all([a1, a2, a3])
        await s.commit()
        out = {"ngo_id": ngo.ngo_id,
               "alert_ids": [a1.alert_id, a2.alert_id, a3.alert_id]}
    yield out
    await _purge(test_session_maker)


async def test_heartbeat_tick_inserts_bucket_per_active_alert(
    two_active_alerts, test_engine, test_session_maker,
):
    from server.eventbus.postgres import PostgresEventBus
    from server.workers.heartbeat import _tick_once

    eventbus = PostgresEventBus(test_engine)
    inserted = await _tick_once(test_session_maker, eventbus)
    assert inserted == 2  # only the two active alerts

    async with test_session_maker() as s:
        active_ids = two_active_alerts["alert_ids"][:2]
        buckets = (
            await s.execute(select(Bucket).where(Bucket.alert_id.in_(active_ids)))
        ).scalars().all()
        assert len(buckets) == 2
        for b in buckets:
            assert b.bucket_key.startswith("heartbeat:")
            assert b.status == "open"
            assert b.window_length_ms == 0


async def test_heartbeat_tick_no_active_alerts_returns_zero(
    test_engine, test_session_maker,
):
    """No active alerts → no buckets, no error."""
    from server.eventbus.postgres import PostgresEventBus
    from server.workers.heartbeat import _tick_once

    # Make sure there are no active alerts.
    async with test_session_maker() as s:
        active = (
            await s.execute(select(Alert).where(Alert.status == "active"))
        ).scalars().all()
        for a in active:
            a.status = "resolved"
        await s.commit()

    eventbus = PostgresEventBus(test_engine)
    inserted = await _tick_once(test_session_maker, eventbus)
    assert inserted == 0

    # Restore activity for downstream tests.
    async with test_session_maker() as s:
        for a in (
            await s.execute(select(Alert))
        ).scalars().all():
            if a.person_name in ("HB One", "HB Two", "Tamar", "Yael",
                                 "Amira Hassan", "Shira", "Layla Saeed"):
                a.status = "active"
        await s.commit()
