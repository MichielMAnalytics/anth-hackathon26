# Matching Engine — Server-Side Design

**Date:** 2026-04-25
**Project:** P2P Amber Alert Network over Bitchat (`anth-hackathon26`)
**Scope:** Server-side architecture for the central NGO node — the system that ingests inbound civilian messages, decides what to do with them via an LLM agent loop, and dispatches outbound replies and broadcasts. Channel-agnostic at the agent layer; transport adapters at the edges.

---

## 1. Goals & non-goals

### Goals

- Ingest inbound civilian messages from heterogeneous channels (app, SMS, bitchat) under spike load (target: 1M messages over 5 minutes without data loss).
- Run an LLM-driven agent loop that decides, per region per alert, what action to take (reply to a sender, broadcast to a region, escalate to NGO operator, mark a bad actor, update alert status, no-op).
- Dispatch outbound messages reliably with a per-recipient channel cascade (app push first, SMS fallback, bitchat last).
- Make the system fully auditable and replayable from the database alone.
- Collapse cleanly to a single-process hackathon deployment without code changes.

### Non-goals

- Multi-NGO multi-tenancy from day one (schema is multi-tenant, runtime is single-NGO).
- Real BLE in the hackathon demo (sim transport only; bitchat adapter is a stretch goal per the existing README).
- Production-grade key management (ephemeral keys are fine).
- LLM prompt engineering or model selection details (treated as a black box; only the I/O contract is specified here).
- App registration / onboarding flow (handled by the government-pushed app, out of scope for the matching engine).

---

## 2. Mental model

The matching engine is a four-stage DAG, each stage communicating only via database tables (no inter-process RPC):

```
Inbound channels  →  API Tier  →  Triage Worker  →  Bucket queue  →  Agent Worker  →  ToolCall queue  →  Outbound Dispatcher  →  Outbound channels
                     (mailroom)   (cheap LLM)       (coalescing)     (main LLM)        (intent rows)     (provider calls)
```

**Key architectural moves:**

1. **Per-message inbound, per-bucket agent.** A bucket is the tuple `(alert_id, geohash_prefix, time_window)`. Many messages collapse into one agent decision. This is the spike-handling primitive.
2. **DB-as-bus.** Every contract between components is a table. No RPC. Every component is restartable, replayable, and auditable.
3. **Idempotency keys at every queue boundary.** At-least-once everywhere, exactly-once where it matters (outbound sends).
4. **Channel-agnostic agent.** The agent never knows or cares what wire a message arrived on or will leave on. Adapters live at the edges.
5. **Push-first cascade.** Outbound prefers app push (free, instant); SMS is the fallback (paid, rate-limited); bitchat is the last resort (offline only).

---

## 3. Runtime topology — the five nodes

```
                                                   ┌──────────────────────────┐
                                                   │  NGO Console (browser)   │
                                                   │  React SPA, static       │
                                                   └─────────────┬────────────┘
                                                                 │ HTTPS + WS
  ┌─────────────────┐                                            ▼
  │ Twilio  /  Sim  │ ──── webhook ────►              ┌─────────────────────────┐
  │ SmsProvider     │ ◄─── send() ─────               │   1. API Tier           │
  └─────────────────┘                                 │   FastAPI, stateless    │
                                                      │   - channel adapters    │
  ┌─────────────────┐                                 │   - /ngo REST + WS      │
  │ App client      │ ──── WSS ────────►              │   - /app WS             │
  │ (push token,    │ ◄─── push ───────               │   auth + persist + ack  │
  │  WS heartbeat)  │                                 └────────┬────────────────┘
  └─────────────────┘                                          │ SQL writes
                                                               ▼
                                                     ┌─────────────────────┐
                                                     │   5. Data Tier      │
                                                     │   Postgres + pgvector│
                                                     │   tables = queues    │
                                                     │   HNSW indices       │
                                                     │   for semantic search│
                                                     └────────┬────────────┘
                                                              │ SQL claims
                                                              │
                                          ┌───────────────────┼───────────────────┐
                                          ▼                   ▼                   ▼
                                ┌─────────────────┐ ┌──────────────────┐ ┌──────────────────┐
                                │ 2. Triage       │ │ 3. Agent Worker  │ │ 4. Outbound      │
                                │    Worker       │ │  (per-alert      │ │    Dispatcher    │
                                │  (Haiku-class   │ │   advisory lock) │ │  (rate-limited,  │
                                │   small LLM)    │ │  (Sonnet/Opus)   │ │   channel        │
                                │                 │ │                  │ │   cascade)       │
                                └─────────────────┘ └──────────────────┘ └──────────────────┘
```

| # | Node | LLM? | Stateless? | Scales with | Output |
|---|---|---|---|---|---|
| 1 | API Tier | no | yes (WS sticky) | inbound conn count | `InboundMessage` rows, ack to caller |
| 2 | Triage Worker | yes — small/cheap | yes | inbound msg rate | `TriagedMessage` + `Bucket` rows |
| 3 | Agent Worker | yes — main | yes (idempotent) | bucket rate, cost-bound, capped 1-per-alert | `AgentDecision` + `ToolCall` rows |
| 4 | Outbound Dispatcher | no | yes (idempotent) | provider quotas | `OutboundMessage` rows + provider sends |
| 5 | Data Tier | n/a | stateful | data volume | the truth, the audit log, the vector store |

**Hackathon collapse:** all four worker nodes run as asyncio tasks inside a single FastAPI process; the data tier is a Postgres container (`postgres:16` + `pgvector` extension). One `docker compose up` brings the backend up: one app container + one DB container. Sim SMS provider in-process. Splitting workers into separate processes is a deployment-time decision, not a code change.

**Heartbeat scheduler.** A tiny periodic asyncio task (separate from the four worker types, but living in the same app process) inserts synthetic empty `Bucket` rows for every `Alert(status='active')` at a configurable cadence (default 5 min). This drives the agent's *consolidation* runs — see §4.3. In prod, this can be replaced by `pg_cron` for stronger uptime guarantees; the trigger contract is the same.

**Prod expansion path** (in order of when needed):
1. Workers split into separate deployments (when LLM cost forces tight Agent concurrency caps, or when Triage and Dispatcher want independent scaling).
2. Add Redis pub/sub (only when running multiple API instances; replaces Postgres `LISTEN/NOTIFY`).
3. Partition `InboundMessage` / `TriagedMessage` / `OutboundMessage` by day (when retention rolls past a few weeks at incident scale).
4. Multi-region API tier (only if NGOs span continents).

We deliberately drop SQLite. pgvector, `LISTEN/NOTIFY`, advisory locks, and partial indices all want a real Postgres; running on Postgres from day one removes a code path and gives the demo full production semantics.

---

## 4. Component responsibilities

### 4.1 API Tier (mailroom)

**Owns:** every external connection. Twilio webhooks, app WSS, NGO operator browser.

**Responsibilities:**
1. Authenticate (Twilio signature, app JWT, NGO operator session).
2. Persist — insert raw inbound into `InboundMessage` and ack the caller fast (Twilio retries above ~10s).
3. Maintain WS sessions to apps and NGO console; relay outbound notifications when the dispatcher pushes them.

**Does not:** classify, dedupe, geohash, score trust, call any LLM, or talk to providers. It is a stupid mailroom.

**Deployment:** single instance for hackathon; multi-instance ready for prod via Redis pub/sub (see §8).

### 4.2 Triage Worker (cheap filter)

**Owns:** turning raw, untrusted inbound into a structured, deduped, geohashed, classified row safe to bucket.

**LLM:** small/cheap (Haiku-class) with structured-output mode. Per-message. ~400ms latency budget. ~500 tokens in / 200 out.

**Client library:** the **bare `anthropic` Python client** (not the Agent SDK). Triage is a single-shot, no-tool, no-multi-turn structured extraction — the Agent SDK's subprocess + agent-loop machinery is the wrong shape. One `messages.create()` call per message, with a single tool defined to enforce the JSON schema:

```python
from anthropic import AsyncAnthropic
client = AsyncAnthropic()

resp = await client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=400,
    system=TRIAGE_SYSTEM_PROMPT,
    messages=[{"role": "user", "content": rendered_inbound}],
    tools=[TRIAGE_OUTPUT_SCHEMA],   # forces structured output
    tool_choice={"type": "tool", "name": "classify"},
)
classification = resp.content[0].input
```

**Responsibilities:**
1. Claim `InboundMessage` rows where `status='new'`.
2. Call cheap LLM with structured output schema:
   ```
   {classification: "sighting"|"question"|"ack"|"noise"|"bad_actor",
    geohash6: str|null,
    geohash_source: "app_gps"|"registered_home"|"alert_region"|"body_extraction",
    confidence: float,
    language: ISO 639-1,
    dedup_hash: str}
   ```
3. Compute embedding (`voyage-3-lite` or `text-embedding-3-small`, 512 dims, ~$0.00002 per call) over the normalized body. Stored on `TriagedMessage.body_embedding` for later semantic retrieval by the agent.
4. Check `BadActor` table; gate accordingly.
5. Compute `bucket_key = (alert_id, geohash_prefix_4, time_window)`.
6. Insert `TriagedMessage` (including embedding); upsert `Bucket(status='open')`.
7. Emit `bucket_open` notification (Postgres NOTIFY or Redis pub/sub).

**Why separate from API Tier:** API tier has a 10-second budget per webhook; triage may need 400ms+ for the LLM call. Triage failures shouldn't backpressure Twilio (else: webhook retries → duplicate `InboundMessage` rows).

**Why separate from Agent Worker:** different cost profile, different model, different rate-limit pool, different scaling axis. Mixing them either starves cheap work behind expensive reasoning, or overprovisions Sonnet for "is this spam?".

### 4.3 Agent Worker (decision-maker)

**Owns:** turning a bucket of triaged messages into a decision plus tool calls.

**LLM:** main reasoning model (Sonnet/Opus). Per-bucket. 5–15s latency budget. 5k–20k tokens in / 1k–3k out.

**Client library:** the **`claude-agent-sdk` Python package** (≥ 0.2.111 for Opus 4.7 support). The SDK provides the multi-turn loop, tool dispatch, parallel tool calls, hooks, cost/usage capture, and rate-limit events out of the box. Configured for server use, *not* Claude Code coding usage:

```python
from claude_agent_sdk import (
    ClaudeSDKClient, ClaudeAgentOptions, tool, create_sdk_mcp_server, HookMatcher
)

# Custom tools — async handlers, run in-process in the FastAPI worker
@tool("send", "Outbound to one/many/region/all_alert/all_ngo",
      {"audience": dict, "bodies": dict, "mode": str})
async def send_handler(args):
    tc_id = await db.insert_tool_call(name="send", args=args, mode=args["mode"])
    return {"content": [{"type": "text", "text": f"queued tool_call_id={tc_id}"}]}

# ... 13 more tools (record_sighting, upsert_cluster, ..., search, get)

matching = create_sdk_mcp_server(name="matching", version="0.1.0",
                                 tools=[send_handler, ...])

AGENT_OPTIONS = ClaudeAgentOptions(
    mcp_servers={"matching": matching},
    allowed_tools=["mcp__matching__*"],
    system_prompt=AGENT_SYSTEM_PROMPT,        # full string; replaces default
    setting_sources=[],                       # do not load .claude/, CLAUDE.md, skills, etc.
    permission_mode="bypassPermissions",      # no interactive prompts; gate via DB
    max_turns=8,
    max_budget_usd=0.50,                      # per-decision cost ceiling
    model="claude-sonnet-4-6",
    fallback_model="claude-opus-4-7",
    enable_file_checkpointing=False,          # no on-disk session state
    hooks={
        "PreToolUse":  [HookMatcher(matcher="mcp__matching__*", hooks=[idempotency_check])],
        "PostToolUse": [HookMatcher(matcher="mcp__matching__*", hooks=[audit_tool_call])],
    },
)
```

**Hook responsibilities:**
- `PreToolUse` (idempotency check): compute `idempotency_key = hash(bucket_key, tool_name, canonical_json(args))`, look up existing `ToolCall` row; if duplicate, short-circuit by returning the prior result; otherwise let the call proceed.
- `PostToolUse` (audit): append `(tool_use_id, name, args, result, latency)` into the in-progress `turns JSON` for the `AgentDecision` row.

**Concurrency rules:**
- Global pool of N workers (default 8).
- **Per-alert advisory lock**: at most one agent decision in flight per `alert_id` at any time. Prevents two concurrent buckets for the same alert from independently deciding to broadcast similar follow-ups.

**Responsibilities:**
1. Claim a `Bucket` row where `status='open'`, atomically setting `status='claimed'` and `claimed_at`.
2. Acquire per-alert advisory lock for the bucket's `alert_id`. If unavailable, release the bucket back (`status='open'`) and pick another.
3. Read **initial context** (parallel queries):
   - All `TriagedMessage` rows in the bucket.
   - Full `Alert` payload (incl. `category`, `urgency_tier`, `urgency_score`) + `NGO.standing_orders`.
   - Last 5 messages from each unique sender in the bucket.
   - `Account` snapshots for each unique sender (incl. credibility tags).
   - Last 10 `AgentDecision` rows for this `alert_id` (avoid redundant broadcasts).
   - Last 20 `Sighting` rows for this `alert_id` (the rolling case file).
   - Active `SightingCluster` rows for this alert (top 10 by recency).
   - Active `Trajectory` row for this alert (most recent if any).
   - Recent `TagAssignment` rows for this alert (last 30 across all entity types).
   - Current dispatch backlog depth + pending-suggestions backlog (for soft backpressure on large `send` calls).
4. **Multi-turn agent loop** (default cap: 8 turns):
   a. Build prompt: system (role + tool defs incl. action and retrieval + standing orders + backpressure flag) + user (initial context + decision instructions).
   b. Call main LLM. Anthropic supports parallel tool calls in one turn.
   c. If response contains **retrieval tool calls** (`search`, `get` — see §5.2):
      - Execute them (in parallel where possible). These are read-only; no DB writes.
      - Append `tool_use` and `tool_result` blocks to the conversation.
      - Loop back to (b).
   d. If response contains **action tool calls** (`send`, `record_sighting`, `escalate_to_ngo`, `mark_bad_actor`, `update_alert_status`, `noop` — see §5.1) or only final text: exit loop.
   e. If turn cap reached without an action call: force a final turn with prompt: "Decide now. Emit action tool calls or `noop`." If still nothing → emit synthetic `noop(reason='turn_cap_reached')`.
5. Persist:
   - One `AgentDecision` row with full multi-turn conversation in `turns JSON` (every `(role, content, tool_calls, tool_results)` per turn — replayable step-by-step).
   - N `ToolCall` rows for the action calls only, each with `mode` (`execute`|`suggest`) chosen per §5.4 and a stable `idempotency_key = hash(bucket_key, tool_name, args)`.
6. Mark `Bucket.status='done'`; release advisory lock; emit `toolcalls_pending` (for `mode='execute'` rows) and/or `suggestions_pending` (for `mode='suggest'` rows).

**Heartbeat-triggered buckets.** A periodic scheduler (asyncio task in the app process; `pg_cron` in prod) inserts a synthetic empty `Bucket` row every N minutes (default 5) for each `Alert(status='active')`, with `bucket_key = 'heartbeat:{alert_id}:{ts}'` and zero member messages. The Agent Worker claims it like any other bucket and runs the same multi-turn loop — but with no new inbound, the agent's job is *consolidation*: extending or deprecating trajectories, refining cluster status, applying tags retroactively, escalating contradictions. Most heartbeats result in `noop` with reasoning ("nothing changed since last heartbeat"). Heartbeat cadence is per-alert configurable (longer when quiet, shorter during spike).

**Subprocess model and worker lifecycle.** The Python Agent SDK spawns the Claude Code CLI as a stdio subprocess. To amortize that cost, each Agent Worker holds **one persistent `ClaudeSDKClient` for its lifetime** and scopes each decision to a fresh `session_id = bucket_key`:

```python
class AgentWorker:
    async def __aenter__(self):
        self.client = ClaudeSDKClient(options=AGENT_OPTIONS)
        await self.client.connect()
        return self

    async def run_decision(self, bucket, ctx):
        await self.client.query(prompt=build_prompt(bucket, ctx),
                                session_id=bucket.bucket_key)
        turns = []
        async for msg in self.client.receive_response():
            turns.append(msg)
            if isinstance(msg, RateLimitEvent) and msg.rate_limit_info.status == "rejected":
                # surface to coordinator; back off
                raise BackpressureError(msg.rate_limit_info.resets_at)
            if isinstance(msg, ResultMessage):
                return AgentDecision(
                    bucket_key=bucket.bucket_key,
                    model=AGENT_OPTIONS.model,
                    turns=turns,                      # full multi-turn audit
                    total_turns=msg.num_turns,
                    latency_ms=msg.duration_ms,
                    cost_usd=msg.total_cost_usd,
                    reasoning_summary=extract_summary(turns),
                )

    async def __aexit__(self, *a):
        await self.client.disconnect()
```

**Restart on `ProcessError`.** A subprocess can die (OOM, segfault, host-level signal). Workers wrap the loop in a watchdog that catches `ProcessError`/`CLIConnectionError`, logs, and re-creates the `ClaudeSDKClient`. The current bucket is released back to `status='open'` with `retry_count++`; the reaper handles eventual dead-lettering after the configured retry cap.

### 4.4 Outbound Dispatcher (courier)

**Owns:** converting `ToolCall` intent into bytes on the wire, reliably, at provider-allowed rates.

**No LLM.** Pure orchestration.

**Responsibilities:**
1. Claim `ToolCall` rows where `status='pending' AND approval_status IN ('auto_executed','approved')` (i.e., agent-auto-executed *and* operator-approved suggestions flow through the same path).
2. For `send` tool calls:
   - Resolve recipients from the audience selector:
     - `one` → single phone.
     - `many` → explicit list.
     - `region` → `SELECT phone FROM Account WHERE last_known_geohash LIKE '<prefix>%' AND trust_score >= min_trust AND opted_out = false` (with optional radius filter on geohash center).
     - `all_alert` → `SELECT recipient_phone FROM AlertDelivery WHERE alert_id = ?`.
     - `all_ngo` → `SELECT phone FROM Account WHERE ngo_id = ? AND opted_out = false`.
   - For each recipient, pick channel via the cascade:
     1. App push if `push_token` exists and `app_last_seen_at` within 14 days.
     2. SMS via `SmsProvider.send()`.
     3. Bitchat (stretch).
   - Insert `OutboundMessage` rows (`status='queued'`).
3. Send loop, per provider, rate-limited via token bucket:
   - App push: WS push to API Tier instance holding the recipient's WS, via Redis pub/sub.
   - SMS: `SmsProvider.send(to, body, idempotency_key=out_id)` — idempotency key is forwarded to Twilio so a crash recovery doesn't double-send.
4. Track delivery:
   - App push ack via WS within fallback window (default 30s) → `status='delivered'`. Timeout → fall back to SMS as a *new* `OutboundMessage` with `previous_out_id` pointing to the failed push.
   - SMS via Twilio status webhook → `status='delivered'|'failed'`.
5. Mark `ToolCall.status='done'` when all child `OutboundMessage`s reach a terminal status.

**Internal-only tool calls** (`record_sighting`, `update_alert_status`, `mark_bad_actor`, `escalate_to_ngo`):
- `record_sighting` → insert `Sighting` row, mark done.
- `update_alert_status` → update `Alert` row, mark done.
- `mark_bad_actor` → insert/update `BadActor` row, mark done.
- `escalate_to_ngo` → insert `OutboundMessage(channel='ngo_console')` and emit WS push to the NGO console.

### 4.5 Data Tier

**Owns:** all state. The only stateful node. Postgres ≥ 16 with the `pgvector` extension. See §6 for schema.

---

## 5. Agent tool surface

The agent has two tool categories:

- **Action tools** (§5.1) — produce side effects, emit `ToolCall` rows, end the multi-turn loop. Every action carries a `mode` field (`execute` or `suggest`) that determines whether it auto-runs or routes to operator approval.
- **Retrieval tools** (§5.2) — read-only, no side effects. The agent calls them as needed during the multi-turn loop to dig deeper into the database. They do **not** create `ToolCall` rows.

### 5.1 Action tools

Twelve tools, grouped: **comms**, **case data**, **derived knowledge**, **operator surface**, **audit**.

**Comms**

| Tool | Args | Effect | Default mode |
|---|---|---|---|
| `send(audience, bodies, mode)` | audience selector (§5.3), `bodies: {lang_code: text}` map | Dispatcher resolves audience → recipient list → channel cascade → send. | per audience size (§5.4) |

**Case data (raw)**

| Tool | Args | Effect | Default mode |
|---|---|---|---|
| `record_sighting(alert_id, observer_phone, geohash, notes, confidence, photo_urls[])` | structured sighting | Insert `Sighting` row + `notes_embedding`. | execute |

**Derived knowledge (the running understanding)**

| Tool | Args | Effect | Default mode |
|---|---|---|---|
| `upsert_cluster(cluster_id?, alert_id, label, center_geohash, radius_m, sighting_ids[], reason)` | cluster shape + member sightings | Create new `SightingCluster` or update existing. Refreshes `embedding` (centroid of member `notes_embedding`s) and cached aggregates. Agent should `search(entity='cluster', filters={alert_id, geohash_prefix})` first to find a cluster to merge into. | execute |
| `merge_clusters(source_cluster_ids[], target_cluster_id, reason)` | clusters to consolidate | Mark sources `status='merged', merged_into=target`; merge member lists onto target; recompute centroid. | execute |
| `upsert_trajectory(alert_id, trajectory_id?, points[], direction_deg, speed_kmh, confidence, reason)` | trajectory shape | Create or extend a `Trajectory`. Each point references source sighting IDs. | execute |
| `apply_tag(entity_type, entity_id, tag_name, confidence?, reason)` | what + tag | Idempotent (UNIQUE on `(tag_id, entity_type, entity_id)`). `Tag` row created lazily on first use within a namespace. Free-form taxonomy. | execute |
| `remove_tag(entity_type, entity_id, tag_name, reason)` | un-tag | Idempotent. | execute |
| `categorize_alert(alert_id, category, urgency_tier, urgency_score, reason)` | structured alert classification | Updates `Alert.category`, `Alert.urgency_tier`, `Alert.urgency_score`. Drives downstream policy thresholds. | **suggest** |

**Operator surface**

| Tool | Args | Effect | Default mode |
|---|---|---|---|
| `escalate_to_ngo(reason, summary, attached_message_ids[])` | reason code, human summary, message refs | Push notification to NGO console with deep link. *This* is the operator path. | execute |
| `mark_bad_actor(phone, reason, ttl_seconds)` | phone, reason, expiry | Insert `BadActor` row; future messages from this phone are dropped at triage. | **suggest** |
| `update_alert_status(alert_id, status, reason)` | alert id, new status, reason | Update `Alert.status` (active / resolved / verified). | **suggest** |

**Audit**

| Tool | Args | Effect | Default mode |
|---|---|---|---|
| `noop(reason)` | reason | Explicit "do nothing" — still recorded for audit. | execute |

Why most derived-knowledge tools default to `execute`: they're recoverable. A wrong cluster label can be fixed with another `upsert_cluster`; a wrong tag can be removed. Only `categorize_alert` defaults to `suggest` because it changes downstream policy (e.g., a `category='missing_child'` may unlock auto-broadcast in standing orders) — miscategorization cascades, so the operator signs off.

### 5.2 Retrieval tools (read-only, no side effects)

Two unified tools cover all read paths. Free to call during the multi-turn loop (within the turn cap); they do not create `ToolCall` rows.

#### `search`

```
search(
    entity:  "message" | "sighting" | "decision" | "cluster" | "trajectory" | "tag_assignment",
    query:   str | null,                            # if set, semantic ranking via pgvector HNSW
                                                    # (messages, sightings, clusters)
    filters: object,                                # any combination of the fields below
    sort:    "similarity" | "recency" | "confidence" | "geo_distance" | "size",
    top_k:   int = 10                                # max 50
)
  → list of records with all fields + score
```

**Filters** (all optional, applied as AND):

| Field | Applies to | Notes |
|---|---|---|
| `alert_id` | message, sighting, decision, cluster, trajectory, tag_assignment | scope to one alert |
| `sender_phone` | message | who sent it |
| `observer_phone` | sighting | who reported it |
| `geohash_prefix` | message, sighting, cluster | spatial filter |
| `radius_km` | message, sighting, cluster | only with `geohash_prefix`; finer geo filter |
| `time_start`, `time_end` | all | temporal filter |
| `classification` | message | `sighting`\|`question`\|`ack`\|`noise` |
| `min_confidence` | message, sighting, cluster, trajectory | filter low-confidence rows |
| `language` | message | ISO 639-1 |
| `has_media` | message, sighting | photo attached |
| `status` | cluster, trajectory | `'active'` (default), `'verified'`, `'merged'`, `'stale'`, `'contradicted'`, `'false_lead'` |
| `min_size` | cluster | minimum member count |
| `tag_name` | tag_assignment | filter by tag (e.g., all things tagged `vehicle_sighting`) |
| `entity_type` | tag_assignment | which kind of thing the tag is on (`message`, `sighting`, `sender`, `alert`, `cluster`) |
| `applied_by` | tag_assignment | `'agent'` or `'operator'` |
| `excludes_ids` | all | skip already-seen rows when paginating |

**Sort default:** `similarity` if `query` is set, else `recency`.

**Validation:** filters not applicable to the chosen entity return a structured error in the tool result (`filter 'sender_phone' not applicable to entity 'sighting'`). The agent learns the correct shape from the error and retries. Safer than silent-ignore.

**Outbound is intentionally not searchable.** The agent reasons over civilian inbound; system outbound is visible via the recent-decisions context (which contains the prior `tool_calls` JSON). Keeping outbound off the search surface prevents accidental loops where the agent reasons over its own past sends.

#### `get`

```
get(entity: "message"|"sighting"|"decision"|"alert"|"account"|"cluster"|"trajectory"|"tag"|"tag_assignment", id: str)
  → full record, including normally-truncated fields (full body, raw payload,
    media URLs, full reasoning summary, full sighting_ids list)
```

PK lookup escape hatch for when a search result is truncated and the agent needs the full row.

**Cap on retrieval per decision**: total turns ≤ 8 (configurable). Most decisions need 0 retrieval rounds (initial context is rich); 1–2 rounds is typical for cluster-detection or trajectory-inference scenarios. Parallel tool calls within a single turn count as one turn against the cap.

**Common search patterns the agent uses:**

```
# semantic dedup before record_sighting
search(entity="sighting", query=this_message.body,
       filters={alert_id, time_start: now-1h}, top_k=5)

# nearby sightings for cluster detection
search(entity="sighting",
       filters={alert_id, geohash_prefix: "sv8d6", time_start: now-30min},
       sort="geo_distance")

# sender deep-dive when trust signal is mixed
search(entity="message",
       filters={sender_phone, time_start: now-24h},
       sort="recency", top_k=20)

# corroboration across the alert (cross-language semantic)
search(entity="message", query="red jacket walking south",
       filters={alert_id, classification: "sighting", time_start: now-1h})

# full case file
search(entity="sighting", filters={alert_id}, sort="recency", top_k=50)
search(entity="decision", filters={alert_id}, sort="recency", top_k=20)
# (the agent runs these in parallel in one turn)

# nearby clusters before creating a new one (dedup pass)
search(entity="cluster",
       filters={alert_id, geohash_prefix: "sv8d6", status: "active"},
       sort="geo_distance", top_k=5)

# all things tagged "trajectory_hint" for this alert
search(entity="tag_assignment",
       filters={alert_id, tag_name: "trajectory_hint", applied_by: "agent"})

# semantic search over cluster labels and member descriptions
search(entity="cluster", query="bakery sightings",
       filters={alert_id, status: "active"})
```

### 5.3 Audience selector for `send`

Discriminated union; dispatcher resolves any shape into a recipient list:

```
{type: "one",       phone}                                    # single sender
{type: "many",      phones: list[str]}                        # explicit list
{type: "region",    geohash_prefix, radius_km, min_trust}     # geo filter
{type: "all_alert", alert_id}                                 # everyone the alert was sent to
{type: "all_ngo"}                                             # full NGO reach (rare)
```

### 5.4 Execute vs suggest mode

The agent picks `mode` per call based on (a) NGO standing orders, (b) audience size, (c) the backpressure flag. Default risk policy when standing orders are silent:

| `send` audience | Default mode | Why |
|---|---|---|
| `one` (ack a sender) | execute | low risk, low cost |
| `many` with size 2–10 | execute | small cluster of senders |
| `many` with size 11–100 / `region` with size 11–100 | execute, but operator gets an informational notification | medium risk, observable |
| `many` or `region` with size 100+ | **suggest** | mass impact, human signs off |
| `all_alert` / `all_ngo` | **suggest, always** | never auto-blast |

NGO operators override these via standing orders ("auto-approve broadcasts up to 1,000 in geohash sv8d for the next 30 min"). The agent reads standing orders on every run, so policy changes take effect on the next decision.

### 5.5 Approval state machine

Every `ToolCall` row has both `mode` and `approval_status`:

```
mode='execute'  →  approval_status='auto_executed'  →  dispatcher claims immediately
mode='suggest'  →  approval_status='pending'        →  shows in NGO console
                   on operator approve              →  'approved'  →  dispatcher claims
                   on operator reject               →  'rejected'  →  no send, audit retained
                   on auto-expire (default 1h)      →  'expired'   →  no send, audit retained
```

Dispatcher claim query: `WHERE status='pending' AND approval_status IN ('auto_executed','approved')`.

The operator may also **edit** a suggestion (tweak `bodies`, narrow `audience`, change `min_trust`) before approving — saved as a new `ToolCall` linked to the original via `revised_from_call_id`, with the original marked `'rejected'`.

### 5.6 Idempotency and backpressure

**Idempotency key** = `sha256(bucket_key || tool_name || canonical_json(args))`. Replays of the same agent decision (worker crash) won't double-execute or double-suggest.

**Backpressure rule:** if dispatch backlog or pending-suggestions backlog exceeds threshold, the prompt's system notice tells the agent to prefer `mode='suggest'` over `mode='execute'`, and to prefer `escalate_to_ngo` over either. The agent retains discretion — "we found her, cancel the alert" overrides backpressure — but the default tilts toward operator review under load.

---

## 6. Data model

All tables use ULID primary keys unless noted. Created/updated timestamps omitted for brevity; assume present everywhere. **All tables carry `ngo_id` FK** for multi-tenancy from day one (cheaper to have it unused than to backfill later).

```
Account
  phone PK, ngo_id FK, account_id, language, home_geohash,
  last_known_geohash, push_token, app_last_seen_at,
  trust_score, opted_out, channel_pref, sms_fallback_after_seconds,
  source: 'app'|'seed'

NGO
  ngo_id PK, name, region_geohash_prefix,
  standing_orders TEXT, operator_pubkey

Alert
  alert_id PK, ngo_id FK, person_name, photo_url,
  last_seen_geohash, description, region_geohash_prefix,
  status: 'active'|'resolved'|'verified', expires_at,
  category,                                -- 'missing_child'|'missing_elder'|... (enum)
  urgency_tier: 'low'|'med'|'high'|'critical',
  urgency_score float                      -- 0..1, agent-derived

InboundMessage
  msg_id PK, ngo_id FK, channel, sender_phone FK→Account,
  in_reply_to_alert_id FK→Alert, body, media_urls JSON,
  raw JSON, received_at,
  status: 'new'|'triaging'|'triaged'|'failed',
  retry_count, claimed_at, claimed_by

TriagedMessage
  msg_id PK FK→InboundMessage, ngo_id FK, classification,
  geohash6, geohash_source, confidence, language,
  duplicate_of, trust_score, bucket_key,
  body_embedding vector(512)              -- pgvector, generated at triage

Bucket
  bucket_key PK, ngo_id FK, alert_id, geohash_prefix_4,
  window_start, window_length_ms,
  status: 'open'|'claimed'|'done'|'failed',
  claimed_by, claimed_at, retry_count

AgentDecision
  decision_id PK, ngo_id FK, bucket_key FK→Bucket,
  model, prompt_hash, reasoning_summary,
  tool_calls JSON,                         -- summary of action tool calls only
  turns JSON,                              -- full multi-turn conversation:
                                           --   list of {role, content, tool_use_blocks,
                                           --   tool_result_blocks, latency_ms}
                                           -- replayable step-by-step
  total_turns INT, latency_ms, cost_usd
  UNIQUE(bucket_key)

ToolCall
  call_id PK, ngo_id FK, decision_id FK,
  tool_name, args JSON, idempotency_key UNIQUE,
  mode: 'execute'|'suggest',
  approval_status: 'auto_executed'|'pending'|'approved'|'rejected'|'expired',
  decided_by, decided_at,                          -- operator id + timestamp on human approve/reject
  revised_from_call_id FK→ToolCall,                -- if operator edited and re-issued
  status: 'pending'|'in_progress'|'done'|'failed',
  claimed_at, claimed_by, retry_count

OutboundMessage
  out_id PK, ngo_id FK, tool_call_id FK,
  recipient_phone, channel: 'app'|'sms'|'bitchat'|'ngo_console',
  body, language,
  status: 'queued'|'sending'|'sent'|'delivered'|'failed',
  provider_msg_id, error,
  attempt INT, previous_out_id FK→OutboundMessage

Sighting
  sighting_id PK, ngo_id FK, alert_id FK,
  observer_phone, geohash, notes, confidence, photo_urls JSON,
  notes_embedding vector(512),             -- pgvector, generated at record_sighting
  recorded_at

BadActor
  phone PK, ngo_id FK, reason, marked_by, expires_at

AlertDelivery
  delivery_id PK, ngo_id FK, alert_id FK, recipient_phone,
  out_id FK→OutboundMessage, sent_at
  -- denormalized roster of who received which alert; populated by dispatcher
  -- on every successful send tied to an alert. Powers audience.type='all_alert'
  -- and "did this person already receive this alert?" lookups.

SightingCluster
  cluster_id PK, ngo_id FK, alert_id FK,
  label,                                   -- agent-generated, human-readable
  center_geohash, radius_m,
  time_window_start, time_window_end,
  sighting_ids JSON,                       -- denormalized member list, fast reads
  sighting_count, mean_confidence,         -- cached aggregates
  status: 'active'|'verified'|'false_lead'|'merged',
  merged_into FK→SightingCluster,          -- if status='merged'
  embedding vector(512),                   -- centroid of member notes_embeddings
  created_at, updated_at, last_member_added_at

Trajectory
  trajectory_id PK, ngo_id FK, alert_id FK,
  points JSON,                             -- [{geohash, time, source_sighting_ids}]
  direction_deg,                           -- compass bearing (0..360)
  speed_kmh, confidence,
  status: 'active'|'stale'|'contradicted',
  last_extended_at, created_at

Tag
  tag_id PK, ngo_id FK, namespace,         -- 'message'|'sighting'|'sender'|'alert'|'cluster'
  name,                                    -- e.g. 'vehicle_sighting', 'false_lead'
  description,                             -- agent or operator written
  created_by: 'agent'|'operator', created_at,
  UNIQUE(ngo_id, namespace, name)          -- dedupe tag creation

TagAssignment
  assignment_id PK, ngo_id FK, tag_id FK,
  entity_type, entity_id,                  -- entity_id is a string ULID/PK
  confidence,
  applied_by: 'agent'|'operator',
  applied_by_id,                           -- decision_id or operator_id
  alert_id FK,                             -- denormalized for fast alert-scoped queries
  created_at,
  UNIQUE(tag_id, entity_type, entity_id)   -- idempotent re-application
```

### Hot-path indices

- `Account(home_geohash text_pattern_ops)` and `Account(last_known_geohash text_pattern_ops)` — supports `WHERE last_known_geohash LIKE 'sv8d%'` for `send` with `audience.type='region'`. Falls back to `home_geohash` when last-known is null.
- `TriagedMessage(bucket_key)` — agent reads bucket contents.
- `TriagedMessage(sender_phone, received_at DESC)` — per-sender history lookup.
- `AgentDecision(alert_id, created_at DESC)` — recent-decisions context.
- `ToolCall(idempotency_key) UNIQUE` — the no-double-broadcast guarantee.
- `Bucket(status, window_start) WHERE status='open'` — worker claim ordering.
- `InboundMessage(status, received_at) WHERE status='new'` — triage worker claim ordering.
- `OutboundMessage(recipient_phone, created_at DESC)` — per-recipient history.
- `AlertDelivery(alert_id, recipient_phone)` — `audience.type='all_alert'` resolution.
- `ToolCall(approval_status, ngo_id) WHERE approval_status='pending'` — NGO console suggested-actions panel.
- `TriagedMessage USING hnsw (body_embedding vector_cosine_ops)` — `search(entity='message', query=...)` semantic ranking.
- `Sighting USING hnsw (notes_embedding vector_cosine_ops)` — `search(entity='sighting', query=...)` semantic ranking.
- `SightingCluster USING hnsw (embedding vector_cosine_ops)` — `search(entity='cluster', query=...)` semantic ranking.
- `TriagedMessage(in_reply_to_alert_id, geohash6 text_pattern_ops, received_at DESC)` — `search` structured filters on messages.
- `Sighting(alert_id, geohash text_pattern_ops, recorded_at DESC)` — `search` structured filters on sightings.
- `Sighting(observer_phone, recorded_at DESC)` — `search` filter by observer.
- `SightingCluster(alert_id, status, last_member_added_at DESC)` — active-cluster lookup for the alert.
- `SightingCluster(alert_id, center_geohash text_pattern_ops) WHERE status='active'` — geo-near-cluster lookup for `upsert_cluster` dedup.
- `Trajectory(alert_id, status, last_extended_at DESC)` — active trajectory lookup.
- `TagAssignment(entity_type, entity_id)` — "what tags does this thing have".
- `TagAssignment(tag_id, entity_type, alert_id)` — "all things in this alert with this tag".
- `Tag(ngo_id, namespace, name) UNIQUE` — tag dedup on creation.
- `Alert(ngo_id, status, urgency_tier) WHERE status='active'` — heartbeat-scheduler scan for live alerts.

### Status lifecycles + reaper

Every queue table (`InboundMessage`, `Bucket`, `ToolCall`) has:
- explicit `status` column with the values listed above
- `claimed_at` timestamp + `claimed_by` worker id
- `retry_count` with a dead-letter terminal state at `status='failed'`

**Reaper job** runs every 60s: any row with `status='claimed'` (or equivalent in-flight state) and `claimed_at < now - 5 min` is reset to its open state and `retry_count++`. After 3 retries → `status='failed'`. Failed rows surface to the NGO console for human triage.

### Postgres + pgvector setup

Postgres ≥ 16 with the `pgvector` extension. Geohash columns are `TEXT` with `text_pattern_ops` B-tree indices for prefix `LIKE` queries; PostGIS is not required for coarse bucketing. Vector columns use `pgvector` with HNSW indices for ANN.

`docker-compose.yml` snippet for hackathon:
```yaml
db:
  image: pgvector/pgvector:pg16
  environment:
    POSTGRES_DB: matching
    POSTGRES_USER: app
    POSTGRES_PASSWORD: app
  ports: ["5432:5432"]
```

Schema migrations run on startup via `alembic upgrade head`.

---

## 7. Message envelope and bucket key

```python
class InboundMessage(BaseModel):
    msg_id: str                       # provider-supplied or ULID, used for dedup
    ngo_id: str
    channel: Literal["sms", "app", "bitchat"]
    received_at: datetime
    sender_phone: str                 # E.164
    sender_account_id: str | None     # resolved at ingress if registered
    in_reply_to_alert_id: str | None
    body: str
    media_urls: list[str]
    raw: dict                         # provider-specific payload, kept for debug

class TriagedMessage(InboundMessage):
    classification: Literal["sighting", "question", "ack", "noise", "bad_actor"]
    geohash6: str | None
    geohash_source: Literal["app_gps", "registered_home", "alert_region", "body_extraction"]
    confidence: float
    language: str                     # ISO 639-1
    duplicate_of: str | None
    trust_score: float                # 0..1
```

### Bucket key

`bucket_key = (alert_id, geohash_prefix_4, window_start)` rendered as a string `"{alert_id}|{geohash4}|{window_iso}"`.

- **`geohash_prefix_4`**: 4-char geohash (~20km cell, stored in `Bucket.geohash_prefix_4`). Coarse enough that "near the bakery" reports cluster; fine enough that Tel Aviv and Haifa don't merge.
- **`window_start`**: floor of `received_at` to a window length. **Adaptive window:**
  - default = 3 seconds
  - if any single bucket exceeded 100 messages in the previous window for the same `(alert_id, geohash_prefix_4)`, next window length doubles (max 30s)
  - back-off and cool-down to default after a quiet window
  - implemented as a small in-memory state on the triage worker, persisted to `Bucket.window_length_ms` for replay

### Resolving `in_reply_to_alert_id`

Triage worker resolves in this order:
1. App-channel messages carry `alert_id` in the WS payload.
2. SMS-channel messages: `To` Twilio number maps to (NGO, alert_id) via a `TwilioRoute` lookup table populated when the alert was broadcast.
3. Body hint (`SAW <alertcode>` or similar).
4. Recent alerts sent to the sender's phone (within last 24h).
5. If still ambiguous → `in_reply_to_alert_id = "unresolved"`. The agent's special "unresolved" bucket asks the sender to clarify.

---

## 8. Cross-component coordination

### Worker wake-up: pub/sub, not polling

Two backends behind one in-process `EventBus` interface, picked at startup:
- **Postgres `LISTEN/NOTIFY`** (channels: `new_inbound`, `bucket_open`, `toolcalls_pending`, `suggestions_pending`, `ws_push:{account_id}`) — default; works for hackathon and any single-instance deployment.
- **Redis pub/sub** (same channel names) — for deployments with multiple API instances, where each pod needs to subscribe to events for accounts whose WS it currently holds.

Workers fall back to a 5-second poll regardless of backend (defense-in-depth against missed events).

### WS push routing in multi-instance API tier

- Each API instance subscribes to `ws_push:{account_id}` for every account whose WS it currently holds.
- Dispatcher publishes to that channel; the right instance forwards down its WS.
- Hackathon (single instance) uses the same code path with a no-op pub/sub backend, so no migration is needed when scaling out.

### Per-alert serialization

Implemented as Postgres advisory locks: `pg_try_advisory_xact_lock(hashtext('alert:' || alert_id))`. The lock is held only for the duration of the agent's multi-turn loop + decision write (typically 10–30s). On worker crash, the lock is released automatically when the connection closes.

### Backpressure visibility

The NGO console renders three live counts (queried on a 5-second interval):
- Inbound backlog (`InboundMessage` where status in `('new','triaging')`).
- Bucket backlog (`Bucket` where status='open' or `status='claimed' AND claimed_at < now - 1 min`).
- Dispatch backlog (`OutboundMessage` where status in `('queued','sending')`).

Soft backpressure on the agent: when dispatch backlog > threshold (e.g., 10,000), or when pending-suggestions backlog is overloading the operator, the agent's system prompt includes a notice and is instructed to (1) prefer `mode='suggest'` over `mode='execute'` for large sends, and (2) prefer `escalate_to_ngo` over either when the situation is genuinely ambiguous.

---

## 9. End-to-end flow (single message)

Setup: alert `A1` is active. Sara (registered, app online) sees a girl matching the photo. She taps "I saw her" in the app, attaches a pin, sends.

| Time | Node | Action |
|---|---|---|
| T+0.05s | API Tier | Validates JWT; inserts `InboundMessage(status='new')`; acks WS; publishes `new_inbound`. |
| T+0.10s | Triage Worker | Claims row; calls Haiku with structured output; checks `BadActor`; inserts `TriagedMessage`; upserts `Bucket(status='open')`; publishes `bucket_open`. |
| T+0.50s | Triage done | Bucket open with one message. |
| T+0.50s | Agent Worker | Claims bucket; acquires per-alert advisory lock for `A1`; reads context (5-way parallel query). |
| T+0.70s | Agent Worker | Calls Sonnet with full tool surface. |
| T+5.50s | Sonnet returns | 3 tool calls: `record_sighting` (mode=execute), `send(audience={type:"one", phone:Sara}, ...)` (mode=execute, single sender), `escalate_to_ngo` (mode=execute). Inserts `AgentDecision` + 3 `ToolCall` rows (all `approval_status='auto_executed'`); releases lock; publishes `toolcalls_pending`. |
| T+5.53s | Dispatcher | Picks up the `send` ToolCall (audience type=one); resolves channel = app (online); inserts `OutboundMessage`; publishes `ws_push:{Sara}`. |
| T+5.55s | API Tier | Receives pub/sub event; pushes WS frame to Sara's app. |
| T+5.58s | Sara's app | Acks delivery; status flips to `delivered`. |
| T+5.55s (parallel) | Dispatcher | escalate_to_ngo → `OutboundMessage(channel='ngo_console')` → WS push to operator dashboard, flashing card with deep link. |

End-to-end latency: ~5.6s, dominated by the ~5s Sonnet call.

---

## 10. Spike behavior (1M messages over 5 minutes)

Validated against the architecture:

| Stage | Volume | Mechanism | Outcome |
|---|---|---|---|
| API Tier | 3,300 INSERTs/s | Stateless, async, multi-instance | Sustained with 3-4 pods. No data loss. |
| Triage | 1M Haiku calls | ~30 concurrent, parallel | Drains in ~5 min. ~$100. |
| Bucketing | 1M → ~150-200 buckets | Adaptive window + region prefix | Coalescing factor ~5,000:1. |
| Agent | ~150 Sonnet calls | 5 alerts × 6 decisions/min/alert (per-alert lock) | ~150 decisions in 5 min. ~$7.50. |
| Dispatch | 150 × 5k = 750k sends | App push (free, ~30s) for 80%; SMS (rate-limited, ~5min) for 20% | ~$3,750, dominated by SMS. |

**Bottlenecks by design:**
- Agent throughput, capped by per-alert serialization. Late buckets queue.
- SMS provider rate (~500/s aggregate). Push has no practical cap.
- **Operator approval throughput** under spike: with default risk policy, broadcasts to >100 recipients require operator approval. In a major incident this becomes the new throttle — by design, since you don't want autonomous mass broadcasts during chaos. NGO operator can pre-authorize a region/window in standing orders ("auto-approve broadcasts up to N in geohash X for the next M minutes") to lift the throttle when warranted.

**Cost breakdown:**

| Item | Volume | Unit | Total |
|---|---|---|---|
| Triage LLM (Haiku) | 1M | $0.0001 | $100 |
| Embedding generation | 1M + ~few hundred sightings + clusters | $0.00002 | ~$20 |
| Agent LLM — bucket decisions (multi-turn, ~3 turns avg) | 150 | $0.15 | $22 |
| Agent LLM — heartbeat consolidation (5 alerts × 12/hr × 5min spike) | ~5 | $0.05 | <$1 |
| SMS sends | 150k | $0.025 | $3,750 |
| Push | 600k | $0 | $0 |
| **Total** | | | **~$3,893** |

The push-first cascade is the single largest cost lever; LLM cost is dwarfed by SMS even with multi-turn loops, embeddings, and consolidation heartbeats.

**Failure modes addressed:**
- Triage backlog → grows but doesn't lose data.
- Agent backlog → buckets queue, processed in order, late but not dropped.
- Dispatch backlog → visible to NGO console, soft backpressure on agent.
- Suggestions backlog (operator overwhelmed) → visible to operator, soft backpressure on agent's bias toward `mode='suggest'`. Standing orders can pre-authorize batches.
- Provider outage → push falls back to SMS; SMS retries; bitchat fallback for offline.
- Worker crashes → reaper resets stale claims, retry_count guards against infinite loops.

---

## 11. Adapter contracts

### SmsProvider

```python
class SmsProvider(Protocol):
    async def send(
        self,
        to: str,
        body: str,
        media: list[str] | None = None,
        idempotency_key: str | None = None,
    ) -> SendResult: ...

    def inbound_handler(self) -> ASGIApp | None:
        """Returns an ASGI app to mount, or None for sim providers
        that drive inbound through their own UI."""
```

Two implementations:
- `SimSmsProvider` — in-process; drives the simulator UI; bypasses the webhook path entirely (calls API Tier directly).
- `TwilioSmsProvider` — wraps Twilio Python SDK; mounts a `/twilio/sms` webhook handler.

### MeshTransport (existing, per the README)

The bitchat adapter follows the same pattern; out of scope for this spec.

### App push

Internal interface, not pluggable for hackathon:
```python
class AppPusher:
    async def push(self, account_id: str, payload: dict) -> PushResult: ...
```

Implementation routes via Redis `ws_push:{account_id}` pub/sub channel. The API instance holding the WS forwards.

---

## 12. NGO console

Out of scope for the matching engine internals, but its contract with the engine:

### 12.1 Reads

- `Alert`, `AgentDecision` (with reasoning_summary), `Sighting`, `OutboundMessage`, backlog counts.
- `ToolCall` rows where `approval_status='pending'` — drives the suggested actions panel.

### 12.2 Writes

- New `Alert` rows; `Alert.status` updates.
- `BadActor` rows (operator override).
- `NGO.standing_orders` text.
- Operator-initiated `ToolCall` rows (manual broadcast, etc.) with `mode='execute'`, `approval_status='auto_executed'`, `decision_id=null`.
- Approval transitions: on approve, `UPDATE ToolCall SET approval_status='approved', decided_by=?, decided_at=now`. On reject, `'rejected'`. On edit-and-approve, insert a new `ToolCall` with `revised_from_call_id` pointing to the original (which becomes `'rejected'`).

### 12.3 Live surfaces

Subscribes to a per-NGO WS channel that streams:
- new `AgentDecision` rows
- new `Sighting` rows
- new `ToolCall(approval_status='pending')` rows for the **suggested actions panel** — each card shows the agent's reasoning summary, audience preview ("would send to 4,832 phones in sv8d"), bodies in each language, and `[approve] [reject] [edit and approve]`
- backlog counts (inbound, bucket, dispatch, pending-suggestions)
- `escalate_to_ngo` notifications (separate from suggestions — these are "look at this", not "approve this")

### 12.4 What the operator decides vs what the agent decides

| The agent decides autonomously | The operator decides |
|---|---|
| Single-sender replies (acks, follow-up questions) | Mass broadcasts (default >100 recipients) |
| Sighting records | Alert status changes (resolved, verified) |
| Escalations to operator | Bad-actor flags |
| No-ops (with reasoning logged) | Edits to agent-suggested bodies before approval |
| Send to small clusters of related senders (≤10) | Standing-orders changes (which then re-bias future agent decisions) |

---

## 13. Hackathon scope

What we actually build for the demo:
1. Single FastAPI process running all 4 worker nodes as asyncio tasks + a tiny heartbeat scheduler task.
2. Postgres + pgvector via `docker-compose` (one extra container).
3. `SimSmsProvider` only; no Twilio.
4. App simulator (browser tabs acting as registered phones).
5. **Triage** uses bare `anthropic` Python client → Haiku classification + structured output, plus an embedding call (`voyage-3-lite` or `text-embedding-3-small`).
6. **Agent Worker** uses `claude-agent-sdk` Python (≥ 0.2.111) → `ClaudeSDKClient` persistent per worker, custom tools registered via `create_sdk_mcp_server`, `setting_sources=[]`, `permission_mode="bypassPermissions"`, `max_turns=8`, `max_budget_usd=0.50`, hooks for idempotency + audit. Sonnet primary, Opus fallback.
7. Full agent action surface: comms (`send`), case data (`record_sighting`), derived knowledge (`upsert_cluster`, `merge_clusters`, `upsert_trajectory`, `apply_tag`, `remove_tag`, `categorize_alert`), operator surface (`escalate_to_ngo`, `mark_bad_actor`, `update_alert_status`), audit (`noop`).
8. Heartbeat scheduler: every 5 minutes per active alert, insert a synthetic empty bucket; agent runs a consolidation pass.
9. NGO console with:
   - alert composer (incl. category + urgency on creation)
   - live decision feed (with reasoning summaries + tool-call list)
   - sighting feed
   - **map view with clustered pins** (sightings collapse into `SightingCluster` rendering) and **trajectory arrows** (active `Trajectory` lines)
   - **tag filter rail** (pick tags to filter the views)
   - suggested-actions panel (approve/reject/edit)
   - backlog counts (inbound, bucket, dispatch, pending suggestions)
   - standing-orders editor
   - manual broadcast button
10. Sim controls page: spawn N simulated phones, drag to reposition, kill nodes, drop edges.

What's out of scope for the demo:
- Real Twilio.
- Multi-instance API tier.
- Redis pub/sub (use Postgres `LISTEN/NOTIFY` for hackathon).
- Multi-NGO operator UI (schema supports it; UI doesn't).
- Bitchat real BLE transport (stretch).
- Tag taxonomy governance (operator can rename/merge tags from console — stretch).

---

## 14. Open questions to resolve during build

1. **Sighting deduplication across buckets:** the agent uses `search(entity='sighting', query=new_message.body, filters={alert_id, time_start: now-30min})` before deciding whether to call `record_sighting`. Default: record only when similarity below ~0.85 cosine. Validate during build.
2. **Bad-actor signal source:** what evidence rises to `mark_bad_actor`? Trust score thresholds, sender-history heuristics, or NGO operator review?
3. **Standing-order grammar:** how does an NGO operator express "don't broadcast at night" or "auto-ack high-confidence sightings"? Free text in the prompt is the simplest first answer.
4. **Retrieval-tool token budget:** what's the right `top_k` default per tool, and should results be truncated by character count to prevent prompt explosion? Start with `top_k=10` and 200-char body truncation per result; tune from telemetry.
5. **Tag taxonomy governance:** the agent creates new tag names freely, which risks fragmentation (`vehicle_seen` / `vehicle_sighting` / `saw_vehicle`). Mitigation: before creating a new tag, the agent should `search(entity='tag_assignment', filters={tag_name: candidate})` to check for similar existing tags. Operator gets a "merge tags" action in the console. Decide in build whether to enforce a starter taxonomy seeded by the NGO.
6. **Cluster membership exclusivity:** a sighting should belong to at most one *active* cluster. Enforced in app logic on `upsert_cluster`/`merge_clusters` rather than DB constraint (since `sighting_ids` is a JSON column for fast reads). Add a check in the worker.
7. **Provisional category vs `Alert.category`:** `categorize_alert` defaults to `suggest`, so `Alert.category` may be null at start. Downstream policy that depends on category should treat null as "default policy". The agent can `apply_tag(entity='alert', tag_name='provisional_category=missing_child')` as a non-binding hint while waiting for operator approval.
8. **Heartbeat cadence vs active-alert count:** with 50+ active alerts, 5-minute heartbeats means 600 agent runs/hr just for consolidation. May need adaptive cadence: short heartbeats for hot alerts, longer for quiet ones. Quiescence detection (no new sightings in 30 min → cadence drops to 30 min) is a simple first heuristic.
9. **SDK parallel tool execution (verify in code).** Anthropic's API supports multiple `tool_use` blocks per assistant turn (parallel tool calls). The Agent SDK docs are silent on whether the SDK preserves this — i.e., when the agent emits 3 parallel `search` calls, are they executed concurrently or sequentially? Need a smoke test before relying on it. If sequential, retrieval-heavy turns get ~3× latency; mitigation is a hook that fans out, but ideally not needed.
10. **SDK on-disk session persistence (verify in code).** `enable_file_checkpointing=False` is the default, but the underlying CLI may still write session metadata under `~/.claude/`. We want zero on-disk state — all audit lives in Postgres. Verify in a smoke test, and if needed, point `cwd` and `add_dirs` away from any persistent location, or pass `--no-session-persist` via `extra_args`.
11. **SDK system-prompt purity.** With `setting_sources=[]` and a string `system_prompt`, the SDK should send exactly our prompt with no Claude Code preset injected. Verify by inspecting the first `SystemMessage` of an `init` event for the actual prompt the CLI assembled. Catch any silent additions early.

These are agent-prompt-level, policy, and SDK-verification concerns; deferred to implementation.

---

## 15. Testing strategy

- **Protocol unit tests:** envelope sign/verify, dedup, TTL, bucket key computation, idempotency key collision behavior.
- **SimMesh propagation:** 5-node line; ALERT reaches end, SIGHTING returns.
- **Triage golden tests:** fixed inputs → expected `(classification, geohash, language)` outputs (LLM stubbed); embedding shape sanity check (length, normalization).
- **Agent golden tests:** fixed bucket + context → expected tool call shape (LLM stubbed); multi-turn replay test (given the same `turns JSON`, regenerating produces identical action calls).
- **Retrieval-tool tests:** `search` returns expected ranking on seeded data per entity (incl. cluster, trajectory, tag_assignment); structured filters (`alert_id`, `geohash_prefix`, `radius_km`, `time_*`, `status`, `tag_name`) honored; cross-filter conjunction correctness; invalid-filter validation errors; `top_k` truncation; `get` returns full record incl. truncated fields.
- **Cluster/tag/trajectory tests:** `upsert_cluster` creates new vs updates existing by id; `merge_clusters` redirects sources to target and recomputes centroid; `apply_tag` is idempotent (re-applying same tag is a no-op due to UNIQUE); `Tag` row created lazily on first use; `upsert_trajectory` extends points correctly; cluster-membership exclusivity check rejects double-membership.
- **Heartbeat tests:** scheduler inserts one synthetic bucket per active alert per cadence; agent on empty bucket reads consolidation context and emits `noop` or update tool calls; per-alert lock prevents heartbeat from running concurrently with a real bucket.
- **SDK smoke tests** (run once during build, not part of CI): verify (a) parallel tool calls — agent emits two `search` calls in one turn, both execute concurrently and both results return before the next agent turn; (b) on-disk state — after a full decision run, no files have been written under the configured `cwd` or `~/.claude/`; (c) system-prompt purity — the SDK's `init` `SystemMessage` shows exactly the string we passed in `system_prompt`, with no Claude Code preset content injected.
- **Dispatcher tests:** channel cascade selection per recipient state; provider rate-limit honoring; idempotency on retries.
- **Reaper test:** stale claim → reset → retry up to N → dead-letter.
- **End-to-end demo script** (per existing README §Verification): NGO composes alert → mesh propagation → phone replies → sighting reaches NGO → operator acknowledges; node-kill resilience.

---

## 16. Build sequence (revised from README)

The README's existing 9-step sequence still applies. The matching engine introduces these inserts:

| Original step | Matching-engine insert |
|---|---|
| 2. Protocol module | Add `InboundMessage` envelope, `bucket_key` helpers. |
| 3. SimMesh | Unchanged. |
| 4. Orchestrator | Replace with the 4-stage pipeline (API tier writes Inbound; Triage worker on bare `anthropic` client with embedding generation; Agent worker on `claude-agent-sdk` ≥ 0.2.111 with `ClaudeSDKClient` persistent per worker, custom tools via `create_sdk_mcp_server`, hooks for idempotency+audit, multi-turn retrieval loop and full action surface incl. clusters/tags/trajectories; Dispatcher). Add heartbeat scheduler. Add smoke tests for SDK parallel-tool-call execution and on-disk-state suppression. |
| 5. NGO dashboard | Add agent-decision feed, suggested-actions panel (approve/reject/edit), backlog counts, standing-orders editor, **clustered map view, trajectory arrows, tag filter rail**. |
| 6. Phone simulator | Add WS-attached "I saw her" reply path that hits the API tier as `channel='app'`. |
| 7. Sim controls | Unchanged. |
| 8. Polish | Add adaptive bucket window + reaper + backpressure UI + retrieval-tool telemetry + tag-merge UI for operators. |
| 9. Stretch BitchatBLE | Unchanged. |
