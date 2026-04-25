"""Agent tool handlers — 12 action tools + 2 retrieval tools.

Per spec §5: action handlers stage `ToolCall` row buffers (the worker commits
them at the end of the multi-turn decision); retrieval handlers query the DB
directly and return rows.

The handlers share a per-decision scope via a ContextVar so they don't need
the SDK to thread state. The worker sets the scope before each `query()`
and unsets after.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from server.db.alerts import Alert
from server.db.decisions import AgentDecision, ToolCall
from server.db.identity import Account
from server.db.knowledge import SightingCluster, Tag, TagAssignment, Trajectory
from server.db.messages import InboundMessage, TriagedMessage
from server.db.outbound import Sighting
from server.db.trust import BadActor
from server.workers.agent_context import AgentContext

logger = logging.getLogger(__name__)


@dataclass
class StagedToolCall:
    tool_name: str
    args: dict
    idempotency_key: str
    mode: str
    approval_status: str


@dataclass
class DecisionScope:
    """Per-decision state shared across tool handlers."""

    ctx: AgentContext
    session_maker: async_sessionmaker
    staged: list[StagedToolCall] = field(default_factory=list)


# Module-level scope holder. The SDK's MCP server runs tool handlers in a
# task that doesn't share our ContextVar, so we use a plain global. Safe
# because each AgentWorker runs exactly one decision at a time (per-alert
# advisory lock + sequential drain in agent_worker_loop).
_current_scope: Optional[DecisionScope] = None


def set_scope(scope: DecisionScope) -> None:
    global _current_scope
    _current_scope = scope


def clear_scope() -> None:
    global _current_scope
    _current_scope = None


def _scope() -> DecisionScope:
    if _current_scope is None:
        raise RuntimeError("agent tool called outside a DecisionScope")
    return _current_scope


# ---------------------------------------------------------------------------
# Idempotency + mode helpers
# ---------------------------------------------------------------------------


def _canonical_json(args: dict) -> str:
    return json.dumps(args, sort_keys=True, separators=(",", ":"), default=str)


def idempotency_key(bucket_key: str, tool_name: str, args: dict) -> str:
    payload = f"{bucket_key}|{tool_name}|{_canonical_json(args)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _audience_size(audience: dict) -> int:
    t = audience.get("type")
    if t == "one":
        return 1
    if t == "many":
        return len(audience.get("phones") or [])
    if t == "region":
        return 50  # estimate; real dispatcher resolves
    if t == "all_alert":
        return 1000
    if t == "all_ngo":
        return 5000
    return 0


def _default_send_mode(audience: dict, backpressure: bool) -> str:
    """Pick mode for a `send` call per spec §5.4."""
    size = _audience_size(audience)
    t = audience.get("type")
    if t in ("all_alert", "all_ngo"):
        return "suggest"
    if size >= 100:
        return "suggest"
    if backpressure and size > 10:
        return "suggest"
    return "execute"


# ---------------------------------------------------------------------------
# Staging
# ---------------------------------------------------------------------------


def _stage(tool_name: str, args: dict, mode: str) -> StagedToolCall:
    scope = _scope()
    key = idempotency_key(scope.ctx.bucket.bucket_key, tool_name, args)
    for prior in scope.staged:
        if prior.idempotency_key == key:
            return prior
    approval_status = "auto_executed" if mode == "execute" else "pending"
    staged = StagedToolCall(
        tool_name=tool_name,
        args=args,
        idempotency_key=key,
        mode=mode,
        approval_status=approval_status,
    )
    scope.staged.append(staged)
    return staged


def _ok(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


# ---------------------------------------------------------------------------
# Action handlers (12)
# ---------------------------------------------------------------------------


async def _send(args: dict) -> dict:
    audience = args.get("audience") or {}
    bodies = args.get("bodies") or {}
    if not bodies:
        return _ok("error: bodies map required")
    mode = args.get("mode") or _default_send_mode(audience, _scope().ctx.backpressure())
    staged = _stage("send", {"audience": audience, "bodies": bodies, "mode": mode}, mode)
    return _ok(f"send queued mode={mode} key={staged.idempotency_key[:8]} size={_audience_size(audience)}")


async def _record_sighting(args: dict) -> dict:
    needed = ("alert_id", "observer_phone", "geohash", "notes", "confidence")
    if not all(args.get(k) is not None for k in needed):
        return _ok(f"error: required fields {needed}")
    staged = _stage("record_sighting", args, mode="execute")
    return _ok(f"sighting queued key={staged.idempotency_key[:8]}")


async def _upsert_cluster(args: dict) -> dict:
    if not args.get("alert_id") or not args.get("label"):
        return _ok("error: alert_id and label required")
    staged = _stage("upsert_cluster", args, mode="execute")
    return _ok(f"cluster queued key={staged.idempotency_key[:8]}")


async def _merge_clusters(args: dict) -> dict:
    if not args.get("source_cluster_ids") or not args.get("target_cluster_id"):
        return _ok("error: source_cluster_ids and target_cluster_id required")
    staged = _stage("merge_clusters", args, mode="execute")
    return _ok(f"merge queued key={staged.idempotency_key[:8]}")


async def _upsert_trajectory(args: dict) -> dict:
    if not args.get("alert_id") or not args.get("points"):
        return _ok("error: alert_id and points required")
    staged = _stage("upsert_trajectory", args, mode="execute")
    return _ok(f"trajectory queued key={staged.idempotency_key[:8]}")


async def _apply_tag(args: dict) -> dict:
    needed = ("entity_type", "entity_id", "tag_name")
    if not all(args.get(k) for k in needed):
        return _ok(f"error: required fields {needed}")
    staged = _stage("apply_tag", args, mode="execute")
    return _ok(f"tag queued key={staged.idempotency_key[:8]}")


async def _remove_tag(args: dict) -> dict:
    needed = ("entity_type", "entity_id", "tag_name")
    if not all(args.get(k) for k in needed):
        return _ok(f"error: required fields {needed}")
    staged = _stage("remove_tag", args, mode="execute")
    return _ok(f"untag queued key={staged.idempotency_key[:8]}")


async def _categorize_alert(args: dict) -> dict:
    needed = ("alert_id", "category", "urgency_tier", "urgency_score")
    if not all(args.get(k) is not None for k in needed):
        return _ok(f"error: required fields {needed}")
    staged = _stage("categorize_alert", args, mode="suggest")
    return _ok(f"categorize queued (suggest) key={staged.idempotency_key[:8]}")


async def _escalate_to_ngo(args: dict) -> dict:
    if not args.get("reason") or not args.get("summary"):
        return _ok("error: reason and summary required")
    staged = _stage("escalate_to_ngo", args, mode="execute")
    return _ok(f"escalation queued key={staged.idempotency_key[:8]}")


async def _mark_bad_actor(args: dict) -> dict:
    if not args.get("phone") or not args.get("reason"):
        return _ok("error: phone and reason required")
    staged = _stage("mark_bad_actor", args, mode="suggest")
    return _ok(f"bad_actor queued (suggest) key={staged.idempotency_key[:8]}")


async def _update_alert_status(args: dict) -> dict:
    if not args.get("alert_id") or not args.get("status"):
        return _ok("error: alert_id and status required")
    staged = _stage("update_alert_status", args, mode="suggest")
    return _ok(f"status_change queued (suggest) key={staged.idempotency_key[:8]}")


async def _noop(args: dict) -> dict:
    reason = args.get("reason") or "no action"
    staged = _stage("noop", {"reason": reason}, mode="execute")
    return _ok(f"noop recorded: {reason} key={staged.idempotency_key[:8]}")


# ---------------------------------------------------------------------------
# Retrieval handlers (2) — query DB live, no staging
# ---------------------------------------------------------------------------


async def _search(args: dict) -> dict:
    entity = args.get("entity")
    filters = args.get("filters") or {}
    sort = args.get("sort") or "recency"
    top_k = min(int(args.get("top_k") or 10), 50)
    scope = _scope()

    async with scope.session_maker() as s:
        if entity == "message":
            q = select(TriagedMessage)
            if filters.get("alert_id"):
                q = q.where(
                    TriagedMessage.bucket_key.like(f"{filters['alert_id']}|%")
                )
            if filters.get("classification"):
                q = q.where(TriagedMessage.classification == filters["classification"])
            if filters.get("language"):
                q = q.where(TriagedMessage.language == filters["language"])
            if filters.get("min_confidence") is not None:
                q = q.where(TriagedMessage.confidence >= float(filters["min_confidence"]))
            if filters.get("geohash_prefix"):
                q = q.where(TriagedMessage.geohash6.like(f"{filters['geohash_prefix']}%"))
            q = q.order_by(TriagedMessage.created_at.desc()).limit(top_k)
            rows = (await s.execute(q)).scalars().all()
            out = [
                {
                    "msg_id": r.msg_id,
                    "classification": r.classification,
                    "geohash6": r.geohash6,
                    "confidence": r.confidence,
                    "language": r.language,
                }
                for r in rows
            ]
        elif entity == "sighting":
            q = select(Sighting)
            if filters.get("alert_id"):
                q = q.where(Sighting.alert_id == filters["alert_id"])
            if filters.get("observer_phone"):
                q = q.where(Sighting.observer_phone == filters["observer_phone"])
            if filters.get("geohash_prefix"):
                q = q.where(Sighting.geohash.like(f"{filters['geohash_prefix']}%"))
            if filters.get("min_confidence") is not None:
                q = q.where(Sighting.confidence >= float(filters["min_confidence"]))
            q = q.order_by(Sighting.recorded_at.desc()).limit(top_k)
            rows = (await s.execute(q)).scalars().all()
            out = [
                {
                    "sighting_id": r.sighting_id,
                    "geohash": r.geohash,
                    "notes": r.notes,
                    "confidence": r.confidence,
                }
                for r in rows
            ]
        elif entity == "decision":
            q = select(AgentDecision)
            if filters.get("alert_id"):
                # join via Bucket
                from server.db.messages import Bucket as _B

                q = q.join(_B, AgentDecision.bucket_key == _B.bucket_key).where(
                    _B.alert_id == filters["alert_id"]
                )
            q = q.order_by(AgentDecision.created_at.desc()).limit(top_k)
            rows = (await s.execute(q)).scalars().all()
            out = [
                {
                    "decision_id": r.decision_id,
                    "model": r.model,
                    "summary": r.reasoning_summary,
                }
                for r in rows
            ]
        elif entity == "cluster":
            q = select(SightingCluster)
            if filters.get("alert_id"):
                q = q.where(SightingCluster.alert_id == filters["alert_id"])
            if filters.get("status"):
                q = q.where(SightingCluster.status == filters["status"])
            else:
                q = q.where(SightingCluster.status == "active")
            if filters.get("min_size") is not None:
                q = q.where(SightingCluster.sighting_count >= int(filters["min_size"]))
            q = q.order_by(SightingCluster.updated_at.desc()).limit(top_k)
            rows = (await s.execute(q)).scalars().all()
            out = [
                {
                    "cluster_id": r.cluster_id,
                    "label": r.label,
                    "center_geohash": r.center_geohash,
                    "size": r.sighting_count,
                }
                for r in rows
            ]
        elif entity == "trajectory":
            q = select(Trajectory)
            if filters.get("alert_id"):
                q = q.where(Trajectory.alert_id == filters["alert_id"])
            if filters.get("status"):
                q = q.where(Trajectory.status == filters["status"])
            q = q.order_by(Trajectory.created_at.desc()).limit(top_k)
            rows = (await s.execute(q)).scalars().all()
            out = [
                {
                    "trajectory_id": r.trajectory_id,
                    "direction_deg": r.direction_deg,
                    "speed_kmh": r.speed_kmh,
                    "confidence": r.confidence,
                    "status": r.status,
                }
                for r in rows
            ]
        elif entity == "tag_assignment":
            q = select(TagAssignment)
            if filters.get("alert_id"):
                q = q.where(TagAssignment.alert_id == filters["alert_id"])
            if filters.get("entity_type"):
                q = q.where(TagAssignment.entity_type == filters["entity_type"])
            if filters.get("applied_by"):
                q = q.where(TagAssignment.applied_by == filters["applied_by"])
            q = q.order_by(TagAssignment.created_at.desc()).limit(top_k)
            rows = (await s.execute(q)).scalars().all()
            out = [
                {
                    "assignment_id": r.assignment_id,
                    "tag_id": r.tag_id,
                    "entity_type": r.entity_type,
                    "entity_id": r.entity_id,
                    "applied_by": r.applied_by,
                }
                for r in rows
            ]
        else:
            return _ok(f"error: unknown entity '{entity}'")

    return _ok(json.dumps({"results": out, "count": len(out)}))


async def _get(args: dict) -> dict:
    entity = args.get("entity")
    eid = args.get("id")
    if not entity or not eid:
        return _ok("error: entity and id required")
    scope = _scope()
    async with scope.session_maker() as s:
        if entity == "message":
            row = await s.get(TriagedMessage, eid)
            if row is None:
                return _ok("not found")
            inbound = await s.get(InboundMessage, eid)
            return _ok(
                json.dumps(
                    {
                        "msg_id": row.msg_id,
                        "classification": row.classification,
                        "geohash6": row.geohash6,
                        "confidence": row.confidence,
                        "language": row.language,
                        "body": inbound.body if inbound else None,
                        "sender_phone": inbound.sender_phone if inbound else None,
                    }
                )
            )
        if entity == "sighting":
            row = await s.get(Sighting, eid)
            if row is None:
                return _ok("not found")
            return _ok(
                json.dumps(
                    {
                        "sighting_id": row.sighting_id,
                        "alert_id": row.alert_id,
                        "observer_phone": row.observer_phone,
                        "geohash": row.geohash,
                        "notes": row.notes,
                        "confidence": row.confidence,
                        "photo_urls": row.photo_urls,
                    }
                )
            )
        if entity == "decision":
            row = await s.get(AgentDecision, eid)
            if row is None:
                return _ok("not found")
            return _ok(
                json.dumps(
                    {
                        "decision_id": row.decision_id,
                        "model": row.model,
                        "summary": row.reasoning_summary,
                        "tool_calls": row.tool_calls,
                        "total_turns": row.total_turns,
                    }
                )
            )
        if entity == "alert":
            row = await s.get(Alert, eid)
            if row is None:
                return _ok("not found")
            return _ok(
                json.dumps(
                    {
                        "alert_id": row.alert_id,
                        "person_name": row.person_name,
                        "description": row.description,
                        "status": row.status,
                        "category": row.category,
                        "urgency_tier": row.urgency_tier,
                    }
                )
            )
        if entity == "account":
            row = await s.get(Account, eid)
            if row is None:
                return _ok("not found")
            return _ok(
                json.dumps(
                    {
                        "phone": row.phone,
                        "language": row.language,
                        "trust_score": row.trust_score,
                        "opted_out": row.opted_out,
                    }
                )
            )
        if entity == "cluster":
            row = await s.get(SightingCluster, eid)
            if row is None:
                return _ok("not found")
            return _ok(
                json.dumps(
                    {
                        "cluster_id": row.cluster_id,
                        "label": row.label,
                        "center_geohash": row.center_geohash,
                        "radius_m": row.radius_m,
                        "sighting_ids": row.sighting_ids,
                        "status": row.status,
                    }
                )
            )
        if entity == "trajectory":
            row = await s.get(Trajectory, eid)
            if row is None:
                return _ok("not found")
            return _ok(
                json.dumps(
                    {
                        "trajectory_id": row.trajectory_id,
                        "points": row.points,
                        "direction_deg": row.direction_deg,
                        "speed_kmh": row.speed_kmh,
                        "confidence": row.confidence,
                        "status": row.status,
                    }
                )
            )
        return _ok(f"error: unknown entity '{entity}'")


# ---------------------------------------------------------------------------
# Tool registry — mapping name → handler. Used both by the SDK MCP server
# and by the stub agent.
# ---------------------------------------------------------------------------


HANDLERS: dict[str, Any] = {
    "send": _send,
    "record_sighting": _record_sighting,
    "upsert_cluster": _upsert_cluster,
    "merge_clusters": _merge_clusters,
    "upsert_trajectory": _upsert_trajectory,
    "apply_tag": _apply_tag,
    "remove_tag": _remove_tag,
    "categorize_alert": _categorize_alert,
    "escalate_to_ngo": _escalate_to_ngo,
    "mark_bad_actor": _mark_bad_actor,
    "update_alert_status": _update_alert_status,
    "noop": _noop,
    "search": _search,
    "get": _get,
}


# ---------------------------------------------------------------------------
# Persistence: turn staged ToolCalls into rows, plus apply side-effects
# for execute-mode tools that have direct DB writes (record_sighting,
# upsert_cluster, etc.).
#
# §4.4 says the Outbound Dispatcher claims tool_call rows and applies
# side-effects. For internal tools (record_sighting, upsert_cluster,
# upsert_trajectory, apply_tag, remove_tag, categorize_alert,
# update_alert_status, mark_bad_actor) the dispatcher just inserts/updates
# DB rows. We materialize those side-effects inline at persistence time
# for `mode='execute'` so the demo's UI sees clusters/sightings/etc.
# without needing a full dispatcher pass.
# ---------------------------------------------------------------------------


async def apply_side_effects(staged: StagedToolCall, ngo_id: str, session) -> None:
    """Apply DB side-effects for internal-only execute-mode tool calls."""
    if staged.approval_status != "auto_executed":
        return
    name = staged.tool_name
    args = staged.args

    if name == "record_sighting":
        s = Sighting(
            ngo_id=ngo_id,
            alert_id=args["alert_id"],
            observer_phone=args["observer_phone"],
            geohash=args["geohash"],
            notes=args.get("notes") or "",
            confidence=float(args.get("confidence") or 0.5),
            photo_urls=args.get("photo_urls") or [],
        )
        session.add(s)

    elif name == "upsert_cluster":
        cid = args.get("cluster_id")
        if cid:
            row = await session.get(SightingCluster, cid)
        else:
            row = None
        sighting_ids = args.get("sighting_ids") or []
        now = datetime.now(UTC)
        if row is None:
            row = SightingCluster(
                ngo_id=ngo_id,
                alert_id=args["alert_id"],
                label=args["label"],
                center_geohash=args.get("center_geohash") or "",
                radius_m=int(args.get("radius_m") or 0),
                sighting_ids=sighting_ids,
                sighting_count=len(sighting_ids),
                status="active",
                last_member_added_at=now,
            )
            session.add(row)
        else:
            row.label = args.get("label") or row.label
            existing = set(row.sighting_ids or [])
            existing.update(sighting_ids)
            row.sighting_ids = list(existing)
            row.sighting_count = len(existing)
            row.last_member_added_at = now

    elif name == "merge_clusters":
        target_id = args["target_cluster_id"]
        target = await session.get(SightingCluster, target_id)
        if target:
            merged_ids: set[str] = set(target.sighting_ids or [])
            for src_id in args.get("source_cluster_ids") or []:
                src = await session.get(SightingCluster, src_id)
                if src:
                    merged_ids.update(src.sighting_ids or [])
                    src.status = "merged"
                    src.merged_into = target_id
            target.sighting_ids = list(merged_ids)
            target.sighting_count = len(merged_ids)

    elif name == "upsert_trajectory":
        tid = args.get("trajectory_id")
        row = await session.get(Trajectory, tid) if tid else None
        if row is None:
            row = Trajectory(
                ngo_id=ngo_id,
                alert_id=args["alert_id"],
                points=args.get("points") or [],
                direction_deg=args.get("direction_deg"),
                speed_kmh=args.get("speed_kmh"),
                confidence=float(args.get("confidence") or 0.5),
                status="active",
                last_extended_at=datetime.now(UTC),
            )
            session.add(row)
        else:
            row.points = args.get("points") or row.points
            if args.get("direction_deg") is not None:
                row.direction_deg = args["direction_deg"]
            if args.get("speed_kmh") is not None:
                row.speed_kmh = args["speed_kmh"]
            if args.get("confidence") is not None:
                row.confidence = float(args["confidence"])
            row.last_extended_at = datetime.now(UTC)

    elif name == "apply_tag":
        ns = args.get("namespace") or "default"
        # Lookup or create Tag
        existing = (
            await session.execute(
                select(Tag).where(
                    Tag.ngo_id == ngo_id,
                    Tag.namespace == ns,
                    Tag.name == args["tag_name"],
                )
            )
        ).scalars().first()
        if existing is None:
            existing = Tag(
                ngo_id=ngo_id,
                namespace=ns,
                name=args["tag_name"],
                created_by="agent",
            )
            session.add(existing)
            await session.flush()
        # Idempotent insert
        prior = (
            await session.execute(
                select(TagAssignment).where(
                    TagAssignment.tag_id == existing.tag_id,
                    TagAssignment.entity_type == args["entity_type"],
                    TagAssignment.entity_id == args["entity_id"],
                )
            )
        ).scalars().first()
        if prior is None:
            ta = TagAssignment(
                ngo_id=ngo_id,
                tag_id=existing.tag_id,
                entity_type=args["entity_type"],
                entity_id=args["entity_id"],
                confidence=args.get("confidence"),
                applied_by="agent",
                alert_id=args.get("alert_id"),
            )
            session.add(ta)

    elif name == "remove_tag":
        ns = args.get("namespace") or "default"
        existing = (
            await session.execute(
                select(Tag).where(
                    Tag.ngo_id == ngo_id,
                    Tag.namespace == ns,
                    Tag.name == args["tag_name"],
                )
            )
        ).scalars().first()
        if existing is not None:
            ta = (
                await session.execute(
                    select(TagAssignment).where(
                        TagAssignment.tag_id == existing.tag_id,
                        TagAssignment.entity_type == args["entity_type"],
                        TagAssignment.entity_id == args["entity_id"],
                    )
                )
            ).scalars().first()
            if ta is not None:
                await session.delete(ta)

    elif name == "categorize_alert":
        # Default mode is 'suggest', so this only fires if explicitly executed.
        alert = await session.get(Alert, args["alert_id"])
        if alert:
            alert.category = args.get("category")
            alert.urgency_tier = args.get("urgency_tier")
            if args.get("urgency_score") is not None:
                alert.urgency_score = float(args["urgency_score"])

    elif name == "update_alert_status":
        alert = await session.get(Alert, args["alert_id"])
        if alert:
            alert.status = args["status"]

    elif name == "mark_bad_actor":
        existing = await session.get(BadActor, args["phone"])
        if existing is None:
            ba = BadActor(
                phone=args["phone"],
                ngo_id=ngo_id,
                reason=args.get("reason") or "",
                marked_by="agent",
            )
            session.add(ba)

    # `send`, `escalate_to_ngo`, `noop` have no inline side-effects; they
    # become rows for the dispatcher (or audit-only) to handle.
