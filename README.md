# Matching Engine

> A P2P amber-alert matching engine for NGOs operating in low-connectivity warzones. Civilian sightings come in over SMS / app push / Bitchat BLE mesh; an LLM-driven agent loop decides what to do per region, per alert; outbound replies and broadcasts go out over the same channels in reverse, push-first.

This repo is the **server-side matching engine** — the central NGO node. It is channel-agnostic at the agent layer with transport adapters at the edges, designed to absorb 1M messages over 5 minutes without data loss and to remain fully auditable and replayable from the database alone.

**Status:** active build. Plan 1 (foundation: schema, migrations, models, FastAPI skeleton, JWT auth, EventBus, SimSmsProvider) is in progress on the `matching-engine` branch. Plans 2–N (inbound pipeline, triage worker, agent worker, dispatcher, NGO console) follow.

---

## Read for humans — executive summary

### The problem

NGOs broadcasting "missing person" (amber) alerts in conflict zones face three compounding problems:

1. **Civilians have intermittent or no connectivity.** Cellular gets cut, internet is sparse, but Bluetooth-mesh apps like Bitchat let phones gossip messages hop-by-hop without infrastructure.
2. **Inbound is a flood, not a trickle.** A high-profile alert can produce thousands of "I think I saw her" replies across hundreds of locations within minutes — most are noise, some are the case.
3. **One operator cannot triage that volume in real time.** Mass broadcasts are too risky to fully automate (false positives erode trust); pure-manual triage doesn't scale.

### The solution

A four-stage pipeline that turns floods of inbound civilian messages into a small number of well-reasoned, auditable agent decisions, with the human operator in the loop only where it matters:

```
Inbound channels  →  API Tier  →  Triage Worker  →  Bucket queue  →  Agent Worker  →  ToolCall queue  →  Outbound Dispatcher  →  Outbound channels
                     (mailroom)   (cheap LLM)       (coalescing)     (main LLM)        (intent rows)     (provider calls)
```

- **Per-message inbound, per-bucket agent.** Many messages collapse into one decision via `(alert_id, geohash_prefix, time_window)` buckets. ~5,000:1 coalescing under spike load.
- **Two-tier LLM cost profile.** Cheap Haiku-class model for triage (classify, geocode, dedupe). Sonnet/Opus for the agent loop (reason, decide, act).
- **Channel-agnostic agent.** The agent never knows whether a message arrived over SMS, app push, or Bitchat. Adapters live at the edges.
- **Push-first cascade.** Outbound prefers app push (free, instant), falls back to SMS (paid, rate-limited), then Bitchat (offline mesh, last resort).
- **DB-as-bus.** Every contract between components is a Postgres table. No RPC. Every component is restartable, replayable, and auditable from the database alone.
- **Execute vs suggest.** Low-risk actions (single-sender ack, sighting record) auto-execute. Mass broadcasts and policy changes route to the operator console for approve/reject/edit.

### Why it is interesting

- **Spike-handling primitive that actually works.** The bucket coalesces 1M inbound messages into ~150 agent decisions in 5 minutes for ~$24 of LLM spend (SMS sends still dominate cost at ~$3.7k).
- **Full audit trail by construction.** Every agent decision stores its full multi-turn conversation (`turns JSON`); idempotency keys at every queue boundary; reaper handles stale claims; replays are exact.
- **Multi-tenant from day one.** Every table carries `ngo_id`. Single-NGO runtime, multi-NGO schema — cheap to keep, expensive to backfill.
- **Hackathon-shaped, production-shaped code.** All four worker nodes run as asyncio tasks in one FastAPI process for the demo. Splitting them into separate deployments is a config change, not a rewrite. Postgres + pgvector + `LISTEN/NOTIFY` + advisory locks from day one — no SQLite half-step.

### Demo (target)

NGO operator composes an alert from a web console. Alert broadcasts to a region. Civilians reply over a simulated mesh. The agent clusters sightings on a map, draws inferred trajectory arrows, and surfaces "approve a broadcast to 4,832 phones in geohash sv8d?" suggestions to the operator. Operator approves. Outbound flows back out the same channels.

**Money shot:** kill a node mid-broadcast, watch the gossip find an alternate path; flood the inbound and watch the agent stay calm because the bucket coalesces it.

### Repo layout (high-level)

```
.
├── server/             # FastAPI app + workers (asyncio tasks)
├── alembic/            # DB migrations (one per schema-task in Plan 1)
├── db/                 # init.sql (pgvector extension, test DB)
├── docker-compose.yml  # 2 services: app + db (pgvector/pgvector:pg16)
├── docs/superpowers/
│   ├── specs/          # source-of-truth design (see §1)
│   └── plans/          # task-by-task implementation plans
├── tests/              # pytest, one test file per domain
└── web/                # NGO console (React/Vite, partially the old prototype — being rebuilt against new API)
```

### Quick start

```bash
# 1. bring up Postgres + pgvector
docker compose up -d db

# 2. install deps + run migrations
uv sync
uv run alembic upgrade head

# 3. run the FastAPI app
uv run uvicorn server.main:app --reload --port 8080

# 4. (separate terminal) frontend
cd web && npm install && npm run dev
# open http://localhost:5173
```

Or fully in Docker once the app image is wired up:

```bash
docker compose up --build
```

`.env.example` documents the required env vars: `DATABASE_URL`, `TEST_DATABASE_URL`, `JWT_SECRET`, `ANTHROPIC_API_KEY`.

---

## Read for agents — technical reference

> Source of truth is `docs/superpowers/specs/2026-04-25-matching-engine-design.md` (the design spec) and `docs/superpowers/plans/2026-04-25-foundation.md` (Plan 1, foundation). Read those before changing anything load-bearing. This section is a fast index, not a replacement.

### 1. Architecture — five nodes, four DB-coupled stages

| # | Node | LLM? | Stateless? | Scales with | Output |
|---|---|---|---|---|---|
| 1 | API Tier (mailroom) | no | yes (WS sticky) | inbound conn count | `InboundMessage` rows, ack to caller |
| 2 | Triage Worker | yes — Haiku-class | yes | inbound msg rate | `TriagedMessage` + `Bucket` rows |
| 3 | Agent Worker | yes — Sonnet/Opus | yes (idempotent) | bucket rate, cost-bound, capped 1-per-alert via advisory lock | `AgentDecision` + `ToolCall` rows |
| 4 | Outbound Dispatcher (courier) | no | yes (idempotent) | provider quotas | `OutboundMessage` rows + provider sends |
| 5 | Data Tier | n/a | stateful | data volume | the truth, the audit log, the vector store |

**Hackathon collapse:** all four worker nodes run as asyncio tasks inside the single FastAPI process; the data tier is a `pgvector/pgvector:pg16` container. One `docker compose up` brings the backend up.

**Heartbeat scheduler:** a periodic asyncio task inserts a synthetic empty `Bucket` row every N minutes per `Alert(status='active')`, driving consolidation runs (cluster pruning, trajectory extension, contradiction surfacing). Replaceable with `pg_cron` in prod; same trigger contract.

**Worker wake-up:** Postgres `LISTEN/NOTIFY` channels (`new_inbound`, `bucket_open`, `toolcalls_pending`, `suggestions_pending`, `ws_push:{account_id}`) behind an `EventBus` Protocol. Redis pub/sub is the multi-instance swap; same channel names. 5-second poll fallback either way.

**Per-alert serialization:** Postgres advisory lock `pg_try_advisory_xact_lock(hashtext('alert:' || alert_id))`. Held for the agent's multi-turn loop + decision write (10–30s). Released automatically on connection drop.

### 2. Component contracts (read this before touching a worker)

#### 2.1 API Tier
- Owns external connections: Twilio webhook, app WSS, NGO operator browser.
- Authenticates (Twilio signature / app JWT / NGO operator session), inserts `InboundMessage(status='new')`, acks fast (Twilio retries above ~10s).
- Does not classify, dedupe, geohash, or call any LLM. **Stupid mailroom.**

#### 2.2 Triage Worker
- **LLM client:** bare `anthropic` Python SDK (not the Agent SDK). One `messages.create()` per message with a single tool defined to enforce JSON-schema output. Model: `claude-haiku-4-5-20251001`.
- **Output schema:** `{classification, geohash6, geohash_source, confidence, language, dedup_hash}`.
- **Embedding:** `voyage-3-lite` or `text-embedding-3-small`, 512 dims, stored on `TriagedMessage.body_embedding` for later semantic retrieval.
- **Output:** `TriagedMessage` row + `Bucket(status='open')` upsert + `bucket_open` notify.
- **Why separate from API tier:** webhook budget vs LLM latency.
- **Why separate from Agent worker:** different cost profile, model, rate-limit pool, scaling axis.

#### 2.3 Agent Worker
- **LLM client:** `claude-agent-sdk` Python (≥ 0.2.111 for Opus 4.7). One persistent `ClaudeSDKClient` per worker for the lifetime of the worker; per-decision `session_id = bucket_key`.
- **Configuration:**
  - `setting_sources=[]` (no `.claude/`, `CLAUDE.md`, or skills loading)
  - `permission_mode="bypassPermissions"` (we gate via DB, not interactive prompts)
  - `system_prompt` = full string we control
  - `max_turns=8`, `max_budget_usd=0.50`
  - `model="claude-sonnet-4-6"`, `fallback_model="claude-opus-4-7"`
  - `enable_file_checkpointing=False`
  - tools registered via `create_sdk_mcp_server(name="matching", tools=[...])`
- **Hooks:**
  - `PreToolUse(matcher="mcp__matching__*")`: idempotency check — `idempotency_key = sha256(bucket_key || tool_name || canonical_json(args))`. Short-circuit duplicates with prior result.
  - `PostToolUse(matcher="mcp__matching__*")`: append `(tool_use_id, name, args, result, latency)` into the in-progress `turns JSON` for the `AgentDecision` row.
- **Concurrency:** N worker tasks (default 8), each holding one persistent client. Per-alert advisory lock prevents two concurrent buckets for the same alert from independently broadcasting similar follow-ups.
- **Lifecycle:** wrap the loop in a watchdog catching `ProcessError` / `CLIConnectionError`; on subprocess death, recreate the `ClaudeSDKClient` and release the bucket back (`status='open'`, `retry_count++`). Reaper handles dead-lettering after retry cap.
- **Multi-turn loop (max 8 turns):** retrieve → reason → retrieve → reason → … → action tool calls or `noop`. If turn cap hits without action: force one final turn ("Decide now"). If still nothing: synthetic `noop(reason='turn_cap_reached')`.

#### 2.4 Outbound Dispatcher
- No LLM. Pure orchestration.
- Claims `ToolCall` rows where `status='pending' AND approval_status IN ('auto_executed','approved')`.
- For `send`: resolves the audience selector (`one` / `many` / `region` / `all_alert` / `all_ngo`), picks channel via cascade (app push → SMS → Bitchat), inserts `OutboundMessage` rows, sends via rate-limited token bucket per provider, tracks delivery via WS ack (push) or webhook (SMS).
- For internal-only tool calls (`record_sighting`, `update_alert_status`, `mark_bad_actor`, `escalate_to_ngo`): writes to the relevant table, no provider call.
- Idempotency keys forwarded to providers (e.g., Twilio) so crash recovery doesn't double-send.

#### 2.5 Data Tier
- Postgres ≥ 16 + `pgvector` extension. Geohashes are `TEXT` with `text_pattern_ops` B-tree indices for prefix `LIKE`. Vectors use HNSW indices for ANN. PostGIS not required.

### 3. Agent tool surface

Two categories. **Action tools** produce side effects, emit `ToolCall` rows, and end the multi-turn loop. **Retrieval tools** are read-only and free to call mid-loop within the turn cap.

#### Action tools — twelve total
- **Comms:** `send(audience, bodies, mode)` — single dispatch primitive; audience selector resolved by Dispatcher.
- **Case data:** `record_sighting(alert_id, observer_phone, geohash, notes, confidence, photo_urls[])`.
- **Derived knowledge:** `upsert_cluster`, `merge_clusters`, `upsert_trajectory`, `apply_tag`, `remove_tag`, `categorize_alert`.
- **Operator surface:** `escalate_to_ngo(reason, summary, attached_message_ids[])`, `mark_bad_actor(phone, reason, ttl_seconds)`, `update_alert_status(alert_id, status, reason)`.
- **Audit:** `noop(reason)` — explicit "do nothing", still recorded.

Every action carries a `mode` field (`execute` or `suggest`). Defaults: most derived-knowledge tools execute (recoverable). `categorize_alert`, `mark_bad_actor`, `update_alert_status` default to `suggest` (cascades, requires sign-off). `send` defaults vary by audience size — `one` and small-cluster `many` execute; `all_alert` / `all_ngo` always suggest.

#### Retrieval tools — two unified
- `search(entity, query?, filters, sort, top_k=10)` — covers messages, sightings, decisions, clusters, trajectories, tag_assignments. Semantic ranking via pgvector HNSW when `query` is set; otherwise sorts by recency / confidence / geo_distance / size. Filters that don't apply to the chosen entity return a structured error so the agent learns the correct shape.
- `get(entity, id)` — PK lookup escape hatch returning the full record incl. fields normally truncated in `search` results.

**Outbound is intentionally not searchable** — prevents loops where the agent reasons over its own past sends. System outbound is visible via the recent-decisions context (which contains prior `tool_calls` JSON).

### 4. Approval state machine (every `ToolCall` row)

```
mode='execute'  →  approval_status='auto_executed'  →  dispatcher claims immediately
mode='suggest'  →  approval_status='pending'        →  shows in NGO console
                   on operator approve              →  'approved'  →  dispatcher claims
                   on operator reject               →  'rejected'  →  no send, audit retained
                   on auto-expire (default 1h)      →  'expired'   →  no send, audit retained
```

Operator-edit-and-approve creates a new `ToolCall` linked via `revised_from_call_id`; the original becomes `'rejected'`.

### 5. Data model — 16 tables

All tables carry `ngo_id` FK. ULID PKs unless noted. Created/updated timestamps assumed everywhere.

| Table | Purpose |
|---|---|
| `NGO` | tenant, region, standing orders, operator pubkey |
| `Account` | civilian phone identity (registered or seeded), trust score, push token, last-known geohash |
| `Alert` | active case; carries `category`, `urgency_tier`, `urgency_score`, region |
| `AlertDelivery` | denormalized roster of who received which alert |
| `InboundMessage` | raw inbound from any channel (queue: `new`/`triaging`/`triaged`/`failed`) |
| `TriagedMessage` | classified + geohashed + embedded; `bucket_key` set |
| `Bucket` | coalescing primitive (queue: `open`/`claimed`/`done`/`failed`) |
| `AgentDecision` | one per claimed bucket; full `turns JSON` for replay |
| `ToolCall` | every action-tool invocation; UNIQUE on `idempotency_key`; `mode` + `approval_status` lifecycle |
| `OutboundMessage` | one per recipient per send; channel-cascade traceable via `previous_out_id` |
| `Sighting` | structured case data with `notes_embedding` |
| `BadActor` | dropped at triage; TTL'd |
| `SightingCluster` | derived knowledge: location/time-coherent groups of sightings; `embedding` is centroid |
| `Trajectory` | inferred path with `points`, direction, speed |
| `Tag` | namespaced free-form taxonomy (`message`/`sighting`/`sender`/`alert`/`cluster`) |
| `TagAssignment` | idempotent (`UNIQUE(tag_id, entity_type, entity_id)`) |

**Hot-path indices** (verbatim from the spec — see §6 of the design doc): geohash prefix `text_pattern_ops`, status partial indices for queue tables, HNSW on every embedding column, idempotency-key UNIQUE on `ToolCall`.

**Reaper job:** every 60s, any row with `status='claimed' AND claimed_at < now - 5 min` resets to its open state and `retry_count++`. After 3 retries → `status='failed'` and surfaces to the NGO console.

### 6. Bucket key

```
bucket_key = "{alert_id}|{geohash_prefix_4}|{window_iso}"
```

- `geohash_prefix_4`: ~20km cell. Coarse enough that "near the bakery" reports cluster, fine enough that Tel Aviv and Haifa don't merge.
- `window_start`: floor of `received_at` to a window length. Adaptive: default 3s; doubles up to 30s if a bucket exceeded 100 messages last window for the same `(alert_id, geohash_prefix_4)`. Cooldown back to default after a quiet window. State persists to `Bucket.window_length_ms` for replay.

`in_reply_to_alert_id` resolution order: app-channel `alert_id` in WS payload → Twilio `To`-number → body hint (`SAW <alertcode>`) → recent alerts to sender's phone (24h) → `"unresolved"` (special bucket asks for clarification).

### 7. Tech stack (current state, post-Plan 1 in progress)

- **Python 3.12+**, FastAPI 0.110+, uvicorn
- **SQLAlchemy 2.0 async** + asyncpg
- **alembic** for migrations (one revision per schema-task)
- **pgvector** Python package + `pgvector/pgvector:pg16` Docker image
- **pydantic-settings** for config, **python-ulid** for PKs
- **python-jose + passlib** for NGO operator JWT auth
- **anthropic** (bare client) for triage
- **claude-agent-sdk** ≥ 0.2.111 for the agent worker
- **pytest + pytest-asyncio + httpx** for tests; **ruff** for lint
- **uv** for package management

### 8. File layout (target — Plan 1)

```
anth-hackathon26/
├── docker-compose.yml             # 2 services: app + db (pgvector/pgvector:pg16)
├── pyproject.toml                 # all deps, pytest config, ruff config
├── alembic.ini
├── .env.example
├── db/
│   └── init.sql                   # creates pgvector ext + matching_test DB
├── server/
│   ├── main.py                    # FastAPI app entry
│   ├── config.py                  # Settings (pydantic-settings)
│   ├── db/
│   │   ├── engine.py              # async engine + session_maker
│   │   ├── session.py             # FastAPI Depends(get_db)
│   │   ├── base.py                # Base + ULID PK mixin + JSONB type alias
│   │   ├── identity.py            # NGO, Account
│   │   ├── alerts.py              # Alert, AlertDelivery
│   │   ├── messages.py            # InboundMessage, TriagedMessage, Bucket
│   │   ├── decisions.py           # AgentDecision, ToolCall
│   │   ├── outbound.py            # OutboundMessage, Sighting
│   │   ├── knowledge.py           # SightingCluster, Trajectory, Tag, TagAssignment
│   │   └── trust.py               # BadActor
│   ├── eventbus/
│   │   ├── base.py                # EventBus Protocol
│   │   └── postgres.py            # PostgresEventBus (LISTEN/NOTIFY)
│   ├── transports/
│   │   ├── sms_base.py            # SmsProvider Protocol + SendResult
│   │   └── sim_sms.py             # SimSmsProvider in-process impl
│   ├── auth/
│   │   └── ngo.py                 # JWT issue + verify, password hash
│   └── api/
│       └── health.py              # GET /health
├── alembic/versions/              # one file per task (migrations)
└── tests/                         # one test file per domain
```

Plans 2+ add: `triage/`, `agent/` (with `tools/`, `prompts/`, `hooks/`), `dispatcher/`, additional `api/` routers, `web/` rebuild against the new API.

### 9. Build sequence

Plans live in `docs/superpowers/plans/`. Each plan is task-by-task with checkbox steps; execute via the `superpowers:executing-plans` or `superpowers:subagent-driven-development` skills.

| Plan | Scope | Status |
|---|---|---|
| 1 — Foundation | Postgres + pgvector compose, FastAPI skeleton, all 16 SQLAlchemy models + alembic revisions, EventBus & SmsProvider Protocols + first impls, NGO operator JWT auth | in progress (current branch: `matching-engine`) |
| 2 — Inbound pipeline | API tier ingress endpoints, channel adapters, WS hub, ack semantics | not started |
| 3 — Triage worker | Bare `anthropic` client, classification + embedding, Bucket coalescing, BadActor gate | not started |
| 4 — Agent worker | `claude-agent-sdk` integration, tool surface, hooks (idempotency + audit), per-alert advisory lock, multi-turn retrieval loop, heartbeat scheduler | not started |
| 5 — Outbound dispatcher | Channel cascade, audience resolution, rate-limited token buckets, `OutboundMessage` lifecycle | not started |
| 6 — NGO console | Live decision feed, suggested-actions panel (approve/reject/edit), clustered map, trajectory arrows, tag filter, standing-orders editor, backlog counts | not started |

### 10. Running and testing

```bash
# bring up DB
docker compose up -d db

# install (uses uv.lock)
uv sync

# migrate
uv run alembic upgrade head

# tests (pytest-asyncio, full DB available; expects matching_test DB seeded by db/init.sql)
uv run pytest -v

# app
uv run uvicorn server.main:app --reload --port 8080
```

**Test layout convention:** one test file per domain module (`test_models_identity.py`, `test_models_alerts.py`, …). Smoke tests (`test_smoke.py`, `test_e2e_foundation.py`) gate import-correctness and full-stack boot.

Plan-specific golden tests:
- Triage: fixed inputs → expected `(classification, geohash, language)` with LLM stubbed; embedding shape sanity.
- Agent: fixed bucket + context → expected tool-call shape with LLM stubbed; multi-turn replay test (same `turns JSON` → identical action calls).
- Retrieval: structured-filter conjunction correctness, invalid-filter validation errors, `top_k` truncation, `get` returns full record incl. truncated fields.
- SDK smoke (run once during build, not part of CI): parallel tool-call concurrency, on-disk-state suppression, system-prompt purity.

### 11. Operating envelope (validated against the spec, not yet measured)

Target spike: **1M messages over 5 minutes**.

| Stage | Volume | Mechanism | Outcome |
|---|---|---|---|
| API Tier | 3,300 INSERTs/s | stateless, async, multi-instance | sustained with 3–4 pods |
| Triage | 1M Haiku calls | ~30 concurrent | drains in ~5 min, ~$100 |
| Bucketing | 1M → ~150–200 buckets | adaptive window + region prefix | coalescing factor ~5,000:1 |
| Agent | ~150 Sonnet calls | 5 alerts × 6 decisions/min/alert (per-alert lock) | ~150 decisions in 5 min, ~$22 (multi-turn ~3 avg) |
| Dispatch | ~750k sends | push (free) for 80%, SMS (rate-limited) for 20% | ~$3,750, dominated by SMS |

Bottlenecks by design: agent throughput is per-alert serialized; SMS provider rate (~500/s aggregate); operator approval throughput under spike (broadcasts >100 recipients are operator-gated by default). Standing orders pre-authorize regions/windows to lift the throttle when warranted.

### 12. Pointers

- **Spec:** `docs/superpowers/specs/2026-04-25-matching-engine-design.md` — full architecture, every contract, every open question.
- **Plan 1:** `docs/superpowers/plans/2026-04-25-foundation.md` — task-by-task foundation.
- **Original Bitchat README context:** captured in the spec's §1; the bitchat BLE transport remains a stretch goal at the edge.

### 13. Open questions (deferred to implementation)

Tracked in §14 of the spec. The load-bearing ones for Plan 4 (agent worker):

1. **Sighting deduplication threshold** — default cosine similarity < 0.85 for `record_sighting`; validate during build.
2. **Bad-actor signal source** — trust thresholds vs sender-history vs operator review.
3. **Standing-order grammar** — free text in the prompt is the v0 answer.
4. **Retrieval token budget** — `top_k=10`, 200-char body truncation per result; tune from telemetry.
5. **Tag taxonomy governance** — agent searches existing tags before creating new; operator gets a "merge tags" action.
6. **Cluster membership exclusivity** — enforced in worker logic, not DB constraint.
7. **Heartbeat cadence vs active-alert count** — adaptive cadence based on quiescence detection.
8. **SDK smoke-test verifications** — parallel tool-call concurrency, no on-disk session state, system-prompt purity. Run once before relying on each.

---

## Conventions

- **Skills-driven workflow.** Plans are written for the `superpowers:executing-plans` and `superpowers:subagent-driven-development` skills. Each task has explicit checkbox steps.
- **TDD where it matters.** Every domain has a failing test before implementation; protocol-shaped contracts (EventBus, SmsProvider) ship with their first concrete implementation.
- **No half-steps.** Postgres + pgvector + advisory locks + `LISTEN/NOTIFY` from day one — we don't run on SQLite and migrate later.
- **Multi-tenant schema, single-tenant runtime.** `ngo_id` everywhere; one NGO live in the demo.
- **Audit by construction.** `AgentDecision.turns JSON` carries the full multi-turn conversation; idempotency keys at every queue boundary; `ToolCall.revised_from_call_id` traces operator edits.
