"""Operator-initiated write endpoints.

Three endpoints used by the NGO console to send outbound:

    POST /api/alerts                       — operator pushes a region alert
    POST /api/requests                     — operator sends a help request
    POST /api/cases/{incident_id}/messages — operator replies inside a case

All three follow the same pattern as the agent-issued path:
  - One `ToolCall` row (tool='send', mode='execute',
    approval_status='approved', decided_by=<operator_id>, decision_id=NULL)
  - One placeholder `OutboundMessage` row (recipient='audience:<id>')
  - An `incident_upserted` event so the UI refreshes the case timeline.

This gives a unified audit trail across agent and operator actions.
"""
from __future__ import annotations

import hashlib
import json
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.api.auth_dep import current_operator
from server.api.registry import AUDIENCES
from server.db.alerts import Alert
from server.db.decisions import ToolCall
from server.db.engine import get_engine
from server.db.outbound import OutboundMessage
from server.db.session import get_db
from server.eventbus.postgres import PostgresEventBus

router = APIRouter(prefix="/api")

_AUDIENCE_INDEX: dict[str, dict[str, Any]] = {a["id"]: a for a in AUDIENCES}


class BroadcastBody(BaseModel):
    incidentId: Optional[str] = None
    audienceId: str
    channels: str = Field(description="Channel: app | sms | fallback")
    region: Optional[str] = None
    body: str
    attachments: dict[str, Any] = Field(default_factory=dict)


class CaseMessageBody(BaseModel):
    body: str
    via: str = Field(description="Channel: app | sms | fallback")
    audienceId: Optional[str] = None


def _idempotency_key(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _ack(audience: dict[str, Any], channel: str, mode: str) -> dict[str, Any]:
    queued = int(audience.get("count") or 0)
    batches = max(1, (queued + 99) // 100)
    return {
        "ok": True,
        "queued": queued,
        "batches": batches,
        "etaSeconds": batches * 2,
        "channels": [channel],
        "audienceLabel": audience.get("label") or audience.get("id") or "audience",
        "note": (
            f"Operator {mode} queued for {queued:,} recipients via {channel}"
        ),
    }


async def _publish_incident_upserted(alert_id: Optional[str]) -> None:
    if not alert_id:
        return
    try:
        bus = PostgresEventBus(get_engine())
        await bus.publish("incident_upserted", alert_id)
    except Exception:
        # Event bus is best-effort here; persistence already succeeded.
        pass


async def _persist_send(
    db: AsyncSession,
    *,
    operator: dict[str, Any],
    audience: dict[str, Any],
    incident_id: Optional[str],
    channel: str,
    body: str,
    mode: str,
    region: Optional[str],
    attachments: dict[str, Any],
    extra_args: Optional[dict[str, Any]] = None,
) -> tuple[ToolCall, OutboundMessage, Optional[Alert]]:
    """Common persistence: one ToolCall + one placeholder OutboundMessage.

    Returns (tool_call, outbound, resolved_alert).
    """
    alert: Optional[Alert] = None
    ngo_id: Optional[str] = None
    if incident_id:
        alert = (
            await db.execute(select(Alert).where(Alert.alert_id == incident_id))
        ).scalar_one_or_none()
        if alert is None:
            raise HTTPException(status_code=404, detail="incident not found")
        ngo_id = alert.ngo_id
    if ngo_id is None:
        # Region-only broadcast without an incident — pin to first NGO.
        from server.db.identity import NGO

        first_ngo = (await db.execute(select(NGO))).scalars().first()
        if first_ngo is None:
            raise HTTPException(status_code=400, detail="no NGO configured")
        ngo_id = first_ngo.ngo_id

    args: dict[str, Any] = {
        "audience": {"type": "audience_id", "id": audience["id"]},
        "bodies": {"en": body},
        "mode": "execute",
        "channel": channel,
        "incident_id": incident_id,
        "region": region,
        "attachments": attachments,
        "send_mode": mode,  # 'alert' | 'request' | 'case_message'
    }
    if extra_args:
        args.update(extra_args)

    idem = _idempotency_key(
        operator["id"],
        incident_id or "no-incident",
        audience["id"],
        channel,
        mode,
        body,
    )

    tc = ToolCall(
        ngo_id=ngo_id,
        decision_id=None,
        tool_name="send",
        args=args,
        idempotency_key=idem,
        mode="execute",
        approval_status="approved",
        decided_by=operator["id"],
        status="pending",
    )
    db.add(tc)
    await db.flush()

    out = OutboundMessage(
        ngo_id=ngo_id,
        tool_call_id=tc.call_id,
        recipient_phone=f"audience:{audience['id']}",
        channel=channel,
        body=body,
        language="en",
        status="queued",
    )
    db.add(out)
    await db.flush()
    return tc, out, alert


@router.post("/alerts")
async def post_alert(
    payload: BroadcastBody,
    operator: Annotated[dict[str, Any], Depends(current_operator)],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    audience = _AUDIENCE_INDEX.get(payload.audienceId)
    if audience is None:
        raise HTTPException(status_code=400, detail="unknown audience")

    if operator.get("role") == "junior":
        # Senior-only action: keep parity with the old CPMS permission model.
        return {
            "ok": False,
            "error": "permission",
            "reason": "Junior operators cannot broadcast amber alerts.",
        }

    _, _, alert = await _persist_send(
        db,
        operator=operator,
        audience=audience,
        incident_id=payload.incidentId,
        channel=payload.channels,
        body=payload.body,
        mode="alert",
        region=payload.region,
        attachments=payload.attachments,
    )
    await db.commit()
    await _publish_incident_upserted(alert.alert_id if alert else None)
    return _ack(audience, payload.channels, "alert")


@router.post("/requests")
async def post_request(
    payload: BroadcastBody,
    operator: Annotated[dict[str, Any], Depends(current_operator)],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    audience = _AUDIENCE_INDEX.get(payload.audienceId)
    if audience is None:
        raise HTTPException(status_code=400, detail="unknown audience")

    _, _, alert = await _persist_send(
        db,
        operator=operator,
        audience=audience,
        incident_id=payload.incidentId,
        channel=payload.channels,
        body=payload.body,
        mode="request",
        region=payload.region,
        attachments=payload.attachments,
    )
    await db.commit()
    await _publish_incident_upserted(alert.alert_id if alert else None)
    return _ack(audience, payload.channels, "request")


@router.post("/cases/{incident_id}/messages")
async def post_case_message(
    incident_id: str,
    payload: CaseMessageBody,
    operator: Annotated[dict[str, Any], Depends(current_operator)],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    audience = (
        _AUDIENCE_INDEX.get(payload.audienceId)
        if payload.audienceId
        else {"id": "case_reply", "label": "Case reply", "count": 1}
    )
    if audience is None:
        raise HTTPException(status_code=400, detail="unknown audience")

    _, _, alert = await _persist_send(
        db,
        operator=operator,
        audience=audience,
        incident_id=incident_id,
        channel=payload.via,
        body=payload.body,
        mode="case_message",
        region=None,
        attachments={},
    )
    await db.commit()
    await _publish_incident_upserted(alert.alert_id if alert else None)
    return {"ok": True, "broadcast": _ack(audience, payload.via, "case")}
