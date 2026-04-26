from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.api.auth_dep import current_operator
from server.api.registry import REGIONS
from server.db.alerts import Alert
from server.db.messages import InboundMessage
from server.db.session import get_db

router = APIRouter(prefix="/api")

DEFAULT_WINDOW_MINUTES = 60
SPARKLINE_SLOTS = 12
BASELINE_MSGS_PER_MIN = 0.5

_GEOHASH_TO_REGION: dict[str, str] = {meta["geohash_prefix"]: key for key, meta in REGIONS.items()}
_DEFAULT_REGION = next(iter(REGIONS.keys()))


def _severity(urgency_tier: str | None) -> str:
    return {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}.get(
        urgency_tier or "", "medium"
    )


def _region_for_prefix(prefix: str | None) -> str:
    if not prefix:
        return _DEFAULT_REGION
    for gh, key in _GEOHASH_TO_REGION.items():
        if prefix == gh or prefix.startswith(gh) or gh.startswith(prefix):
            return key
    return _DEFAULT_REGION


@router.get("/dashboard")
async def dashboard(
    _op: Annotated[dict[str, Any], Depends(current_operator)],
    minutes: Annotated[int, Query(ge=5, le=1440)] = DEFAULT_WINDOW_MINUTES,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    now = datetime.now(UTC)
    window_minutes = minutes
    # Sparkline slot length scales with the requested window so the chart
    # always covers the full range with the same number of buckets.
    sparkline_slot_minutes = max(1, window_minutes // SPARKLINE_SLOTS)
    window_start = now - timedelta(minutes=window_minutes)

    alerts = (await db.execute(select(Alert).where(Alert.status == "active"))).scalars().all()
    alert_map: dict[str, Alert] = {a.alert_id: a for a in alerts}

    msgs_in_window = (
        await db.execute(
            select(InboundMessage)
            .where(InboundMessage.in_reply_to_alert_id.isnot(None))
            .where(InboundMessage.received_at >= window_start)
            .order_by(InboundMessage.received_at.desc())
        )
    ).scalars().all()

    region_msgs: dict[str, list[InboundMessage]] = {k: [] for k in REGIONS}
    region_alerts: dict[str, list[Alert]] = {k: [] for k in REGIONS}

    for msg in msgs_in_window:
        if msg.in_reply_to_alert_id and msg.in_reply_to_alert_id in alert_map:
            alert = alert_map[msg.in_reply_to_alert_id]
            region_msgs[_region_for_prefix(alert.region_geohash_prefix)].append(msg)

    for alert in alerts:
        region_alerts[_region_for_prefix(alert.region_geohash_prefix)].append(alert)

    per_alert_count: dict[str, int] = {}
    if alerts:
        rows = (
            await db.execute(
                select(InboundMessage.in_reply_to_alert_id, func.count().label("cnt"))
                .where(InboundMessage.in_reply_to_alert_id.in_([a.alert_id for a in alerts]))
                .group_by(InboundMessage.in_reply_to_alert_id)
            )
        ).all()
        per_alert_count = {r.in_reply_to_alert_id: r.cnt for r in rows}

    regions_out = []
    for region_key, meta in REGIONS.items():
        r_msgs = region_msgs[region_key]
        r_alerts = region_alerts[region_key]

        msg_count = len(r_msgs)
        distinct_senders = len({m.sender_phone for m in r_msgs})
        msgs_per_min = msg_count / window_minutes
        urgency = min(1.0, msgs_per_min / max(1, BASELINE_MSGS_PER_MIN) / 5.0)
        anomaly = msgs_per_min > BASELINE_MSGS_PER_MIN * 2

        sparkline = [0.0] * SPARKLINE_SLOTS
        for msg in r_msgs:
            age_minutes = (now - msg.received_at).total_seconds() / 60
            if 0 <= age_minutes < window_minutes:
                slot = min(int(age_minutes // sparkline_slot_minutes), SPARKLINE_SLOTS - 1)
                sparkline[SPARKLINE_SLOTS - 1 - slot] += 1.0

        sorted_alerts = sorted(
            r_alerts, key=lambda a: per_alert_count.get(a.alert_id, 0), reverse=True
        )[:3]
        cases = [
            {
                "id": a.alert_id,
                "title": a.person_name or (a.description or "")[:80],
                "category": a.category or "other",
                "severity": _severity(a.urgency_tier),
                "messageCount": per_alert_count.get(a.alert_id, 0),
            }
            for a in sorted_alerts
        ]

        regions_out.append({
            "region": region_key,
            "label": meta["label"],
            "lat": float(meta["lat"]),
            "lon": float(meta["lon"]),
            "urgency": round(urgency, 4),
            "anomaly": anomaly,
            "msgsPerMin": round(msgs_per_min, 4),
            "baselineMsgsPerMin": BASELINE_MSGS_PER_MIN,
            "openCases": len(r_alerts),
            "messageCount": msg_count,
            "distressCount": msg_count,
            "distinctSenders": distinct_senders,
            "sparkline": sparkline,
            "themes": [],
            "cases": cases,
        })

    recent_distress = []
    for msg in msgs_in_window[:10]:
        if msg.in_reply_to_alert_id and msg.in_reply_to_alert_id in alert_map:
            alert = alert_map[msg.in_reply_to_alert_id]
            region_key = _region_for_prefix(alert.region_geohash_prefix)
            meta = REGIONS[region_key]
            recent_distress.append({
                "messageId": msg.msg_id,
                "incidentId": msg.in_reply_to_alert_id,
                "region": region_key,
                "regionLabel": meta["label"],
                "from": msg.sender_phone,
                "body": msg.body,
                "ts": msg.received_at.isoformat(),
            })

    return {
        "windowMinutes": window_minutes,
        "regions": regions_out,
        "recentDistress": recent_distress,
    }
