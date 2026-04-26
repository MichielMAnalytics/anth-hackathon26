"""Agent activity feed + header-pill stats.

  GET /api/decisions/recent?limit=20  — backfill for the activity tape
  GET /api/agent/stats                — aggregates for the header pill
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.api.auth_dep import current_operator
from server.db.alerts import Alert
from server.db.decisions import AgentDecision, ToolCall
from server.db.messages import Bucket
from server.db.session import get_db
from server.workers.narrate import narrate_decision

router = APIRouter(prefix="/api")


def _decision_shape(d: AgentDecision, alert: Alert | None, calls: list[ToolCall]) -> dict[str, Any]:
    is_heartbeat = d.bucket_key.startswith("heartbeat:")
    narration = narrate_decision(
        [{"tool_name": c.tool_name, "args": c.args, "mode": c.mode} for c in calls],
        alert=alert,
        is_heartbeat=is_heartbeat,
    )
    return {
        "id": d.decision_id,
        "model": d.model,
        "summary": d.reasoning_summary,
        "narration": narration,
        "totalTurns": d.total_turns,
        "latencyMs": d.latency_ms,
        "costUsd": d.cost_usd,
        "createdAt": d.created_at.isoformat() if d.created_at else None,
        "bucketKey": d.bucket_key,
        "isHeartbeat": is_heartbeat,
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
        "toolCalls": [
            {
                "id": c.call_id,
                "name": c.tool_name,
                "mode": c.mode,
                "approvalStatus": c.approval_status,
            }
            for c in calls
        ],
    }


@router.get("/decisions/recent")
async def recent_decisions(
    _op: Annotated[dict[str, Any], Depends(current_operator)],
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    decisions = (
        await db.execute(
            select(AgentDecision)
            .order_by(AgentDecision.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    if not decisions:
        return []

    bucket_keys = {d.bucket_key for d in decisions}
    buckets = (
        await db.execute(select(Bucket).where(Bucket.bucket_key.in_(bucket_keys)))
    ).scalars().all()
    bucket_map = {b.bucket_key: b for b in buckets}
    alert_ids = {b.alert_id for b in buckets}
    alerts = (
        await db.execute(select(Alert).where(Alert.alert_id.in_(alert_ids)))
    ).scalars().all() if alert_ids else []
    alert_map = {a.alert_id: a for a in alerts}

    decision_ids = [d.decision_id for d in decisions]
    calls = (
        await db.execute(
            select(ToolCall).where(ToolCall.decision_id.in_(decision_ids))
        )
    ).scalars().all()
    by_decision: dict[str, list[ToolCall]] = {}
    for c in calls:
        by_decision.setdefault(c.decision_id, []).append(c)

    out: list[dict[str, Any]] = []
    for d in decisions:
        bucket = bucket_map.get(d.bucket_key)
        alert = alert_map.get(bucket.alert_id) if bucket else None
        out.append(_decision_shape(d, alert, by_decision.get(d.decision_id, [])))
    return out


@router.get("/decisions/{decision_id}")
async def decision_detail(
    decision_id: str,
    _op: Annotated[dict[str, Any], Depends(current_operator)],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Full AgentDecision row for the reasoning drawer.

    Returns the standard list shape PLUS the full multi-turn `turns JSON`
    and each ToolCall's args (so the operator can audit what the agent
    looked at, what it considered, and what it called).
    """
    d = await db.get(AgentDecision, decision_id)
    if d is None:
        raise HTTPException(status_code=404, detail="decision not found")

    bucket = await db.get(Bucket, d.bucket_key)
    alert = await db.get(Alert, bucket.alert_id) if bucket else None

    calls = (
        await db.execute(
            select(ToolCall).where(ToolCall.decision_id == decision_id)
        )
    ).scalars().all()

    base = _decision_shape(d, alert, list(calls))
    base["turns"] = d.turns or []
    base["promptHash"] = d.prompt_hash
    # Replace the lean toolCalls with full args / approval state.
    base["toolCalls"] = [
        {
            "id": c.call_id,
            "name": c.tool_name,
            "mode": c.mode,
            "approvalStatus": c.approval_status,
            "args": c.args,
            "decidedBy": c.decided_by,
            "decidedAt": c.decided_at.isoformat() if c.decided_at else None,
            "createdAt": c.created_at.isoformat() if c.created_at else None,
        }
        for c in calls
    ]
    return base


@router.get("/agent/stats")
async def agent_stats(
    _op: Annotated[dict[str, Any], Depends(current_operator)],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Aggregates for the header pill."""
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    decisions_today = (
        await db.execute(
            select(func.count(AgentDecision.decision_id)).where(
                AgentDecision.created_at >= today_start
            )
        )
    ).scalar() or 0

    cost_today = (
        await db.execute(
            select(func.coalesce(func.sum(AgentDecision.cost_usd), 0.0)).where(
                AgentDecision.created_at >= today_start
            )
        )
    ).scalar() or 0.0

    pending = (
        await db.execute(
            select(func.count(ToolCall.call_id)).where(
                ToolCall.approval_status == "pending"
            )
        )
    ).scalar() or 0

    executed_today = (
        await db.execute(
            select(func.count(ToolCall.call_id)).where(
                ToolCall.approval_status == "auto_executed",
                ToolCall.created_at >= today_start,
            )
        )
    ).scalar() or 0

    last_decision = (
        await db.execute(
            select(AgentDecision)
            .order_by(AgentDecision.created_at.desc())
            .limit(1)
        )
    ).scalars().first()

    return {
        "decisionsToday": int(decisions_today),
        "costTodayUsd": round(float(cost_today), 4),
        "pending": int(pending),
        "executedToday": int(executed_today),
        "lastDecisionAt": (
            last_decision.created_at.isoformat()
            if last_decision and last_decision.created_at
            else None
        ),
    }
