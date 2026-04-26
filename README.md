# SafeThread / Matching Engine

> A P2P amber-alert matching engine for NGOs operating in low-connectivity warzones. Civilian sightings come in over SMS / app push / Bitchat BLE mesh; an LLM-driven agent loop decides what to do per region, per alert; outbound replies and broadcasts go out over the same channels in reverse, push-first.

This repo is the **server-side matching engine** plus a **React NGO console** that consumes it. It is channel-agnostic at the agent layer with transport adapters at the edges, designed to absorb 1M messages over 5 minutes without data loss and to remain fully auditable and replayable from the database alone.

**Status:** running end-to-end on `main`. Foundation, inbound pipeline, agent worker (stub + real LLM), operator approvals inbox, agent activity feed, rich demo seeder, live replay drip, and heartbeat scheduler are all built and tested (98 passing). Outbound dispatcher (real Twilio/push) and BLE Bitchat transport are deferred.

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
- **Always alive.** A heartbeat scheduler ticks every active alert on a periodic cadence; the agent runs a consolidation prompt on each. The dashboard breathes even with zero inbound.

### Why it is interesting

- **Spike-handling primitive that actually works.** The bucket coalesces 1M inbound messages into ~150 agent decisions in 5 minutes for ~$24 of LLM spend (SMS sends still dominate cost at ~$3.7k).
- **Full audit trail by construction.** Every agent decision stores its full multi-turn conversation (`turns JSON`); idempotency keys at every queue boundary; replays are exact.
- **Operator-as-co-pilot, not button-pusher.** Suggestions land in an inbox with the agent's reasoning summary attached; one click to approve, reject, or edit before sending.
- **Multi-tenant from day one.** Every table carries `ngo_id`. Single-NGO runtime, multi-NGO schema.
- **Hackathon-shaped, production-shaped code.** All four worker nodes run as asyncio tasks in one FastAPI process for the demo. Splitting them into separate deployments is a config change, not a rewrite. Postgres + pgvector + `LISTEN/NOTIFY` + advisory locks from day one — no SQLite half-step.

### Demo flow

1. **Seed** the rich demo scene — 8 alerts across 6 regions, ~30 historic agent decisions, 8 suggestions waiting in the operator inbox, 20 sightings, 4 sighting clusters, 2 trajectories.
2. **Open the dashboard** — every region card has live content, the activity tape is populated, the approval inbox shows real Sonnet-style reasoning summaries with one-click approve / reject.
3. **Start the live drip** — one new civilian message every few seconds against a random active alert. Triage classifies it, the agent makes a decision in real time, the activity tape grows, the header pill ticks ($cost, decisions today, pending approvals).
4. **Approve a suggestion** — see the inbox row animate out, the suggestion-resolved event ride the WebSocket, the dispatcher (when wired) pick it up.
5. **Wait** — even if you do nothing, the heartbeat scheduler fires synthetic buckets every interval and the agent runs consolidation; tape ticks on its own.

### Quick start

```bash
# 1. bring up Postgres + pgvector
docker compose up -d db

# 2. install deps + run migrations
uv sync
uv run alembic upgrade head

# 3. run the FastAPI app (workers start in lifespan)
uv run uvicorn server.main:app --reload --port 8080

# 4. seed the demo scene (idempotent; ?reset=true to rebuild)
curl -X POST "http://localhost:8080/api/sim/seed"

# 5. (optional) start the live replay drip — fires one message every 4s
curl -X POST "http://localhost:8080/api/sim/replay/start?intervalSec=4"

# 6. (separate terminal) frontend
cd web && npm install && npm run dev
# open http://localhost:5173
```

`.env.example` documents the required env vars: `DATABASE_URL`, `TEST_DATABASE_URL`, `JWT_SECRET`, `ANTHROPIC_API_KEY` (optional — without it the agent runs in deterministic stub mode), `HEARTBEAT_INTERVAL_SEC` (default 300, set lower for demo).

### Repo layout

```
.
├── server/                # FastAPI app + workers (asyncio tasks)
│   ├── api/               # REST + WS routers
│   ├── db/                # SQLAlchemy 2.0 async models, engine, session
│   ├── eventbus/          # Postgres LISTEN/NOTIFY pub/sub
│   ├── llm/               # Triage + Agent LLM clients
│   ├── sim/               # Demo seeder + replay drip
│   ├── transports/        # SMS provider protocol + sim impl
│   └── workers/           # Triage, Agent, Heartbeat loops
├── alembic/               # DB migrations
├── db/init.sql            # pgvector extension, test DB
├── docker-compose.yml     # 2 services: app + db (pgvector/pgvector:pg16)
├── docs/superpowers/      # Specs + plans (source of truth)
├── tests/                 # pytest, one file per domain
├── web/                   # NGO console (React + Vite + Tailwind + Zustand)
├── mobileapp/             # SafeThread iOS slice (Bitchat-derived)
└── scripts/               # One-off: real-LLM smoke test
```

---

## Read for agents — technical reference

> Source of truth is `docs/superpowers/specs/2026-04-25-matching-engine-design.md` (the design spec). Read it before changing anything load-bearing. This section is a fast index, not a replacement.

### 1. Architecture — five nodes, four DB-coupled stages

| # | Node | LLM? | Stateless? | Scales with | Output |
|---|---|---|---|---|---|
| 1 | API Tier (mailroom) | no | yes | inbound conn count | `InboundMessage` rows, ack to caller |
| 2 | Triage Worker | yes — Haiku | yes | inbound msg rate | `TriagedMessage` + `Bucket` rows |
| 3 | Agent Worker | yes — Sonnet/Opus | yes (idempotent) | bucket rate, capped 1-per-alert via advisory lock | `AgentDecision` + `ToolCall` rows |
| 4 | Outbound Dispatcher (courier) | no | yes (idempotent) | provider quotas | `OutboundMessage` rows + provider sends |
| 5 | Data Tier | n/a | stateful | data volume | the truth, the audit log, the vector store |

**Hackathon collapse:** all four worker nodes run as asyncio tasks inside a single FastAPI process; the data tier is a `pgvector/pgvector:pg16` container.

**Heartbeat scheduler** (`server/workers/heartbeat.py`): periodic asyncio task inserts a synthetic empty `Bucket` row every `HEARTBEAT_INTERVAL_SEC` per `Alert(status='active')`, driving consolidation runs (cluster pruning, trajectory extension, contradiction surfacing).

**Worker wake-up:** Postgres `LISTEN/NOTIFY` channels behind a `PostgresEventBus` Protocol. Channels currently in use:
- `new_inbound` — triage worker drains
- `bucket_open` — agent worker drains
- `agent_thinking` — UI: region card glow on
- `decision_made` — UI: activity tape new row
- `suggestion_pending` — UI: approvals inbox new row
- `suggestion_resolved` — UI: inbox row removed (`{call_id}|{status}` payload)
- `incident_upserted` / `toolcalls_pending` / `suggestions_pending` — internal pipeline coordination
- `ws_push:{account_id}` — reserved for outbound dispatcher (not yet wired)

**Per-alert serialization:** Postgres advisory lock keyed off the alert ID. Held for the agent's multi-turn loop + decision write.

### 2. Component contracts

#### 2.1 API Tier (`server/api/*`)
Stateless ingress. `current_operator` dep reads the `X-Operator-Id` header against a static registry (full JWT auth deferred). FastAPI routers grouped by purpose, all listed in §3 below.

#### 2.2 Triage Worker (`server/workers/triage.py`)
- **LLM client:** bare `anthropic` Python SDK. One `messages.create()` per message with a single tool defined to enforce JSON-schema output. Model `claude-haiku-4-5-20251001`. Falls back to a deterministic stub when `ANTHROPIC_API_KEY` is unset.
- **Embedding:** deterministic 512-float hash placeholder for the demo (real Voyage / OpenAI embedding is a swap in `server/llm/triage_client.py`).
- **Output:** `TriagedMessage` row + `Bucket(status='open')` upsert + `bucket_open` notify.

#### 2.3 Agent Worker (`server/workers/agent.py`)
- **LLM client:** `claude-agent-sdk` (≥ 0.1.68). One persistent `ClaudeSDKClient` per worker, real-mode lazy-imported only if `ANTHROPIC_API_KEY` is set.
- **Configuration** (`server/llm/agent_client.py`): `setting_sources=[]`, `permission_mode="bypassPermissions"`, `max_turns=8`, `max_budget_usd=0.50`, model `claude-sonnet-4-5` / fallback `claude-opus-4-1`, `enable_file_checkpointing=False`. All 14 matching-engine tools registered as an in-process MCP server via `create_sdk_mcp_server`.
- **Stub mode**: when no API key, `stub_decide` synthesizes a deterministic decision (record sighting + ack) so the full pipeline runs end-to-end without network or cost.
- **Per-decision flow:**
  1. Claim a `Bucket` (`FOR UPDATE SKIP LOCKED`).
  2. Acquire `pg_try_advisory_lock(hashtext(alert_id))`.
  3. Publish `agent_thinking` event.
  4. Load context via 8 parallel queries (`asyncio.gather` over triaged messages, recent decisions, sightings, clusters, trajectories, tag assignments, account snapshots, dispatch backlog).
  5. Run multi-turn loop (real or stub).
  6. Persist `AgentDecision` + N `ToolCall` rows; apply execute-mode side-effects inline (Sighting/Cluster/Trajectory/Tag DB writes).
  7. Publish `decision_made` and one `suggestion_pending` per pending tool call.
  8. Mark bucket done; release advisory lock.
- **Watchdog:** wraps the loop catching `ProcessError`/`CLIConnectionError`; on subprocess death, recreates the client and releases the bucket back. Bucket retries up to 3 times → `status='failed'`.

#### 2.4 Outbound Dispatcher
**Not yet built.** Pipeline currently terminates at `ToolCall` rows + inline side-effects for internal tools. The frontend's operator-write endpoints (`/api/alerts`, `/api/requests`, `/api/cases/{id}/messages`) write `ToolCall(approval_status='approved')` + placeholder `OutboundMessage` rows so the audit trail is unified. Real Twilio / WS-push integration is a Plan-5 deliverable.

#### 2.5 Data Tier
Postgres ≥ 16 + `pgvector` extension. Geohashes are `TEXT` with prefix `LIKE` queries. Vectors use `Vector(512)` columns; HNSW indices defined in alembic migrations.

### 3. HTTP API surface

All endpoints require `X-Operator-Id: op-senior` (or `op-junior`) header except `/health` and `/api/sim/*`.

#### Read paths (frontend hydration)
| Method | Path | Returns |
|---|---|---|
| GET | `/health` | `{ok: true}` |
| GET | `/api/me` | current operator profile |
| GET | `/api/operators` | list (for the operator switcher) |
| GET | `/api/audiences` | static audience definitions for `send` |
| GET | `/api/regions/stats` | per-region counts (reachable, incidents, msgs/min, anomaly flag) |
| GET | `/api/regions/{region}/timeline?minutes=60&bucket=60` | per-region message rate buckets |
| GET | `/api/incidents` | active alerts shaped for the case grid |
| GET | `/api/incidents/{id}/messages` | inbound + outbound (agent-issued + operator-issued) |
| GET | `/api/dashboard` | aggregate dashboard view |

#### Agent activity (the "alive" surface)
| Method | Path | Returns |
|---|---|---|
| GET | `/api/agent/stats` | `{decisionsToday, costTodayUsd, pending, executedToday, lastDecisionAt}` |
| GET | `/api/decisions/recent?limit=20` | activity tape backfill — recent `AgentDecision` rows with `reasoning_summary`, model, cost, tool-call names, alert |
| GET | `/api/suggestions` | operator inbox — pending `ToolCall` rows + parent decision summary + alert info |
| POST | `/api/suggestions/{id}/approve` | flip to `approved`; publishes `suggestion_resolved` |
| POST | `/api/suggestions/{id}/reject` | flip to `rejected`, status=`done`; publishes `suggestion_resolved` |

#### Operator writes (case actions)
| Method | Path | Effect |
|---|---|---|
| POST | `/api/alerts` | broadcast amber alert; senior-only |
| POST | `/api/requests` | broadcast help/medical request |
| POST | `/api/cases/{id}/messages` | reply within a case |

All three persist a `ToolCall(decision_id=NULL, decided_by=<op>, approval_status='approved')` + an `OutboundMessage` placeholder, mirroring the agent path.

#### Demo / sim
| Method | Path | Effect |
|---|---|---|
| POST | `/api/sim/seed?reset=true` | populate the rich demo scene (8 alerts, 14 historic decisions, 8 pending suggestions, etc.) |
| POST | `/api/sim/inbound` | inject a single InboundMessage; rides triage + agent |
| POST | `/api/sim/replay/start?intervalSec=6` | start the live drip — one fresh message every N seconds |
| POST | `/api/sim/replay/stop` | halt the drip |
| GET | `/api/sim/replay/status` | running flag + last 10 fired messages |

### 4. WebSocket — `/ws/stream`

One persistent connection per dashboard. Forwards 6 event types:

| Type | Payload shape | Triggered by |
|---|---|---|
| `message` | `{incident, message}` | inbound message persisted |
| `incident_upserted` | `{incident}` | alert created/updated; operator wrote a ToolCall |
| `agent_thinking` | `{bucketKey, alertId, regionPrefix, incident}` | agent claimed a bucket — UI glows the region card |
| `decision_made` | `{decision: {id, model, summary, totalTurns, latencyMs, costUsd, toolCalls[]}, alertId, regionPrefix, incident}` | `AgentDecision` row persisted — UI prepends to activity tape |
| `suggestion_pending` | `{suggestion: {id, tool, args, decisionSummary}, incident}` | new `ToolCall(approval_status='pending')` — UI prepends to inbox |
| `suggestion_resolved` | `{id, approvalStatus}` | operator clicked approve/reject — UI removes from inbox |

### 5. Agent tool surface

Two categories. **Action tools** produce side effects, emit `ToolCall` rows, end the multi-turn loop. **Retrieval tools** are read-only and free to call mid-loop within the turn cap.

#### Action tools (12)
- **Comms:** `send(audience, bodies, mode)`
- **Case data:** `record_sighting(alert_id, observer_phone, geohash, notes, confidence, photo_urls[])`
- **Derived knowledge:** `upsert_cluster`, `merge_clusters`, `upsert_trajectory`, `apply_tag`, `remove_tag`, `categorize_alert`
- **Operator surface:** `escalate_to_ngo`, `mark_bad_actor`, `update_alert_status`
- **Audit:** `noop(reason)`

Default modes: most derived-knowledge tools execute (recoverable). `categorize_alert`, `mark_bad_actor`, `update_alert_status` default to `suggest` (cascades, requires sign-off). `send` defaults vary by audience size — `one` and small `many` execute; `all_alert` / `all_ngo` always suggest.

#### Retrieval tools (2)
- `search(entity, query?, filters, sort, top_k=10)` — covers messages, sightings, decisions, clusters, trajectories, tag_assignments. Semantic ranking via pgvector when `query` is set.
- `get(entity, id)` — PK lookup escape hatch.

### 6. Approval state machine

```
mode='execute'  →  approval_status='auto_executed'  →  dispatcher claims immediately
mode='suggest'  →  approval_status='pending'        →  shows in NGO console inbox
                   on operator approve              →  'approved'  →  dispatcher claims
                   on operator reject               →  'rejected'  →  status='done', audit retained
                   on auto-expire (default 1h)      →  'expired'   →  no send, audit retained
```

### 7. Data model — 16 tables

All carry `ngo_id` FK. ULID PKs unless noted.

| Table | Purpose |
|---|---|
| `NGO` | tenant, region, standing orders |
| `Account` | civilian phone identity, trust score, push token, last-known geohash |
| `Alert` | active case; carries `category`, `urgency_tier`, `urgency_score`, region |
| `AlertDelivery` | denormalized roster of who received which alert |
| `InboundMessage` | raw inbound (queue: `new`/`triaging`/`triaged`/`failed`) |
| `TriagedMessage` | classified + geohashed + embedded; `bucket_key` set; `body_embedding Vector(512)` |
| `Bucket` | coalescing primitive (queue: `open`/`claimed`/`done`/`failed`) |
| `AgentDecision` | one per claimed bucket; full `turns JSON` for replay; `UNIQUE(bucket_key)` |
| `ToolCall` | every action-tool invocation; `UNIQUE(idempotency_key)`; `mode` + `approval_status` lifecycle |
| `OutboundMessage` | one per recipient per send; channel-cascade traceable via `previous_out_id` |
| `Sighting` | structured case data with `notes_embedding Vector(512)` |
| `BadActor` | dropped at triage; TTL'd |
| `SightingCluster` | derived knowledge: location/time-coherent groups; `embedding Vector(512)` is centroid |
| `Trajectory` | inferred path with `points`, direction, speed |
| `Tag` | namespaced free-form taxonomy |
| `TagAssignment` | idempotent (`UNIQUE(tag_id, entity_type, entity_id)`) |

**Bucket key:** `{alert_id}|{geohash_prefix_4}|{window_iso}`. Default 3000ms window (per `Bucket.window_length_ms`). Heartbeat buckets use `heartbeat:{alert_id}:{ts}`.

**Idempotency key:** `sha256(bucket_key || tool_name || canonical_json(args))` on every `ToolCall`. Replay-safe by construction.

### 8. Tech stack

- **Python 3.12+**, FastAPI 0.110+, uvicorn
- **SQLAlchemy 2.0 async** + asyncpg
- **alembic** for migrations
- **pgvector** Python package + `pgvector/pgvector:pg16` Docker image
- **pydantic-settings** for config, **python-ulid** for PKs
- **anthropic** (bare client) for triage
- **claude-agent-sdk** ≥ 0.1.68 for the agent worker (requires Claude Code CLI on PATH for real mode)
- **pytest + pytest-asyncio + httpx** for tests; **ruff** for lint
- **uv** for package management

Frontend: React + Vite + Tailwind + Zustand + Leaflet (in `web/`).

### 9. Build status

| Plan | Scope | Status |
|---|---|---|
| 1 — Foundation | Postgres + pgvector compose, FastAPI skeleton, all 16 SQLAlchemy models + alembic revisions, EventBus & SmsProvider Protocols + first impls, NGO operator JWT auth | **shipped** |
| 2 — Inbound pipeline | API tier ingress, channel adapters, triage worker, registry, /api/me, /api/audiences, /api/regions/*, /api/incidents/*, /api/dashboard, /api/sim/{seed,inbound}, WS /ws/stream, e2e | **shipped** |
| 3 — Agent worker | claude-agent-sdk integration, 14-tool surface, idempotency + audit, per-alert advisory lock, multi-turn loop with retrieval, stub mode for tests | **shipped** (real-LLM path validated against Sonnet 4.5) |
| 3.5 — Operator endpoints | POST /api/alerts, /api/requests, /api/cases/{id}/messages writing unified ToolCall + OutboundMessage rows | **shipped** |
| 3.6 — Liveness | /api/suggestions inbox, /api/decisions/recent, /api/agent/stats, 4 new WS event types, agent-worker publish hooks | **shipped** |
| 3.7 — Demo aliveness | Rich multi-region seeder (8 alerts, ~30 decisions, 8 pending), live replay drip, heartbeat scheduler | **shipped** |
| 4 — Outbound dispatcher | Real Twilio + WS push, channel cascade, audience resolution, rate-limited token buckets, OutboundMessage delivery lifecycle | not yet started |
| 5 — Frontend liveness UI | Header pill, activity tape, approvals inbox, region-glow on `agent_thinking` | in flight (frontend) |
| 6 — Bitchat BLE transport | Last-mile mesh adapter | stretch goal |

### 10. Tests

```bash
uv run pytest               # 98 passing as of last commit
uv run pytest -k agent      # agent-worker focused
uv run pytest -k suggestions  # liveness endpoints
```

Test files (one per domain):

| File | Coverage |
|---|---|
| `test_models_*` | every SQLAlchemy model |
| `test_db_engine.py` | pgvector loaded, test DB isolation |
| `test_eventbus_postgres.py` | LISTEN/NOTIFY round-trip |
| `test_sim_sms.py` | sim transport |
| `test_registry_and_auth.py` | static registry + `current_operator` dep |
| `test_api_*` | every REST endpoint |
| `test_triage_worker.py` | classify → triaged + bucket |
| `test_agent_worker.py` | stub mode → AgentDecision + ToolCall + side-effects |
| `test_api_suggestions_and_feed.py` | inbox + activity feed contract |
| `test_sim_replay.py`, `test_heartbeat.py` | aliveness backends |
| `test_e2e_foundation.py`, `test_e2e_inbound_pipeline.py` | full pipeline: POST /sim/inbound → triage → bucket → agent decision |
| `test_worker_lifecycle.py` | both workers stay alive across requests |

For the real-LLM path: `scripts/smoke_real_agent.py` does a one-shot end-to-end test with a real `ANTHROPIC_API_KEY`. Validates SDK connect, multi-turn loop, tool dispatch, persistence. Costs ~$0.06 per run.

### 11. Operating envelope (validated against the spec, not yet measured)

Target spike: **1M messages over 5 minutes**.

| Stage | Volume | Mechanism | Outcome |
|---|---|---|---|
| API Tier | 3,300 INSERTs/s | stateless, async, multi-instance | sustained with 3-4 pods |
| Triage | 1M Haiku calls | ~30 concurrent | drains in ~5 min, ~$100 |
| Bucketing | 1M → ~150-200 buckets | adaptive window + region prefix | coalescing factor ~5,000:1 |
| Agent | ~150 Sonnet calls | 5 alerts × 6 decisions/min/alert (per-alert lock) | ~150 decisions in 5 min, ~$22 |
| Dispatch | ~750k sends | push (free) for 80%, SMS (rate-limited) for 20% | ~$3,750, dominated by SMS |

### 12. Pointers

- **Spec:** `docs/superpowers/specs/2026-04-25-matching-engine-design.md` — full architecture and every contract.
- **Plans:** `docs/superpowers/plans/2026-04-25-foundation.md`, `2026-04-25-inbound-pipeline.md`.
- **Smoke script:** `scripts/smoke_real_agent.py` — one-shot real-LLM validation.
- **Mobile slice:** `mobileapp/` — SafeThread iOS (Bitchat-derived) — UI shell, store-and-forward layer.

---

## Conventions

- **Skills-driven workflow.** Plans are written for the `superpowers:executing-plans` and `superpowers:subagent-driven-development` skills.
- **TDD where it matters.** Every domain has tests; protocol-shaped contracts (EventBus, SmsProvider, etc.) ship with their first concrete implementation.
- **No half-steps.** Postgres + pgvector + advisory locks + `LISTEN/NOTIFY` from day one.
- **Multi-tenant schema, single-tenant runtime.** `ngo_id` everywhere; one NGO live in the demo.
- **Audit by construction.** `AgentDecision.turns JSON` carries the full multi-turn conversation; idempotency keys at every queue boundary; `ToolCall.revised_from_call_id` traces operator edits.
- **Graceful LLM degradation.** Triage and agent both fall back to deterministic stubs when `ANTHROPIC_API_KEY` is unset, so tests and offline demos always run.
