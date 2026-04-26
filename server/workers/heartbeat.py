"""Heartbeat scheduler.

Per spec §4.3: a periodic task inserts a synthetic empty Bucket for every
active Alert. The agent worker claims it and runs the consolidation prompt
— usually a noop, sometimes a cluster refresh / trajectory extension /
status update. Result: even with zero inbound, the dashboard ticks every
heartbeat interval, proving the system is breathing on its own.

Configuration:
  HEARTBEAT_INTERVAL_SEC — default 300 (5 min). Set lower (e.g. 60) for
                           a livelier demo.
  HEARTBEAT_ENABLED       — default true; set "false" to disable.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from server.db.alerts import Alert
from server.db.messages import Bucket
from server.eventbus.postgres import PostgresEventBus

logger = logging.getLogger(__name__)


def _interval_seconds() -> float:
    raw = os.environ.get("HEARTBEAT_INTERVAL_SEC", "300")
    try:
        return max(10.0, float(raw))
    except ValueError:
        return 300.0


def _enabled() -> bool:
    return os.environ.get("HEARTBEAT_ENABLED", "true").lower() != "false"


async def _tick_once(
    session_maker: async_sessionmaker,
    eventbus: PostgresEventBus,
) -> int:
    """Insert one synthetic Bucket per active Alert; return count."""
    now = datetime.now(UTC)
    inserted = 0
    async with session_maker() as session:
        alerts = (
            await session.execute(select(Alert).where(Alert.status == "active"))
        ).scalars().all()
        for alert in alerts:
            bucket_key = f"heartbeat:{alert.alert_id}:{now.isoformat()}"
            bucket = Bucket(
                bucket_key=bucket_key,
                ngo_id=alert.ngo_id,
                alert_id=alert.alert_id,
                geohash_prefix_4=(alert.region_geohash_prefix or "")[:4] or None,
                window_start=now,
                window_length_ms=0,
                status="open",
            )
            session.add(bucket)
            inserted += 1
        await session.commit()

    # Notify the agent worker to drain.
    if inserted:
        try:
            await eventbus.publish("bucket_open", "heartbeat")
        except Exception as exc:  # noqa: BLE001
            logger.warning("heartbeat: publish failed: %s", exc)
    return inserted


async def heartbeat_loop(
    eventbus: PostgresEventBus,
    session_maker: async_sessionmaker,
) -> None:
    """Long-running coroutine: ticks every HEARTBEAT_INTERVAL_SEC."""
    if not _enabled():
        logger.info("heartbeat: disabled via HEARTBEAT_ENABLED=false")
        return
    interval = _interval_seconds()
    logger.info("heartbeat: starting, interval=%.0fs", interval)
    try:
        # Wait one full interval before the first tick so we don't burst at
        # boot together with the seed.
        await asyncio.sleep(interval)
        while True:
            try:
                count = await _tick_once(session_maker, eventbus)
                logger.info("heartbeat: inserted %d synthetic buckets", count)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.exception("heartbeat: tick failed: %s", exc)
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        raise
