"""Context loading for the Agent Worker.

Per spec §4.3: before each multi-turn loop, the agent reads a rich snapshot
of the bucket and its surrounding case file. We materialize that into a
single dataclass via parallel queries.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from server.db.alerts import Alert
from server.db.decisions import AgentDecision, ToolCall
from server.db.identity import NGO, Account
from server.db.knowledge import SightingCluster, TagAssignment, Trajectory
from server.db.messages import Bucket, InboundMessage, TriagedMessage
from server.db.outbound import Sighting


@dataclass
class AgentContext:
    bucket: Bucket
    alert: Optional[Alert]
    ngo: Optional[NGO]
    triaged: list[TriagedMessage] = field(default_factory=list)
    inbound_by_msg_id: dict[str, InboundMessage] = field(default_factory=dict)
    accounts_by_phone: dict[str, Account] = field(default_factory=dict)
    recent_decisions: list[AgentDecision] = field(default_factory=list)
    recent_sightings: list[Sighting] = field(default_factory=list)
    active_clusters: list[SightingCluster] = field(default_factory=list)
    latest_trajectory: Optional[Trajectory] = None
    recent_tag_assignments: list[TagAssignment] = field(default_factory=list)
    dispatch_backlog: int = 0
    pending_suggestions: int = 0

    def is_heartbeat(self) -> bool:
        return self.bucket.bucket_key.startswith("heartbeat:")

    def backpressure(self) -> bool:
        return self.dispatch_backlog > 200 or self.pending_suggestions > 50


async def _load_triaged(session: AsyncSession, bucket_key: str) -> list[TriagedMessage]:
    rows = (
        await session.execute(
            select(TriagedMessage).where(TriagedMessage.bucket_key == bucket_key)
        )
    ).scalars().all()
    return list(rows)


async def _load_inbound_for_msg_ids(
    session: AsyncSession, msg_ids: list[str]
) -> dict[str, InboundMessage]:
    if not msg_ids:
        return {}
    rows = (
        await session.execute(
            select(InboundMessage).where(InboundMessage.msg_id.in_(msg_ids))
        )
    ).scalars().all()
    return {row.msg_id: row for row in rows}


async def _load_accounts(
    session: AsyncSession, phones: set[str]
) -> dict[str, Account]:
    if not phones:
        return {}
    rows = (
        await session.execute(select(Account).where(Account.phone.in_(phones)))
    ).scalars().all()
    return {row.phone: row for row in rows}


async def _load_recent_decisions(
    session: AsyncSession, alert_id: str, limit: int = 10
) -> list[AgentDecision]:
    rows = (
        await session.execute(
            select(AgentDecision)
            .join(Bucket, AgentDecision.bucket_key == Bucket.bucket_key)
            .where(Bucket.alert_id == alert_id)
            .order_by(AgentDecision.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return list(rows)


async def _load_recent_sightings(
    session: AsyncSession, alert_id: str, limit: int = 20
) -> list[Sighting]:
    rows = (
        await session.execute(
            select(Sighting)
            .where(Sighting.alert_id == alert_id)
            .order_by(Sighting.recorded_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return list(rows)


async def _load_active_clusters(
    session: AsyncSession, alert_id: str, limit: int = 10
) -> list[SightingCluster]:
    rows = (
        await session.execute(
            select(SightingCluster)
            .where(SightingCluster.alert_id == alert_id)
            .where(SightingCluster.status == "active")
            .order_by(SightingCluster.updated_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return list(rows)


async def _load_latest_trajectory(
    session: AsyncSession, alert_id: str
) -> Optional[Trajectory]:
    rows = (
        await session.execute(
            select(Trajectory)
            .where(Trajectory.alert_id == alert_id)
            .order_by(Trajectory.created_at.desc())
            .limit(1)
        )
    ).scalars().all()
    return rows[0] if rows else None


async def _load_recent_tag_assignments(
    session: AsyncSession, alert_id: str, limit: int = 30
) -> list[TagAssignment]:
    rows = (
        await session.execute(
            select(TagAssignment)
            .where(TagAssignment.alert_id == alert_id)
            .order_by(TagAssignment.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return list(rows)


async def _count_dispatch_backlog(session: AsyncSession) -> int:
    rows = (
        await session.execute(
            select(ToolCall).where(
                ToolCall.status == "pending",
                ToolCall.approval_status.in_(("auto_executed", "approved")),
            )
        )
    ).scalars().all()
    return len(rows)


async def _count_pending_suggestions(session: AsyncSession) -> int:
    rows = (
        await session.execute(
            select(ToolCall).where(
                ToolCall.status == "pending",
                ToolCall.approval_status == "pending",
            )
        )
    ).scalars().all()
    return len(rows)


async def load_context(
    session_maker: async_sessionmaker, bucket: Bucket
) -> AgentContext:
    """Load full agent context for a claimed bucket via parallel queries."""
    async with session_maker() as session:
        alert: Optional[Alert] = await session.get(Alert, bucket.alert_id)
        ngo: Optional[NGO] = await session.get(NGO, bucket.ngo_id)
        triaged = await _load_triaged(session, bucket.bucket_key)

        msg_ids = [t.msg_id for t in triaged]
        inbound_map = await _load_inbound_for_msg_ids(session, msg_ids)
        phones = {m.sender_phone for m in inbound_map.values() if m.sender_phone}

        (
            accounts_map,
            decisions,
            sightings,
            clusters,
            trajectory,
            tag_assigns,
            dispatch_backlog,
            pending_suggestions,
        ) = await asyncio.gather(
            _load_accounts(session, phones),
            _load_recent_decisions(session, bucket.alert_id),
            _load_recent_sightings(session, bucket.alert_id),
            _load_active_clusters(session, bucket.alert_id),
            _load_latest_trajectory(session, bucket.alert_id),
            _load_recent_tag_assignments(session, bucket.alert_id),
            _count_dispatch_backlog(session),
            _count_pending_suggestions(session),
        )

    return AgentContext(
        bucket=bucket,
        alert=alert,
        ngo=ngo,
        triaged=triaged,
        inbound_by_msg_id=inbound_map,
        accounts_by_phone=accounts_map,
        recent_decisions=decisions,
        recent_sightings=sightings,
        active_clusters=clusters,
        latest_trajectory=trajectory,
        recent_tag_assignments=tag_assigns,
        dispatch_backlog=dispatch_backlog,
        pending_suggestions=pending_suggestions,
    )


def render_prompt(ctx: AgentContext) -> str:
    """Render initial user prompt content for the multi-turn loop.

    Real-LLM mode uses this. Stub mode also computes it (for test parity)
    but ignores it.
    """
    parts: list[str] = []
    parts.append(f"# Bucket: {ctx.bucket.bucket_key}")
    if ctx.is_heartbeat():
        parts.append("Mode: HEARTBEAT (consolidation only — no new inbound)")
    if ctx.alert:
        parts.append(
            f"# Alert: {ctx.alert.person_name} (id={ctx.alert.alert_id}, "
            f"status={ctx.alert.status}, category={ctx.alert.category}, "
            f"urgency_tier={ctx.alert.urgency_tier})"
        )
        if ctx.alert.description:
            parts.append(f"Description: {ctx.alert.description}")
    if ctx.ngo and ctx.ngo.standing_orders:
        parts.append(f"# NGO standing orders\n{ctx.ngo.standing_orders}")
    if ctx.backpressure():
        parts.append(
            "# Backpressure\nDispatch / suggestions backlog is high. "
            "Prefer mode='suggest' over 'execute' and prefer escalate_to_ngo."
        )

    parts.append(f"# Triaged messages in bucket ({len(ctx.triaged)})")
    for t in ctx.triaged:
        inbound = ctx.inbound_by_msg_id.get(t.msg_id)
        body = (inbound.body[:300] if inbound else "<missing>")
        sender = inbound.sender_phone if inbound else "?"
        parts.append(
            f"- msg_id={t.msg_id} sender={sender} class={t.classification} "
            f"conf={t.confidence:.2f} geohash={t.geohash6}\n  body: {body}"
        )

    parts.append(f"# Recent sightings ({len(ctx.recent_sightings)})")
    for s in ctx.recent_sightings[:10]:
        parts.append(
            f"- {s.sighting_id} @ {s.geohash} conf={s.confidence:.2f}: {s.notes[:120]}"
        )

    parts.append(f"# Active clusters ({len(ctx.active_clusters)})")
    for c in ctx.active_clusters:
        parts.append(
            f"- {c.cluster_id} {c.label} center={c.center_geohash} "
            f"r={c.radius_m}m size={c.sighting_count}"
        )

    if ctx.latest_trajectory:
        tr = ctx.latest_trajectory
        parts.append(
            f"# Latest trajectory: {tr.trajectory_id} "
            f"dir={tr.direction_deg} speed={tr.speed_kmh}kmh conf={tr.confidence}"
        )

    parts.append(f"# Recent decisions ({len(ctx.recent_decisions)})")
    for d in ctx.recent_decisions[:5]:
        parts.append(f"- {d.decision_id}: {d.reasoning_summary or '(no summary)'}")

    parts.append(
        "# Decide now\n"
        "Use retrieval tools (search/get) only if necessary. Then emit one or "
        "more action tool calls. Each action carries a `mode`: 'execute' (auto) "
        "or 'suggest' (operator approves). Defaults from §5.4: small audiences "
        "execute, large broadcasts suggest. Use noop with a reason if nothing "
        "should happen."
    )
    return "\n\n".join(parts)
