"""Operator approval inbox.

  GET    /api/suggestions                — list pending suggestions
  POST   /api/suggestions/{id}/approve   — approve, dispatcher picks up
  POST   /api/suggestions/{id}/reject    — reject, audit retained

Each pending suggestion is a `ToolCall(approval_status='pending')`. We
join up to its parent AgentDecision so the inbox UI can show the agent's
reasoning_summary alongside the proposed action.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.api.auth_dep import current_operator
from server.db.alerts import Alert
from server.db.decisions import AgentDecision, ToolCall
from server.db.engine import get_engine
from server.db.messages import Bucket
from server.db.session import get_db
from server.eventbus.postgres import PostgresEventBus

router = APIRouter(prefix="/api")


def _summarize_audience(args: dict[str, Any]) -> dict[str, Any]:
    aud = args.get("audience") or {}
    return {
        "type": aud.get("type"),
        "phone": aud.get("phone"),
        "audienceId": aud.get("id"),
        "phones": aud.get("phones"),
        "geohash_prefix": aud.get("geohash_prefix"),
        "alert_id": aud.get("alert_id"),
    }


def _suggestion_shape(
    tc: ToolCall, decision: AgentDecision | None, alert: Alert | None
) -> dict[str, Any]:
    args = tc.args or {}
    bodies = args.get("bodies") if isinstance(args, dict) else None
    return {
        "id": tc.call_id,
        "tool": tc.tool_name,
        "args": args,
        "audience": _summarize_audience(args),
        "bodies": bodies or {},
        "createdAt": tc.created_at.isoformat() if tc.created_at else None,
        "decision": (
            {
                "id": decision.decision_id,
                "model": decision.model,
                "summary": decision.reasoning_summary,
                "totalTurns": decision.total_turns,
                "costUsd": decision.cost_usd,
                "latencyMs": decision.latency_ms,
            }
            if decision is not None
            else None
        ),
        "alert": (
            {
                "id": alert.alert_id,
                "personName": alert.person_name,
                "category": alert.category,
                "urgencyTier": alert.urgency_tier,
                "regionPrefix": alert.region_geohash_prefix,
            }
            if alert is not None
            else None
        ),
    }


@router.get("/suggestions")
async def list_suggestions(
    _op: Annotated[dict[str, Any], Depends(current_operator)],
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(ToolCall)
            .where(ToolCall.approval_status == "pending")
            .order_by(ToolCall.created_at.desc())
            .limit(100)
        )
    ).scalars().all()
    if not rows:
        return []

    decision_ids = {r.decision_id for r in rows if r.decision_id}
    decisions: dict[str, AgentDecision] = {}
    if decision_ids:
        d_rows = (
            await db.execute(
                select(AgentDecision).where(AgentDecision.decision_id.in_(decision_ids))
            )
        ).scalars().all()
        decisions = {d.decision_id: d for d in d_rows}

    bucket_keys = {d.bucket_key for d in decisions.values()}
    buckets: dict[str, Bucket] = {}
    if bucket_keys:
        b_rows = (
            await db.execute(select(Bucket).where(Bucket.bucket_key.in_(bucket_keys)))
        ).scalars().all()
        buckets = {b.bucket_key: b for b in b_rows}

    alert_ids = {b.alert_id for b in buckets.values()}
    # Operator-issued ToolCalls have no decision; fall back to args['incident_id'].
    for r in rows:
        if r.decision_id is None and isinstance(r.args, dict):
            inc = r.args.get("incident_id")
            if inc:
                alert_ids.add(inc)
    alerts: dict[str, Alert] = {}
    if alert_ids:
        a_rows = (
            await db.execute(select(Alert).where(Alert.alert_id.in_(alert_ids)))
        ).scalars().all()
        alerts = {a.alert_id: a for a in a_rows}

    out: list[dict[str, Any]] = []
    for r in rows:
        decision = decisions.get(r.decision_id) if r.decision_id else None
        alert: Alert | None = None
        if decision is not None:
            bucket = buckets.get(decision.bucket_key)
            if bucket is not None:
                alert = alerts.get(bucket.alert_id)
        elif isinstance(r.args, dict):
            alert = alerts.get(r.args.get("incident_id"))
        out.append(_suggestion_shape(r, decision, alert))
    return out


async def _publish_resolved(call_id: str, status: str) -> None:
    try:
        bus = PostgresEventBus(get_engine())
        await bus.publish("suggestion_resolved", f"{call_id}|{status}")
    except Exception:
        pass


async def _resolve(
    call_id: str,
    status: str,
    operator: dict[str, Any],
    db: AsyncSession,
) -> dict[str, Any]:
    tc = await db.get(ToolCall, call_id)
    if tc is None:
        raise HTTPException(status_code=404, detail="suggestion not found")
    if tc.approval_status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"suggestion already {tc.approval_status}",
        )

    tc.approval_status = status
    tc.decided_by = operator["id"]
    tc.decided_at = datetime.now(UTC)
    if status == "rejected":
        tc.status = "done"
    # Approved suggestions stay pending so the dispatcher can pick them up.
    await db.commit()
    await _publish_resolved(tc.call_id, status)
    return {
        "id": tc.call_id,
        "approvalStatus": tc.approval_status,
        "decidedBy": tc.decided_by,
        "decidedAt": tc.decided_at.isoformat(),
    }


@router.post("/suggestions/{call_id}/approve")
async def approve(
    call_id: str,
    operator: Annotated[dict[str, Any], Depends(current_operator)],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await _resolve(call_id, "approved", operator, db)


@router.post("/suggestions/{call_id}/reject")
async def reject(
    call_id: str,
    operator: Annotated[dict[str, Any], Depends(current_operator)],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await _resolve(call_id, "rejected", operator, db)
