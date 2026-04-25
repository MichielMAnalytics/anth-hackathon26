"""Agent Worker — the main decision loop.

Per spec §4.3: subscribe to `bucket_open`, drain the queue. For each event:
  1. Claim the bucket (FOR UPDATE SKIP LOCKED) and acquire a per-alert
     advisory lock to serialize decisions per alert.
  2. Load context (parallel queries via load_context).
  3. Run the decision (stub if no API key, else ClaudeSDKClient).
  4. Persist AgentDecision + ToolCall rows; apply inline side-effects for
     execute-mode internal tools.
  5. Emit `toolcalls_pending` / `suggestions_pending` notifications.
  6. Mark bucket done; release advisory lock.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import hashlib

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from server.db.buckets import (
    claim_open_bucket,
    fail_bucket,
    mark_bucket_done,
    release_advisory_lock,
    release_bucket,
    try_advisory_lock,
)
from server.db.decisions import AgentDecision, ToolCall
from server.db.messages import Bucket
from server.eventbus.postgres import PostgresEventBus
from server.llm.agent_client import (
    have_real_key,
    make_agent_options,
    real_decide,
    stub_decide,
)
from server.workers.agent_context import load_context
from server.workers.agent_tools import (
    DecisionScope,
    apply_side_effects,
)

logger = logging.getLogger(__name__)
WORKER_ID = "agent-worker-1"


async def _process_bucket(
    bucket: Bucket,
    session_maker: async_sessionmaker,
    eventbus: PostgresEventBus,
    sdk_client: Any,
) -> None:
    """Run a single agent decision for one claimed bucket."""
    ctx = await load_context(session_maker, bucket)
    scope = DecisionScope(ctx=ctx, session_maker=session_maker)

    if sdk_client is not None:
        decision_meta = await real_decide(ctx, scope, sdk_client)
    else:
        decision_meta = await stub_decide(ctx, scope)

    await _persist_decision(scope, decision_meta, session_maker)

    has_execute = any(s.approval_status == "auto_executed" for s in scope.staged)
    has_suggest = any(s.approval_status == "pending" for s in scope.staged)
    if has_execute:
        await eventbus.publish("toolcalls_pending", bucket.bucket_key)
    if has_suggest:
        await eventbus.publish("suggestions_pending", bucket.bucket_key)


async def _persist_decision(
    scope: DecisionScope,
    decision_meta: dict,
    session_maker: async_sessionmaker,
) -> None:
    """Write AgentDecision + ToolCall rows; apply execute-mode side-effects."""
    async with session_maker() as session:
        decision = AgentDecision(
            ngo_id=scope.ctx.bucket.ngo_id,
            bucket_key=scope.ctx.bucket.bucket_key,
            model=decision_meta.get("model") or "stub",
            prompt_hash=hashlib.sha256(
                scope.ctx.bucket.bucket_key.encode("utf-8")
            ).hexdigest(),
            reasoning_summary=decision_meta.get("reasoning_summary"),
            tool_calls=[
                {"name": s.tool_name, "args": s.args, "mode": s.mode}
                for s in scope.staged
            ],
            turns=decision_meta.get("turns") or [],
            total_turns=int(decision_meta.get("total_turns") or 0),
            latency_ms=int(decision_meta.get("latency_ms") or 0),
            cost_usd=float(decision_meta.get("cost_usd") or 0.0),
        )
        session.add(decision)
        try:
            await session.flush()
        except IntegrityError:
            # UNIQUE(bucket_key) — replay of this same bucket; bail.
            await session.rollback()
            return

        for staged in scope.staged:
            tc = ToolCall(
                ngo_id=scope.ctx.bucket.ngo_id,
                decision_id=decision.decision_id,
                tool_name=staged.tool_name,
                args=staged.args,
                idempotency_key=staged.idempotency_key,
                mode=staged.mode,
                approval_status=staged.approval_status,
                status="pending",
            )
            session.add(tc)
            try:
                await session.flush()
            except IntegrityError:
                # UNIQUE(idempotency_key) — duplicate from a prior decision.
                await session.rollback()
                continue
            await apply_side_effects(staged, scope.ctx.bucket.ngo_id, session)

        await session.commit()


async def agent_worker_loop(
    eventbus: PostgresEventBus,
    session_maker: async_sessionmaker,
) -> None:
    """Long-running coroutine: drain bucket_open events.

    Real-mode lazy-imports ClaudeSDKClient so stub-mode tests don't pay
    the SDK startup cost.
    """
    sdk_client = None
    if have_real_key():
        try:
            from claude_agent_sdk import ClaudeSDKClient

            sdk_client = ClaudeSDKClient(options=make_agent_options())
            await sdk_client.connect()
            logger.info("agent: ClaudeSDKClient connected (real mode)")
        except Exception as exc:  # noqa: BLE001
            logger.exception("agent: SDK client init failed; falling back to stub: %s", exc)
            sdk_client = None
    else:
        logger.info("agent: no ANTHROPIC_API_KEY → stub mode")

    try:
        async for _payload in eventbus.subscribe("bucket_open"):
            # Drain all open buckets each notification (multiple buckets may
            # race). This also catches buckets created between notifications.
            while True:
                async with session_maker() as session:
                    bucket = await claim_open_bucket(session, WORKER_ID)
                if bucket is None:
                    break
                await _handle_one_bucket(bucket, session_maker, eventbus, sdk_client)
    except asyncio.CancelledError:
        if sdk_client is not None:
            try:
                await sdk_client.disconnect()
            except Exception:  # noqa: BLE001
                pass
        raise


async def _handle_one_bucket(
    bucket: Bucket,
    session_maker: async_sessionmaker,
    eventbus: PostgresEventBus,
    sdk_client: Any,
) -> None:
    """Acquire advisory lock, process, release. On error: release bucket
    back to 'open' or mark 'failed' after retries."""
    # Advisory lock must be on a separate connection that lives for the
    # decision; we use a dedicated session.
    lock_session = session_maker()
    got_lock = False
    try:
        got_lock = await try_advisory_lock(lock_session, bucket.alert_id)
        if not got_lock:
            # Another worker is in flight for this alert — release back.
            async with session_maker() as s:
                await release_bucket(s, bucket.bucket_key)
            return

        try:
            await _process_bucket(bucket, session_maker, eventbus, sdk_client)
            async with session_maker() as s:
                await mark_bucket_done(s, bucket.bucket_key)
        except Exception as exc:  # noqa: BLE001
            logger.exception("agent: bucket %s failed: %s", bucket.bucket_key, exc)
            async with session_maker() as s:
                fresh = await s.get(Bucket, bucket.bucket_key)
                if fresh is None:
                    return
                if (fresh.retry_count or 0) >= 3:
                    await fail_bucket(s, bucket.bucket_key)
                else:
                    await release_bucket(s, bucket.bucket_key)
    finally:
        if got_lock:
            try:
                await release_advisory_lock(lock_session, bucket.alert_id)
            except Exception:  # noqa: BLE001
                pass
        await lock_session.close()
