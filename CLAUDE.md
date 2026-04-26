# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repo at a glance

SafeThread is a field-coordination platform for NGOs in low-connectivity warzones. Civilians signal sightings/needs over SMS, app push, and a Bluetooth-mesh app (bitchat). A backend matching engine fuses the signals through an LLM agent and surfaces decisions to operators in a React console.

Four cooperating slices:

- `server/` — FastAPI + asyncio workers (matching engine)
- `web/` — React/Vite NGO console (operator UI)
- `mobileapp/` — **curated subset** of a bitchat-derived iOS slice; not a buildable Xcode project (full project lives at `hidden-salmon/bitchat-amber#amber-alert`)
- `server/dtn/`, `server/transports/{ble_mesh,sim_mesh,mesh_base}.py` — DTN ingest library + mesh transport adapters; **only present on the `matching-engine` branch**

The full architecture, every contract, and the data model are in `README.md` (read it). The design source-of-truth is `docs/superpowers/specs/2026-04-25-matching-engine-design.md`.

## Commands

### Backend (Python, uv)

```bash
uv sync                                     # install / lock
uv run alembic upgrade head                 # migrations
uv run uvicorn server.main:app --reload --port 8080  # dev server (workers start in lifespan)

uv run pytest                               # full suite
uv run pytest -k agent                      # single domain
uv run pytest tests/test_agent_worker.py    # single file
uv run pytest tests/test_agent_worker.py::test_stub_decide_records_sighting  # single test
uv run ruff check .                         # lint
uv run ruff format .                        # format
```

Tests use a separate `TEST_DATABASE_URL` (see `.env.example`) and require Postgres + pgvector running.

### Frontend (Node, npm)

```bash
cd web
npm install
npm run dev          # Vite dev server on :5173, proxies API to :8080
npm run build        # type-check + production build to web/dist
npx tsc -b --noEmit  # type-check only (no emit)
```

There is **no test runner wired** for the frontend.

### Full stack (Docker)

```bash
docker compose up -d db        # Postgres + pgvector only
docker compose up --build      # everything (builds web/, runs migrations, starts workers)
```

`ANTHROPIC_API_KEY` is forwarded from the host. The Dockerfile installs Node + the Claude Code CLI because `claude-agent-sdk` real mode spawns the CLI as a subprocess.

### Demo seed + drip

```bash
curl -X POST "http://localhost:8080/api/sim/seed?reset=true"
curl -X POST "http://localhost:8080/api/sim/replay/start?intervalSec=4"
curl -X POST "http://localhost:8080/api/sim/replay/stop"
```

### Real-LLM smoke test

```bash
uv run python scripts/smoke_real_agent.py   # ~$0.06; needs ANTHROPIC_API_KEY
```

## Architecture you must keep in your head

**Pipeline (4 DB-coupled stages, 5 nodes).** API tier (and DTN dispatcher on the branch) writes `InboundMessage` → triage worker writes `TriagedMessage` + `Bucket` → agent worker claims a `Bucket` and writes `AgentDecision` + `ToolCall` rows → outbound dispatcher (not yet built) reads approved/auto-executed `ToolCall` rows.

**DB-as-bus.** No RPC between components. Every contract is a Postgres table. Wake-ups are `LISTEN/NOTIFY` channels (`new_inbound`, `bucket_open`, `agent_thinking`, `decision_made`, `suggestion_pending`, `suggestion_resolved`). Per-alert serialization is a `pg_advisory_lock(hashtext(alert_id))` held for the agent's whole multi-turn loop.

**Coalescing.** Bucket key is `{alert_id}|{geohash_prefix_4}|{window_iso}`. Many inbound messages collapse into one agent decision. Heartbeat scheduler periodically inserts synthetic empty buckets per active alert so the agent runs consolidation even with no inbound.

**Idempotency.** Every `ToolCall` carries `idempotency_key = sha256(bucket_key || tool_name || canonical_json(args))`. Replays are exact.

**Execute vs suggest.** Action tools default to either `execute` (auto-applies, audit-only) or `suggest` (writes a pending `ToolCall` that surfaces in the operator inbox at `/api/suggestions`). `send` to `all_alert`/`all_ngo` always suggests.

## Critical gotchas

- **Agent worker has two modes.** `ANTHROPIC_API_KEY` set → real mode (spawns Claude Code CLI subprocess via `claude-agent-sdk`; needs the CLI on PATH). Unset → deterministic stub. Tests, CI, and offline demos rely on stub mode. If the CLI isn't installed and the key is set, the worker crashes with `ProcessError` at connect.
- **Branch model.** `main` has the matching engine + console. **DTN library, mesh transport adapters, and the `account.bitchat_pubkey` column live on `matching-engine`.** Don't add or modify DTN code on `main`.
- **Frontend routing is hand-rolled.** `web/src/lib/router.ts` exposes `useRoute()` + `navigate()` backed by `history.pushState`. **Do not introduce react-router.** When adding a route, update both `PATH_TO_ROUTE` and `ROUTE_TO_PATH`.
- **No `<select>` elements in the frontend.** Native selects render OS-styled (dark on macOS) and broke the design system. Use `web/src/components/Select.tsx` everywhere.
- **Multi-tenant schema, single-tenant runtime.** Every table carries `ngo_id`. War Child is the launch tenant. Don't hardcode `ngo_id` in new code; resolve it from the operator context.
- **Wire-format compat.** `mobileapp/.../DTNPackets.swift` ↔ `server/dtn/packets.py` (matching-engine branch) must stay byte-identical. The HKDF info string `b"safethread-dtn-v1"` is load-bearing.

## Style and conventions

- **uv** for Python deps, **alembic** for migrations (always run `alembic upgrade head` after schema changes).
- **Stub-friendly.** Both LLM tiers fall back to deterministic stubs without an API key so tests and offline demos always run; preserve this behavior.
- **TDD where it matters.** Protocol-shaped contracts (`EventBus`, `SmsProvider`, mesh transports) ship with their first concrete implementation + tests.
- **Plans + skills.** Major work is planned in `docs/superpowers/plans/` and executed via the `superpowers:executing-plans` / `superpowers:subagent-driven-development` skills.
- **Operator auth is a stub.** `current_operator` reads `X-Operator-Id` against `server/api/registry.py`. Full JWT auth is deferred. Don't build new code that assumes JWT.
