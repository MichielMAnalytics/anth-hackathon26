from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.api.auth_dep import current_operator
from server.api.registry import REGIONS
from server.db.alerts import Alert
from server.db.identity import Account
from server.db.messages import InboundMessage
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
