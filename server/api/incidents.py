from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.api.auth_dep import current_operator
from server.api.registry import REGIONS
from server.db.alerts import Alert
from server.db.decisions import AgentDecision, ToolCall
from server.db.messages import Bucket, InboundMessage, TriagedMessage
from server.db.outbound import OutboundMessage
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


def alert_to_incident_shape(alert: Alert | None) -> dict[str, Any]:
    """Camel-case Incident shape matching what GET /api/incidents returns.

    Used by the WebSocket layer so the store can upsert incidents from WS
    events without a shape translation step. Aggregate fields the list
    endpoint computes (messageCount, lastActivity) are 0 / null here —
    the frontend can fall back to a refetch if it needs them.
    """
    if alert is None:
        return {}
    region_key = _region_for_prefix(alert.region_geohash_prefix)
    meta = REGIONS[region_key]
    return {
        "id": alert.alert_id,
        "category": alert.category or "other",
        "title": alert.person_name or (alert.description or "")[:80],
        "severity": _severity(alert.urgency_tier),
        "region": region_key,
        "lat": float(meta["lat"]),
        "lon": float(meta["lon"]),
        "details": {
            "description": alert.description,
            "last_seen_geohash": alert.last_seen_geohash,
            "expires_at": alert.expires_at.isoformat() if alert.expires_at else None,
        },
        "messageCount": 0,
        "lastActivity": None,
    }


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


@router.get("/incidents/{incident_id}/messages")
async def incident_messages(
    incident_id: str,
    _op: Annotated[dict[str, Any], Depends(current_operator)],
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    alert = (
        await db.execute(select(Alert).where(Alert.alert_id == incident_id))
    ).scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail="incident not found")

    inbound_rows = (
        await db.execute(
            select(InboundMessage)
            .where(InboundMessage.in_reply_to_alert_id == incident_id)
            .order_by(InboundMessage.received_at)
        )
    ).scalars().all()

    triage_geohash: dict[str, str] = {}
    if inbound_rows:
        msg_ids = [m.msg_id for m in inbound_rows]
        triage_rows = (
            await db.execute(select(TriagedMessage).where(TriagedMessage.msg_id.in_(msg_ids)))
        ).scalars().all()
        triage_geohash = {t.msg_id: t.geohash6 for t in triage_rows if t.geohash6}

    messages: list[dict[str, Any]] = []
    for msg in inbound_rows:
        via = msg.channel if msg.channel in ("app", "sms", "fallback") else None
        messages.append({
            "messageId": msg.msg_id,
            "incidentId": incident_id,
            "from": msg.sender_phone,
            "body": msg.body,
            "ts": msg.received_at.isoformat(),
            "geohash": triage_geohash.get(msg.msg_id),
            "lat": None,
            "lon": None,
            "extracted": None,
            "outbound": False,
            "via": via,
        })

    # Agent-issued outbounds: linked to an AgentDecision via Bucket.alert_id.
    # Per-recipient delivery rows carry previous_out_id; we want the
    # parent broadcast row only, so the timeline shows one bubble per send.
    agent_outbound_rows = (
        await db.execute(
            select(OutboundMessage)
            .join(ToolCall, OutboundMessage.tool_call_id == ToolCall.call_id)
            .join(AgentDecision, ToolCall.decision_id == AgentDecision.decision_id)
            .join(Bucket, AgentDecision.bucket_key == Bucket.bucket_key)
            .where(Bucket.alert_id == incident_id)
            .where(OutboundMessage.previous_out_id.is_(None))
        )
    ).scalars().all()

    # Operator-issued outbounds: ToolCall has no decision_id; the incident
    # is recorded inside ToolCall.args -> 'incident_id'.
    operator_outbound_rows = (
        await db.execute(
            select(OutboundMessage)
            .join(ToolCall, OutboundMessage.tool_call_id == ToolCall.call_id)
            .where(ToolCall.decision_id.is_(None))
            .where(ToolCall.args["incident_id"].astext == incident_id)
            .where(OutboundMessage.previous_out_id.is_(None))
        )
    ).scalars().all()

    outbound_rows = list(agent_outbound_rows) + list(operator_outbound_rows)

    for out in outbound_rows:
        via = out.channel if out.channel in ("app", "sms", "fallback") else None
        messages.append({
            "messageId": out.out_id,
            "incidentId": incident_id,
            "from": "ngo",
            "body": out.body,
            "ts": out.created_at.isoformat(),
            "geohash": None,
            "lat": None,
            "lon": None,
            "extracted": None,
            "outbound": True,
            "via": via,
        })

    messages.sort(key=lambda m: m["ts"])
    return messages
