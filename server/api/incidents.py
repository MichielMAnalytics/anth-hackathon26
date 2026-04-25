from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.api.auth_dep import current_operator
from server.api.registry import REGIONS
from server.db.alerts import Alert
from server.db.messages import InboundMessage
from server.db.session import get_db

router = APIRouter(prefix="/api")

_URGENCY_TO_SEVERITY = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}
_GEOHASH_TO_REGION: dict[str, str] = {meta["geohash_prefix"]: key for key, meta in REGIONS.items()}
_DEFAULT_REGION = next(iter(REGIONS.keys()))


def _severity(urgency_tier: str | None) -> str:
    return _URGENCY_TO_SEVERITY.get(urgency_tier or "", "medium")


def _region_for_prefix(prefix: str | None) -> str:
    if not prefix:
        return _DEFAULT_REGION
    if prefix in _GEOHASH_TO_REGION:
        return _GEOHASH_TO_REGION[prefix]
    for gh, key in _GEOHASH_TO_REGION.items():
        if prefix.startswith(gh) or gh.startswith(prefix):
            return key
    return _DEFAULT_REGION


@router.get("/incidents")
async def list_incidents(
    _op: Annotated[dict[str, Any], Depends(current_operator)],
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    alerts = (await db.execute(select(Alert).where(Alert.status == "active"))).scalars().all()
    if not alerts:
        return []

    alert_ids = [a.alert_id for a in alerts]

    count_rows = (
        await db.execute(
            select(InboundMessage.in_reply_to_alert_id, func.count().label("cnt"))
            .where(InboundMessage.in_reply_to_alert_id.in_(alert_ids))
            .group_by(InboundMessage.in_reply_to_alert_id)
        )
    ).all()
    msg_counts: dict[str, int] = {r.in_reply_to_alert_id: r.cnt for r in count_rows}

    activity_rows = (
        await db.execute(
            select(
                InboundMessage.in_reply_to_alert_id,
                func.max(InboundMessage.received_at).label("last_at"),
            )
            .where(InboundMessage.in_reply_to_alert_id.in_(alert_ids))
            .group_by(InboundMessage.in_reply_to_alert_id)
        )
    ).all()
    last_activity: dict[str, str] = {
        r.in_reply_to_alert_id: r.last_at.isoformat() for r in activity_rows
    }

    result = []
    for alert in alerts:
        region_key = _region_for_prefix(alert.region_geohash_prefix)
        meta = REGIONS[region_key]
        title = alert.person_name or (alert.description or "")[:80]
        category = alert.category or "other"
        result.append({
            "id": alert.alert_id,
            "category": category,
            "title": title,
            "severity": _severity(alert.urgency_tier),
            "region": region_key,
            "lat": float(meta["lat"]),
            "lon": float(meta["lon"]),
            "details": {
                "description": alert.description,
                "last_seen_geohash": alert.last_seen_geohash,
                "expires_at": alert.expires_at.isoformat() if alert.expires_at else None,
            },
            "messageCount": msg_counts.get(alert.alert_id, 0),
            "lastActivity": last_activity.get(alert.alert_id),
        })
    return result
