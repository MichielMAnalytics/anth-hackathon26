# SafeThread

> A field-coordination platform for NGOs operating in low-connectivity warzones. Civilians signal sightings and needs over **SMS, app push, and a Bluetooth-mesh app (bitchat)**. SafeThread fuses those signals through an **LLM-driven matching engine**, surfaces the right cases to operators in a console, and broadcasts decisions back over the same channels — push-first.

This repo contains four cooperating slices that compose into one product:

| Slice | What it is | Where it lives |
|---|---|---|
| **Matching engine** | Backend pipeline that classifies inbound, coalesces by region, runs an agent, and emits decisions | `server/` |
| **DTN ingest layer** | Decoder + dispatcher for opaque delay-tolerant-network bundles posted by the iOS app | `server/dtn/` *(on `matching-engine` branch)* |
| **Mesh transport adapters** | `SmsProvider`-shaped adapters: in-process simulator + BLE skeleton | `server/transports/` *(on `matching-engine` branch)* |
| **NGO console** | React/Vite operator UI: dashboard, cases, map, broadcast composer | `web/` |
| **Mobile slice** | bitchat-derived iOS app with SafeThread store-and-forward | `mobileapp/` |

**Status:** matching engine + console run end-to-end on `main`. DTN library + mesh transport scaffold land on `matching-engine`. Twilio/push outbound and real-radio BLE are explicit roadmap items.

---

## 1. The architecture in one picture

```
                        ┌─────────────────────────────────────────────┐
                        │              CIVILIAN DEVICES               │
                        │  (SafeThread iOS — bitchat-derived)         │
                        │   SMS  ·  app push  ·  BLE mesh             │
                        └────────────────┬────────────────────────────┘
                                         │
        ┌────────────────────────────────┼────────────────────────────┐
        │                                │                            │
        ▼                                ▼                            ▼
   carrier SMS              POST /api/sim/inbound (HTTP)     POST /app/dtn/deliver
   (sms_base)                                                (DTN sealed bundle)
        │                                │                            │
        └────────────────┬───────────────┴────────────┬───────────────┘
                         │                            │
                         ▼                            ▼
               ┌─────────────────────┐    ┌──────────────────────────┐
               │   API tier          │    │  DTN dispatcher          │
               │ (FastAPI mailroom)  │    │  decode · seal-open      │
               │                     │    │  amber / sighting / chat │
               └──────────┬──────────┘    └──────────┬───────────────┘
                          │                          │
                          ▼                          ▼
                  ┌──────────────────────────────────────┐
                  │           InboundMessage             │  ← DB-as-bus
                  └─────────────────┬────────────────────┘
                                    │ NOTIFY new_inbound
                                    ▼
                  ┌──────────────────────────────────────┐
                  │  Triage worker  (Haiku)              │
                  │  classify · geocode · dedupe · embed │
                  └─────────────────┬────────────────────┘
                                    │ NOTIFY bucket_open
                                    ▼
              ┌───────────────────────────────────────────────┐
              │   Bucket (alert_id, geohash_4, time_window)   │  ← coalescing primitive
              └─────────────────────┬─────────────────────────┘
                                    │ pg_advisory_lock(alert)
                                    ▼
                  ┌──────────────────────────────────────┐
                  │  Agent worker  (Sonnet/Opus)         │
                  │  retrieve → reason → 14 tools        │
                  └─────────────────┬────────────────────┘
                                    │
                  ┌─────────────────┴────────────────────┐
                  ▼                                      ▼
          AgentDecision row                 ToolCall rows (execute or suggest)
                  │                                      │
                  │                                      ├── auto_executed → dispatcher
                  │                                      └── pending → operator console
                  ▼                                      ▼
               WS /ws/stream  ────►  NGO console (web/)
                                     ▲
                                     │ approve / reject / compose
                                     │
                              human operator
                                     │
                                     ▼
                            Outbound dispatcher
                            (push → SMS → mesh)
```

Five **execution nodes**, four **DB-coupled stages**, one **operator-in-the-loop surface**. Every contract is a Postgres table; every node is restartable, replayable, auditable.

---

## 2. Why it is interesting

- **Spike-handling primitive that actually works.** Buckets coalesce ~1M inbound messages into ~150 agent decisions in 5 minutes for ~$22 of LLM spend. SMS sends still dominate cost (~$3.7k).
- **Channel-agnostic agent.** The agent never knows whether a signal arrived over SMS, app push, or BLE mesh. Adapters live at the edges; the agent reasons on `InboundMessage` rows.
- **Push-first cascade.** Outbound prefers app push (free, instant) → SMS (paid, rate-limited) → bitchat mesh (offline, last resort).
- **DB-as-bus.** No RPC. Every inter-component contract is a Postgres table. `LISTEN/NOTIFY` for wake-ups, advisory locks for serialization.
- **Execute vs suggest.** Low-risk actions auto-execute; mass broadcasts route to the operator console for approve/reject/edit.
- **Always alive.** A heartbeat scheduler ticks every active alert on a periodic cadence; the agent runs a consolidation prompt on each. The dashboard breathes even with zero inbound.
- **Audit by construction.** Every agent decision stores its full multi-turn conversation (`turns JSON`); idempotency keys at every queue boundary; replays are exact.
- **Multi-tenant schema, single-tenant runtime.** Every table carries `ngo_id`. War Child is the launch tenant.
- **Hackathon-shaped, production-shaped code.** All four worker nodes run as asyncio tasks in one FastAPI process for the demo. Splitting them into separate deployments is a config change, not a rewrite.

---

## 3. Quick start

### Production-style (one step, demo-ready)

```bash
# 1. set the Anthropic key (.env is gitignored)
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# 2. up
docker compose up -d --build
```

That's it. The image runs alembic migrations, starts the workers, calls
`seed_rich()` (8 alerts across 6 regions, ~30 historic decisions, 8
pending suggestions), and starts the live replay drip 3s later. Open
`http://localhost:8080` (or `https://<vm>.boxd.sh` on a deploy) — the
dashboard lands populated and breathing.

### Dev (hot-reload backend + Vite)

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

### Env vars

All settable via `.env` or the host shell. Defaults in parentheses are
what `docker-compose.yml` ships.

| Var | Default | Effect |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://app:app@db:5432/matching` | Postgres URL the app + alembic use |
| `ANTHROPIC_API_KEY` | — | enables real Haiku triage + Opus 4.7 agent. Without it both fall back to deterministic stubs (demo still runs, just stub-mode + `costUsd=0`). |
| `JWT_SECRET` | `change-me` | NGO operator JWT signing |
| `HEARTBEAT_INTERVAL_SEC` | `300` | how often the heartbeat scheduler ticks each active alert. Drop to `60` for a livelier demo. |
| `HEARTBEAT_ENABLED` | `true` | `false` to skip the heartbeat task entirely |
| `SEED_ON_BOOT` | `true` (compose) | call `seed_rich()` on app startup if Warchild isn't there yet. Idempotent. |
| `REPLAY_AUTOSTART` | `true` (compose) | start the live drip a few seconds after boot. |
| `REPLAY_INTERVAL_SEC` | `4` | drip cadence when autostarted; lower = busier dashboard. |

---

## 4. Repo layout

```
.
├── server/                         # FastAPI app + workers (asyncio tasks)
│   ├── api/                        # REST + WS routers
│   ├── auth/                       # X-Operator-Id resolver, role checks
│   ├── db/                         # SQLAlchemy 2.0 async models, engine, session
│   ├── eventbus/                   # Postgres LISTEN/NOTIFY pub/sub
│   ├── llm/                        # Triage + Agent LLM clients
│   ├── sim/                        # Demo seeder + replay drip
│   ├── transports/                 # Channel adapters
│   │   ├── sms_base.py / sim_sms.py
│   │   ├── mesh_base.py            # SmsProvider-shaped mesh interface  (matching-engine)
│   │   ├── sim_mesh.py             # in-process asyncio mesh           (matching-engine)
│   │   └── ble_mesh.py             # bleak-based BLE skeleton          (matching-engine)
│   ├── dtn/                        # DTN ingest library                (matching-engine)
│   │   ├── packets.py              # fixed-binary codecs (mirror of iOS DTNPackets.swift)
│   │   ├── seal.py                 # X25519 + HKDF + ChaChaPoly sealed-box
│   │   ├── amber.py                # tolerant TLV decoders (sighting / chat / amber)
│   │   ├── dispatcher.py           # async dispatch_bundle(); FK-strict
│   │   └── store.py                # idempotency cache (dtn_seen_bundle)
│   ├── workers/                    # Triage, Agent, Heartbeat loops
│   └── main.py                     # app factory + lifespan
├── alembic/                        # DB migrations
├── db/init.sql                     # pgvector extension, test DB
├── docker-compose.yml              # 2 services: app + db (pgvector/pgvector:pg16)
├── docs/superpowers/               # Specs + plans (source of truth)
├── tests/                          # pytest, one file per domain
├── web/                            # NGO console — see §6
├── mobileapp/                      # SafeThread iOS (bitchat-derived) — see §7
└── scripts/                        # One-off: real-LLM smoke test
```

---

## 5. Backend — five nodes, four DB-coupled stages

| # | Node | LLM? | Stateless? | Scales with | Output |
|---|---|---|---|---|---|
| 1 | API tier (mailroom) | no | yes | inbound conn count | `InboundMessage` rows |
| 2 | DTN dispatcher | no | yes (idempotent) | bundle rate | `InboundMessage` rows + receipts |
| 3 | Triage worker | yes — Haiku | yes | inbound msg rate | `TriagedMessage` + `Bucket` rows |
| 4 | Agent worker | yes — Sonnet/Opus | yes (idempotent) | bucket rate, capped 1-per-alert via advisory lock | `AgentDecision` + `ToolCall` rows |
| 5 | Outbound dispatcher (courier) | no | yes (idempotent) | provider quotas | `OutboundMessage` rows + provider sends |

**Hackathon collapse:** all worker nodes run as asyncio tasks inside a single FastAPI process; the data tier is a `pgvector/pgvector:pg16` container.

**Heartbeat scheduler** (`server/workers/heartbeat.py`): periodic asyncio task inserts a synthetic empty `Bucket` row every `HEARTBEAT_INTERVAL_SEC` per `Alert(status='active')`, driving consolidation runs (cluster pruning, trajectory extension, contradiction surfacing).

**Worker wake-up:** Postgres `LISTEN/NOTIFY` channels behind a `PostgresEventBus` Protocol:

| Channel | Purpose |
|---|---|
| `new_inbound` | triage worker drains |
| `bucket_open` | agent worker drains |
| `agent_thinking` | UI: region card glow on |
| `decision_made` | UI: activity tape new row |
| `suggestion_pending` | UI: approvals inbox new row |
| `suggestion_resolved` | UI: inbox row removed |
| `incident_upserted` / `toolcalls_pending` / `suggestions_pending` | internal pipeline coordination |
| `ws_push:{account_id}` | reserved for outbound dispatcher |

**Per-alert serialization:** Postgres advisory lock keyed off the alert ID. Held for the agent's multi-turn loop + decision write.

### 5.1 Component contracts

**API tier (`server/api/*`).** Stateless ingress. `current_operator` dep reads `X-Operator-Id` against a static registry (full JWT auth deferred). FastAPI routers grouped by purpose, all listed in §8.

**DTN dispatcher (`server/dtn/*`, on `matching-engine`).** Pure library — no FastAPI routes. Sibling slice owns `/app/dtn/deliver`. Wire format mirrors `mobileapp/.../DTNPackets.swift` exactly. The HKDF info string `b"safethread-dtn-v1"` is load-bearing — both sides must use the same value. Idempotency via `dtn_seen_bundle`. Caller is expected to verify the bundle's Ed25519 signature against `Account.bitchat_pubkey` before invoking `dispatch_bundle()`.

**Triage worker (`server/workers/triage.py`).** Bare `anthropic` SDK; one `messages.create()` per message with a single tool to enforce JSON-schema output. Model `claude-haiku-4-5-20251001`. Falls back to a deterministic stub when `ANTHROPIC_API_KEY` is unset. Output: `TriagedMessage` row + `Bucket(status='open')` upsert + `bucket_open` notify.

**Agent worker (`server/workers/agent.py`).** `claude-agent-sdk` ≥ 0.1.68. One persistent `ClaudeSDKClient` per worker. `setting_sources=[]`, `permission_mode="bypassPermissions"`, `max_turns=8`, `max_budget_usd=0.50`, model `claude-opus-4-7` / fallback `claude-sonnet-4-6`. All 14 matching-engine tools registered as an in-process MCP server via `create_sdk_mcp_server`. Stub mode synthesizes a deterministic decision when no API key is set. Per-decision flow:

1. Claim a `Bucket` (`FOR UPDATE SKIP LOCKED`).
2. Acquire `pg_try_advisory_lock(hashtext(alert_id))`.
3. Publish `agent_thinking` event.
4. Load context via 8 parallel queries (`asyncio.gather` over triaged messages, recent decisions, sightings, clusters, trajectories, tag assignments, account snapshots, dispatch backlog).
5. Run multi-turn loop (real or stub).
6. Persist `AgentDecision` + N `ToolCall` rows; apply execute-mode side-effects inline.
7. Publish `decision_made` and one `suggestion_pending` per pending tool call.
8. Mark bucket done; release advisory lock.

A watchdog wraps the loop catching `ProcessError`/`CLIConnectionError`; on subprocess death, it recreates the client and releases the bucket back. Bucket retries up to 3 times → `status='failed'`.

**Outbound dispatcher.** Not yet built. Pipeline currently terminates at `ToolCall` rows + inline side-effects for internal tools. The frontend's operator-write endpoints (`/api/alerts`, `/api/requests`, `/api/cases/{id}/messages`) write `ToolCall(approval_status='approved')` + placeholder `OutboundMessage` rows so the audit trail is unified. Real Twilio / WS-push integration is the next deliverable.

**Data tier.** Postgres ≥ 16 + `pgvector` extension. Geohashes are `TEXT` with prefix `LIKE` queries. Vectors use `Vector(512)` columns; HNSW indices defined in alembic migrations.

---

## 6. Frontend — NGO console (`web/`)

React + Vite + Tailwind + Zustand + Leaflet. Editorial design system: pure-white surfaces, near-black typography, `///` section markers, mono uppercase metadata, restrained brand-red accents.

### 6.1 Routes

Hand-rolled URL router (`web/src/lib/router.ts`) backed by `history.pushState`:

| Path | View | Purpose |
|---|---|---|
| `/` | `DashboardView` | "Where to act first" — region cards ranked by urgency, stats banner, recent-distress wire panel |
| `/cases` | `CasesView` | three-pane: incident list · chat thread · case profile |
| `/map` | `MapView` | Leaflet map with severity-coded markers + region panel |

### 6.2 Live state

- **`LiveIndicator`** subscribes to the WebSocket lifecycle and the `lastEventTs` and renders one of: **LIVE** (pulse, fresh event in last 30s), **IDLE · 2m** (connected, quiet), **CONNECTING** (amber pulse), **OFFLINE** (red).
- **`openStream`** (`web/src/lib/api.ts`) is a self-reconnecting WebSocket wrapper that calls back with both events and connection-state changes.
- Zustand store holds `incidents`, `messagesByIncident`, `audiences`, `regions`, `me`, `operators`, `selectedIncidentId`, `selectedRegion`, `issueFilter`. Routing state was deliberately moved out of the store and into the URL.

### 6.3 Component system

- **`Select`** — accessible custom dropdown that replaces every native `<select>` (which renders OS-styled and looked broken on macOS dark theme). Used by FilterBar, CaseComposer, SendModal.
- **`SeverityChip`** — dot + mono uppercase label; no pills.
- **`OperatorSwitcher`** — initials monogram tile, role + organization affiliation in the trigger, dropdown carries the War Child banner above the switch list.
- **`MessageBubble`** — real chat: civilian messages on the left with a circular avatar (last 2 phone digits) + bitchat icon badge; operator replies on the right with a dark bubble + AH initials avatar; consecutive messages from the same sender within 2 minutes collapse into a group; timestamp shows only at group boundaries.
- **`RegionCard`** — indexed `[01]`, `[02]` editorial cards with severity rail; sparkline; theme list; click-through to `/cases` or `/map` with the region pre-selected.

### 6.4 Branding model

The app renders SafeThread (the platform). The operator's NGO is a separate concept surfaced in the `OperatorSwitcher`: a banner inside the dropdown shows the org logo + name; the trigger subtitle includes `SENIOR · [logo] War Child`. War Child is currently a constant in `OperatorSwitcher.tsx` because it's the only tenant; when SafeThread onboards more NGOs it becomes a per-operator field on `me`.

---

## 7. Mobile + mesh

`mobileapp/` is a fork of the open-source **bitchat** iOS app, augmented with SafeThread's store-and-forward layer.

- **Bluetooth-mesh hops.** Civilian phones gossip messages to each other when no carrier is available. The originating phone signs an Ed25519-authenticated DTN bundle.
- **Carrier-uplink phone.** The first phone in the mesh that has internet POSTs the (still-encrypted) bundle to `/app/dtn/deliver`. The hub never needs a BLE radio for the demo path.
- **Wire format.** `DTNPackets.swift` (mobile) ↔ `server/dtn/packets.py` (hub). Fixed-binary codecs covering: `Sighting (0x21)`, `Chat (0x22)`, `Amber/Status (0x23)`, `ProfileUpdate (0x24, forward-declared)`, `dtnBundle (0x25)`. Sealed with X25519 + HKDF (`info=b"safethread-dtn-v1"`) + ChaChaPoly.
- **Hub-side mesh adapter (optional).** `server/transports/{mesh_base,sim_mesh,ble_mesh}.py` provide an `SmsProvider`-shaped abstraction so the hub itself can speak mesh in tests (in-process simulator) or on a Pi with a USB BLE dongle (skeleton; explicit roadmap item).

This entire layer (DTN + mesh transports + tests) lives on the **`matching-engine`** branch as of the latest merge; it has not been merged into `main` yet.

---

## 8. HTTP API surface

All endpoints require `X-Operator-Id: op-senior` (or `op-junior`) header except `/health` and `/api/sim/*`.

### Read paths (frontend hydration)
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

### Agent activity
| Method | Path | Returns |
|---|---|---|
| GET | `/api/agent/stats` | `{decisionsToday, costTodayUsd, pending, executedToday, lastDecisionAt}` |
| GET | `/api/decisions/recent?limit=20` | activity tape backfill |
| GET | `/api/suggestions` | operator inbox — pending `ToolCall` rows |
| POST | `/api/suggestions/{id}/approve` | flip to `approved`; publishes `suggestion_resolved` |
| POST | `/api/suggestions/{id}/reject` | flip to `rejected`, status=`done` |

### Operator writes
| Method | Path | Effect |
|---|---|---|
| POST | `/api/alerts` | broadcast amber alert; senior-only |
| POST | `/api/requests` | broadcast help/medical request |
| POST | `/api/cases/{id}/messages` | reply within a case |

All three persist a `ToolCall(decision_id=NULL, decided_by=<op>, approval_status='approved')` + an `OutboundMessage` placeholder, mirroring the agent path.

### Mobile / DTN ingest *(matching-engine branch — routes are a sibling slice)*
| Method | Path | Effect |
|---|---|---|
| POST | `/app/dtn/deliver` | accept opaque DTN bundle bytes; verify Ed25519 sig; resolve sender via `Account.bitchat_pubkey`; call `dispatch_bundle()` |

### Demo / sim
| Method | Path | Effect |
|---|---|---|
| POST | `/api/sim/seed?reset=true` | populate the rich demo scene |
| POST | `/api/sim/inbound` | inject a single InboundMessage; rides triage + agent |
| POST | `/api/sim/replay/start?intervalSec=6` | start the live drip |
| POST | `/api/sim/replay/stop` | halt the drip |
| GET | `/api/sim/replay/status` | running flag + last 10 fired messages |

### WebSocket — `/ws/stream`

One persistent connection per dashboard. Forwards 6 event types:

| Type | Payload shape | Triggered by |
|---|---|---|
| `message` | `{incident, message}` | inbound message persisted |
| `incident_upserted` | `{incident}` | alert created/updated |
| `agent_thinking` | `{bucketKey, alertId, regionPrefix, incident}` | agent claimed a bucket |
| `decision_made` | `{decision, alertId, regionPrefix, incident}` | `AgentDecision` row persisted |
| `suggestion_pending` | `{suggestion, incident}` | new `ToolCall(approval_status='pending')` |
| `suggestion_resolved` | `{id, approvalStatus}` | operator clicked approve/reject |

---

## 9. Agent tool surface

Two categories. **Action tools** produce side effects, emit `ToolCall` rows, end the multi-turn loop. **Retrieval tools** are read-only and free to call mid-loop within the turn cap.

**Action tools (12).**
- *Comms:* `send(audience, bodies, mode)`
- *Case data:* `record_sighting(alert_id, observer_phone, geohash, notes, confidence, photo_urls[])`
- *Derived knowledge:* `upsert_cluster`, `merge_clusters`, `upsert_trajectory`, `apply_tag`, `remove_tag`, `categorize_alert`
- *Operator surface:* `escalate_to_ngo`, `mark_bad_actor`, `update_alert_status`
- *Audit:* `noop(reason)`

Default modes: most derived-knowledge tools execute (recoverable). `categorize_alert`, `mark_bad_actor`, `update_alert_status` default to `suggest`. `send` defaults vary by audience size — `one` and small `many` execute; `all_alert` / `all_ngo` always suggest.

**Retrieval tools (2).**
- `search(entity, query?, filters, sort, top_k=10)` — covers messages, sightings, decisions, clusters, trajectories, tag_assignments. Semantic ranking via pgvector when `query` is set.
- `get(entity, id)` — PK lookup escape hatch.

**Approval state machine.**

```
mode='execute'  →  approval_status='auto_executed'  →  dispatcher claims immediately
mode='suggest'  →  approval_status='pending'        →  shows in NGO console inbox
                   on operator approve              →  'approved'  →  dispatcher claims
                   on operator reject               →  'rejected'  →  status='done'
                   on auto-expire (default 1h)      →  'expired'   →  no send
```

---

## 10. Data model — 16 tables

All carry `ngo_id` FK. ULID PKs unless noted.

| Table | Purpose |
|---|---|
| `NGO` | tenant, region, standing orders |
| `Account` | civilian phone identity, trust score, push token, last-known geohash, **`bitchat_pubkey`** (matching-engine) |
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
| `dtn_seen_bundle` *(matching-engine)* | DTN idempotency cache |

**Bucket key:** `{alert_id}|{geohash_prefix_4}|{window_iso}`. Default 3000ms window. Heartbeat buckets use `heartbeat:{alert_id}:{ts}`.

**Idempotency key:** `sha256(bucket_key || tool_name || canonical_json(args))` on every `ToolCall`. Replay-safe by construction.

---

## 11. Tech stack

**Backend.** Python 3.12+, FastAPI 0.110+, uvicorn, SQLAlchemy 2.0 async + asyncpg, alembic, pgvector, pydantic-settings, python-ulid, anthropic (bare client) for triage, claude-agent-sdk ≥ 0.1.68 for the agent worker (requires Claude Code CLI on PATH for real mode), pytest + pytest-asyncio + httpx, ruff, uv.

**DTN / mesh** *(matching-engine)*. cryptography (X25519 + HKDF + ChaCha20-Poly1305), bleak (BLE skeleton — never imported on the hot path).

**Frontend.** React 18, Vite, Tailwind v3, Zustand, Leaflet, clsx. Inter Tight + Inter + JetBrains Mono. Self-contained URL router (no react-router), self-contained `Select` component (no headlessui/radix).

**Mobile.** Swift 5, bitchat fork with SafeThread store-and-forward layer.

---

## 12. Build status

| Plan | Scope | Status |
|---|---|---|
| 1 — Foundation | Postgres + pgvector compose, FastAPI skeleton, all 16 SQLAlchemy models + alembic, EventBus & SmsProvider Protocols, JWT auth scaffold | shipped |
| 2 — Inbound pipeline | API ingress, channel adapters, triage worker, registry, frontend hydration endpoints, WS, e2e | shipped |
| 3 — Agent worker | claude-agent-sdk integration, 14-tool surface, idempotency + audit, per-alert advisory lock, multi-turn loop with retrieval, stub mode | shipped (real-LLM path validated against Sonnet 4.5) |
| 3.5 — Operator endpoints | unified ToolCall + OutboundMessage on operator writes | shipped |
| 3.6 — Liveness | `/api/suggestions` inbox, `/api/decisions/recent`, `/api/agent/stats`, 4 new WS event types | shipped |
| 3.7 — Demo aliveness | rich seeder, replay drip, heartbeat scheduler | shipped |
| 4 — DTN ingest library | wire-format codecs, sealed-box crypto, dispatcher, idempotency, account `bitchat_pubkey` | shipped on `matching-engine` |
| 4.1 — Mesh transport adapters | `SmsProvider`-shaped mesh interface, sim transport, BLE skeleton | shipped on `matching-engine` |
| 5 — Frontend rebuild | SafeThread rebrand, editorial design system, URL routing, smart `LiveIndicator`, custom `Select`, real chat layout, operator/org model | shipped |
| 6 — Outbound dispatcher | real Twilio + WS push, channel cascade, audience resolution, rate-limited token buckets | not yet started |
| 7 — Bitchat BLE on hub | bleak-backed BLE radio, real GATT service binding | stretch goal |

---

## 13. Tests

```bash
uv run pytest               # 98 passing on main; +29 DTN tests on matching-engine
uv run pytest -k agent      # agent-worker focused
uv run pytest -k dtn        # DTN library (matching-engine)
uv run pytest -k transport  # mesh adapters (matching-engine)
```

For the real-LLM path: `scripts/smoke_real_agent.py` does a one-shot end-to-end test with a real `ANTHROPIC_API_KEY`. Validates SDK connect, multi-turn loop, tool dispatch, persistence. Costs ~$0.06 per run.

---

## 14. Operating envelope

Target spike: **1M messages over 5 minutes**.

| Stage | Volume | Mechanism | Outcome |
|---|---|---|---|
| API tier | 3,300 INSERTs/s | stateless, async, multi-instance | sustained with 3-4 pods |
| DTN dispatcher | 100s of bundles/s | tolerant decode, idempotency cache, FK-strict writes | bounded by Account lookups |
| Triage | 1M Haiku calls | ~30 concurrent | drains in ~5 min, ~$100 |
| Bucketing | 1M → ~150-200 buckets | adaptive window + region prefix | coalescing factor ~5,000:1 |
| Agent | ~150 Sonnet calls | per-alert advisory lock | ~$22 in 5 min |
| Dispatch | ~750k sends | push (free) for 80%, SMS for 20% | ~$3,750, dominated by SMS |

---

## 15. Pointers

- **Spec:** `docs/superpowers/specs/2026-04-25-matching-engine-design.md` — full architecture and every contract.
- **Plans:** `docs/superpowers/plans/`
- **Smoke script:** `scripts/smoke_real_agent.py` — one-shot real-LLM validation.
- **DTN wire format:** `mobileapp/.../DTNPackets.swift` ↔ `server/dtn/packets.py` (must stay in sync).
- **Branches:** `main` (matching engine + console); `matching-engine` (adds DTN library + mesh transport adapters, will fold into `main`).

---

## Conventions

- **Skills-driven workflow.** Plans are written for the `superpowers:executing-plans` and `superpowers:subagent-driven-development` skills.
- **TDD where it matters.** Every domain has tests; protocol-shaped contracts ship with their first concrete implementation.
- **No half-steps.** Postgres + pgvector + advisory locks + `LISTEN/NOTIFY` from day one.
- **Multi-tenant schema, single-tenant runtime.** `ngo_id` everywhere; War Child is the launch tenant.
- **Audit by construction.** `AgentDecision.turns JSON` carries the full multi-turn conversation; idempotency keys at every queue boundary; `ToolCall.revised_from_call_id` traces operator edits.
- **Graceful LLM degradation.** Triage and agent both fall back to deterministic stubs when `ANTHROPIC_API_KEY` is unset, so tests and offline demos always run.
