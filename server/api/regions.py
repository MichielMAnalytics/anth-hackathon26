from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.api.auth_dep import current_operator
from server.api.registry import REGIONS
from server.db.alerts import Alert
from server.db.identity import Account
from server.db.messages import Bucket, InboundMessage
from server.db.session import get_db

router = APIRouter(prefix="/api/regions")

BASELINE_MSGS_PER_MIN = 0.5


@router.get("/stats")
async def get_region_stats(
    _op: Annotated[dict[str, Any], Depends(current_operator)],
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    one_minute_ago = now - timedelta(minutes=1)
    results: list[dict[str, Any]] = []

    for region_key, meta in REGIONS.items():
        prefix: str = meta["geohash_prefix"]

        reachable = (
            await db.execute(
                select(func.count())
                .select_from(Account)
                .where(Account.last_known_geohash.like(f"{prefix}%"))
            )
        ).scalar_one()

        incident_count = (
            await db.execute(
                select(func.count())
                .select_from(Alert)
                .where(Alert.region_geohash_prefix.like(f"{prefix}%"))
            )
        ).scalar_one()

        message_count = (
            await db.execute(
                select(func.count())
                .select_from(InboundMessage)
                .join(Alert, InboundMessage.in_reply_to_alert_id == Alert.alert_id)
                .where(Alert.region_geohash_prefix.like(f"{prefix}%"))
            )
        ).scalar_one()

        recent_count = (
            await db.execute(
                select(func.count())
                .select_from(InboundMessage)
                .join(Alert, InboundMessage.in_reply_to_alert_id == Alert.alert_id)
                .where(
                    Alert.region_geohash_prefix.like(f"{prefix}%"),
                    InboundMessage.received_at >= one_minute_ago,
                )
            )
        ).scalar_one()

        msgs_per_min = float(recent_count)
        anomaly = msgs_per_min > 3 * BASELINE_MSGS_PER_MIN

        results.append({
            "region": region_key,
            "label": meta["label"],
            "lat": float(meta["lat"]),
            "lon": float(meta["lon"]),
            "reachable": int(reachable),
            "incidentCount": int(incident_count),
            "messageCount": int(message_count),
            "msgsPerMin": msgs_per_min,
            "baselineMsgsPerMin": BASELINE_MSGS_PER_MIN,
            "anomaly": anomaly,
        })

    return results


@router.get("/{region}/timeline")
async def region_timeline(
    region: str,
    _op: Annotated[dict[str, Any], Depends(current_operator)],
    minutes: Annotated[int, Query(ge=1, le=1440)] = 60,
    bucket: Annotated[int, Query(alias="bucket", ge=1, le=3600)] = 60,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if region not in REGIONS:
        raise HTTPException(status_code=404, detail="unknown region")

    meta = REGIONS[region]
    prefix: str = meta["geohash_prefix"]

    now = datetime.now(UTC)
    window_start = now - timedelta(minutes=minutes)

    rows = (
        await db.execute(
            select(
                func.floor(func.extract("epoch", Bucket.window_start) / bucket).label("slot"),
                func.count().label("cnt"),
            )
            .where(Bucket.geohash_prefix_4 == prefix)
            .where(Bucket.window_start >= window_start)
            .where(Bucket.window_start < now)
            .group_by("slot")
        )
    ).all()
    slot_to_count: dict[int, int] = {int(r.slot): int(r.cnt) for r in rows}

    total_slots = (minutes * 60) // bucket
    buckets: list[dict[str, Any]] = []
    for i in range(total_slots):
        slot_time = window_start + timedelta(seconds=i * bucket)
        slot_num = int(slot_time.timestamp()) // bucket
        buckets.append({"ts": slot_time.isoformat(), "count": slot_to_count.get(slot_num, 0)})

    return {
        "region": region,
        "minutes": minutes,
        "bucketSeconds": bucket,
        "buckets": buckets,
        "total": sum(slot_to_count.values()),
    }
