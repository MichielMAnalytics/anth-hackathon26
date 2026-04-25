"""Agent Worker LLM client.

Two paths:
- **Stub** (`ANTHROPIC_API_KEY` unset): synthesize a deterministic decision
  by walking the loaded `AgentContext` and emitting the obvious tool calls.
  Lets the full pipeline run end-to-end without network.
- **Real** (`ANTHROPIC_API_KEY` set): a `ClaudeSDKClient` configured with
  the 14 custom tools as an in-process MCP server. Multi-turn loop drains
  to a `ResultMessage`. Persistence happens in the worker.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from server.workers.agent_context import AgentContext, render_prompt
from server.workers.agent_tools import (
    DecisionScope,
    HANDLERS,
    StagedToolCall,
    _audience_size,
    _default_send_mode,
    clear_scope,
    set_scope,
)

logger = logging.getLogger(__name__)


AGENT_SYSTEM_PROMPT = """\
You are the matching-engine agent for an NGO running an amber-alert (missing
person) network. A bucket of triaged civilian messages has been delivered to
you. You must decide what to do.

You have 14 tools:
- 12 ACTION tools (record_sighting, send, upsert_cluster, merge_clusters,
  upsert_trajectory, apply_tag, remove_tag, categorize_alert,
  escalate_to_ngo, mark_bad_actor, update_alert_status, noop) — each emits a
  ToolCall row. Every action carries a `mode`: 'execute' (auto-runs) or
  'suggest' (operator approves).
- 2 RETRIEVAL tools (search, get) — read-only, free to call within the
  turn cap.

Defaults from policy:
- send to one or 2-10 recipients: mode='execute'
- send to 100+ or all_alert/all_ngo: mode='suggest'
- categorize_alert / update_alert_status / mark_bad_actor: mode='suggest'

Backpressure flag in the prompt → tilt toward suggest and escalate_to_ngo.

End every decision with at least one action tool call (or noop). Do not
emit free text after action calls.
"""


# ---------------------------------------------------------------------------
# Real-mode SDK options builder.
# ---------------------------------------------------------------------------


def _build_sdk_tools() -> list:
    """Wrap the 14 HANDLERS with the SDK's @tool decorator.

    Each tool gets an explicit per-parameter schema so the model can see
    what's expected. The handlers themselves take a single dict so we just
    pass the SDK's args through.
    """
    from claude_agent_sdk import tool

    SCHEMAS: dict[str, tuple[str, dict]] = {
        "send": (
            "Send a message to a recipient or audience. audience is an object "
            "with type='one'|'many'|'region'|'all_alert'|'all_ngo' and shape-"
            "specific fields. bodies is a map of language code -> text. mode "
            "is 'execute' or 'suggest' (large audiences must be 'suggest').",
            {"audience": dict, "bodies": dict, "mode": str},
        ),
        "record_sighting": (
            "Record a civilian sighting tied to the active alert.",
            {
                "alert_id": str,
                "observer_phone": str,
                "geohash": str,
                "notes": str,
                "confidence": float,
                "photo_urls": list,
            },
        ),
        "upsert_cluster": (
            "Create or update a SightingCluster. Provide cluster_id to update "
            "an existing one, omit to create new.",
            {
                "alert_id": str,
                "label": str,
                "center_geohash": str,
                "radius_m": int,
                "sighting_ids": list,
                "reason": str,
                "cluster_id": str,
            },
        ),
        "merge_clusters": (
            "Merge sources into target cluster.",
            {
                "source_cluster_ids": list,
                "target_cluster_id": str,
                "reason": str,
            },
        ),
        "upsert_trajectory": (
            "Create or extend a movement trajectory for the alert subject. "
            "points is a list of {geohash, t, sighting_ids[]} objects.",
            {
                "alert_id": str,
                "points": list,
                "direction_deg": float,
                "speed_kmh": float,
                "confidence": float,
                "reason": str,
                "trajectory_id": str,
            },
        ),
        "apply_tag": (
            "Apply a tag to an entity (idempotent).",
            {
                "entity_type": str,
                "entity_id": str,
                "tag_name": str,
                "confidence": float,
                "reason": str,
            },
        ),
        "remove_tag": (
            "Remove a tag from an entity.",
            {
                "entity_type": str,
                "entity_id": str,
                "tag_name": str,
                "reason": str,
            },
        ),
        "categorize_alert": (
            "Set alert category and urgency. Defaults to mode='suggest' "
            "(operator approves).",
            {
                "alert_id": str,
                "category": str,
                "urgency_tier": str,
                "urgency_score": float,
                "reason": str,
            },
        ),
        "escalate_to_ngo": (
            "Push a notification to the NGO operator console.",
            {"reason": str, "summary": str, "attached_message_ids": list},
        ),
        "mark_bad_actor": (
            "Flag a sender as a bad actor. Defaults to mode='suggest'.",
            {"phone": str, "reason": str, "ttl_seconds": int},
        ),
        "update_alert_status": (
            "Change an alert's status (active|resolved|verified). Defaults to "
            "mode='suggest'.",
            {"alert_id": str, "status": str, "reason": str},
        ),
        "noop": (
            "Explicit 'do nothing' — recorded for audit. Always end with at "
            "least one action call; if no action is appropriate, call noop.",
            {"reason": str},
        ),
        "search": (
            "Read-only search across the case file. entity is one of "
            "message|sighting|decision|cluster|trajectory|tag_assignment. "
            "filters is an object (alert_id, sender_phone, geohash_prefix, "
            "time_start, time_end, classification, status, min_confidence, "
            "tag_name, etc.). sort is similarity|recency|confidence|geo_distance|size.",
            {
                "entity": str,
                "query": str,
                "filters": dict,
                "sort": str,
                "top_k": int,
            },
        ),
        "get": (
            "Read-only PK lookup for any entity by id.",
            {"entity": str, "id": str},
        ),
    }

    sdk_tools = []
    for name, handler in HANDLERS.items():
        description, schema = SCHEMAS[name]

        # Pass-through wrapper: SDK passes named args as a dict; our
        # handlers accept the same dict.
        async def _wrapper(args, _h=handler):
            return await _h(args)

        sdk_tools.append(tool(name, description, schema)(_wrapper))
    return sdk_tools


def make_agent_options() -> Any:
    """Build ClaudeAgentOptions for the live agent worker."""
    from claude_agent_sdk import (
        ClaudeAgentOptions,
        HookMatcher,
        create_sdk_mcp_server,
    )

    sdk_tools = _build_sdk_tools()
    matching_server = create_sdk_mcp_server(
        name="matching", version="0.1.0", tools=sdk_tools
    )

    async def _idempotency_hook(input_, tool_use_id, context):
        # PreToolUse hook receives tool_use blocks; idempotency is enforced
        # in the handler itself (it dedupes within scope.staged), and at
        # commit time via the UNIQUE(idempotency_key) constraint. Pass-through.
        return {}

    async def _audit_hook(input_, tool_use_id, context):
        # PostToolUse hook — turns are captured by the worker draining
        # `client.receive_response()`, so nothing to do here.
        return {}

    return ClaudeAgentOptions(
        mcp_servers={"matching": matching_server},
        allowed_tools=[f"mcp__matching__{n}" for n in HANDLERS],
        system_prompt=AGENT_SYSTEM_PROMPT,
        setting_sources=[],  # do not load .claude/, CLAUDE.md, skills, plugins
        permission_mode="bypassPermissions",
        max_turns=8,
        max_budget_usd=0.50,
        model="claude-sonnet-4-5",
        fallback_model="claude-opus-4-1",
        enable_file_checkpointing=False,
        hooks={
            "PreToolUse": [HookMatcher(matcher="mcp__matching__*", hooks=[_idempotency_hook])],
            "PostToolUse": [HookMatcher(matcher="mcp__matching__*", hooks=[_audit_hook])],
        },
    )


# ---------------------------------------------------------------------------
# Stub mode — deterministic decision from context. Used when
# ANTHROPIC_API_KEY is unset (tests + first-boot demo).
# ---------------------------------------------------------------------------


async def stub_decide(ctx: AgentContext, scope: DecisionScope) -> dict:
    """Synthesize a decision: record sightings + ack senders + sometimes
    escalate to NGO. Mirrors what a real agent would do for canonical
    inbound traffic.

    Returns a `decision_meta` dict for the AgentDecision row.
    """
    set_scope(scope)
    try:
        emitted: list[str] = []
        # For each high-confidence sighting, record it + ack the sender.
        for triaged in ctx.triaged:
            inbound = ctx.inbound_by_msg_id.get(triaged.msg_id)
            if inbound is None:
                continue
            if triaged.classification == "sighting" and triaged.confidence >= 0.6:
                if ctx.alert is None:
                    continue
                geohash = triaged.geohash6 or ctx.alert.last_seen_geohash or "unknown"
                await HANDLERS["record_sighting"](
                    {
                        "alert_id": ctx.alert.alert_id,
                        "observer_phone": inbound.sender_phone,
                        "geohash": geohash,
                        "notes": inbound.body[:500],
                        "confidence": float(triaged.confidence),
                        "photo_urls": [],
                    }
                )
                emitted.append("record_sighting")
                lang = (triaged.language or "en")
                await HANDLERS["send"](
                    {
                        "audience": {"type": "one", "phone": inbound.sender_phone},
                        "bodies": {lang: "Thanks — your sighting is recorded."},
                    }
                )
                emitted.append("send")
            elif triaged.classification == "bad_actor":
                await HANDLERS["mark_bad_actor"](
                    {
                        "phone": inbound.sender_phone,
                        "reason": "triage flagged",
                        "ttl_seconds": 3600,
                    }
                )
                emitted.append("mark_bad_actor")

        # If the bucket is heartbeat-only (no triaged messages), emit a noop.
        if not ctx.triaged:
            await HANDLERS["noop"]({"reason": "heartbeat: no new inbound"})
            emitted.append("noop")
        elif not emitted:
            await HANDLERS["noop"]({"reason": "no actionable messages in bucket"})
            emitted.append("noop")

        summary = "stub: " + ",".join(emitted)
        return {
            "model": "stub",
            "reasoning_summary": summary,
            "turns": [
                {
                    "role": "assistant",
                    "content": summary,
                    "tool_calls": [
                        {"name": s.tool_name, "args": s.args} for s in scope.staged
                    ],
                }
            ],
            "total_turns": 1,
            "latency_ms": 0,
            "cost_usd": 0.0,
        }
    finally:
        clear_scope()


# ---------------------------------------------------------------------------
# Real-mode runner
# ---------------------------------------------------------------------------


async def real_decide(ctx: AgentContext, scope: DecisionScope, client: Any) -> dict:
    """Run the multi-turn loop via ClaudeSDKClient. Returns decision_meta."""
    from claude_agent_sdk import ResultMessage

    set_scope(scope)
    try:
        prompt = render_prompt(ctx)
        await client.query(prompt=prompt, session_id=ctx.bucket.bucket_key)
        turns: list[Any] = []
        result: Optional[ResultMessage] = None
        async for msg in client.receive_response():
            turns.append(_serialize_msg(msg))
            if isinstance(msg, ResultMessage):
                result = msg
                break

        if result is None:
            # Force a noop if the loop produced nothing.
            await HANDLERS["noop"]({"reason": "no result returned"})

        summary = (result.result if result and hasattr(result, "result") else None) or "agent decision"
        return {
            "model": "claude-sonnet-4-5",
            "reasoning_summary": summary,
            "turns": turns,
            "total_turns": result.num_turns if result else len(turns),
            "latency_ms": int(result.duration_ms) if result and getattr(result, "duration_ms", None) else 0,
            "cost_usd": float(result.total_cost_usd or 0.0) if result else 0.0,
        }
    finally:
        clear_scope()


def _serialize_msg(msg: Any) -> dict:
    """Best-effort JSON-serializable form of an SDK message."""
    try:
        return {"type": type(msg).__name__, "repr": str(msg)[:2000]}
    except Exception:
        return {"type": type(msg).__name__}


def have_real_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
