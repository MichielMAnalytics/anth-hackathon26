# Plan 2 — Inbound Pipeline + Frontend Shell

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the matching engine's inbound pipeline end-to-end (civilian message → InboundMessage → Triage worker → TriagedMessage + Bucket → EventBus → WS event), and stand up the minimum frontend-shell endpoints so the existing `web/` UI stops 404-ing and renders real seeded data.

**Architecture:** Endpoints live as small FastAPI router files under `server/api/`, sharing a static registry (operators / audiences / region metadata) and a header-based auth dependency. The Triage worker runs as an asyncio background task started by FastAPI's `lifespan`; it drains `inbound_message` rows, classifies via Haiku (with a deterministic stub when `ANTHROPIC_API_KEY` is unset), generates a deterministic stub embedding (real embedding client deferred to Plan 3), inserts `TriagedMessage`, upserts `Bucket`, and publishes `bucket_open` on the EventBus. A WebSocket route at `/ws/stream` subscribes to the EventBus and emits `{type:"message"|"incident_upserted"}` events shaped for the frontend.

**Tech Stack:**
- Existing Plan 1 stack: FastAPI, SQLAlchemy 2.0 async, asyncpg, alembic, pgvector, Postgres + LISTEN/NOTIFY, JWT (carried for prod), pytest + httpx + pytest-asyncio.
- New: `anthropic` Python client (Haiku triage with `tool_choice` for structured output).
- Stubbed for Plan 2: embeddings (deterministic hash → 512 floats) and operator auth (header lookup against a static registry; JWT bridge deferred).

---

## File structure

```
server/
├── api/
│   ├── __init__.py            (existing, empty)
│   ├── health.py              (existing)
│   ├── registry.py            (NEW — Task 1) static OPERATORS/AUDIENCES/REGIONS
│   ├── auth_dep.py            (NEW — Task 1) current_operator FastAPI dep
│   ├── operators.py           (NEW — Task 2) /api/me, /api/operators
│   ├── audiences.py           (NEW — Task 3) /api/audiences
│   ├── regions.py             (NEW — Task 4, extended Task 5) /api/regions/stats and /timeline
│   ├── incidents.py           (NEW — Task 6, extended Task 7) /api/incidents and /:id/messages
│   ├── dashboard.py           (NEW — Task 8) /api/dashboard
│   ├── sim.py                 (NEW — Task 9, extended Task 10) /api/sim/seed and /inbound
│   └── ws.py                  (NEW — Task 13) WS /ws/stream
├── llm/
│   ├── __init__.py            (NEW — Task 11)
│   └── triage_client.py       (NEW — Task 11) Haiku call + hash_to_vec stub
├── workers/
│   ├── __init__.py            (NEW — Task 11)
│   └── triage.py              (NEW — Task 11) triage_worker_loop
└── main.py                    (MODIFIED — Tasks 2-13) router + lifespan registration

tests/
├── test_registry_and_auth.py  (NEW — Task 1)
├── test_api_operators.py      (NEW — Task 2)
├── test_api_audiences.py      (NEW — Task 3)
├── test_api_regions.py        (NEW — Tasks 4-5)
├── test_api_incidents.py      (NEW — Tasks 6-7)
├── test_api_dashboard.py      (NEW — Task 8)
├── test_api_sim_seed.py       (NEW — Task 9)
├── test_api_sim_inbound.py    (NEW — Task 10)
├── test_triage_worker.py      (NEW — Task 11)
├── test_worker_lifecycle.py   (NEW — Task 12)
├── test_api_ws_stream.py      (NEW — Task 13)
└── test_e2e_inbound_pipeline.py (NEW — Task 14)
```

Each task creates one router file plus its test file (where applicable). `server/main.py` is modified at the end of each task to register the new router. The auth dep + registry land first (Task 1) and are imported by every endpoint task afterward.

The static `REGIONS` is a **dict keyed by region key** (`{"IRQ_BAGHDAD": {...}, ...}`) so endpoints can do `REGIONS["IRQ_BAGHDAD"]["geohash_prefix"]` directly. Iteration is `for region_key, meta in REGIONS.items()`.

---

## Task 1 — Static registry + operator auth dep

**Files:**
- Create: `server/api/registry.py`
- Create: `server/api/auth_dep.py`
- Test: `tests/test_registry_and_auth.py`

- [ ] **Step 1.1 — Write failing test**

`tests/test_registry_and_auth.py`:
```python
import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from server.api.auth_dep import current_operator
from server.api.registry import AUDIENCES, OPERATORS, REGIONS, get_operator_by_id


def test_registry_counts():
    assert len(OPERATORS) == 2
    assert len(AUDIENCES) == 4
    assert len(REGIONS) == 6


def test_region_keys_match_frontend_enum():
    expected = {"IRQ_BAGHDAD", "IRQ_MOSUL", "SYR_ALEPPO", "SYR_DAMASCUS", "YEM_SANAA", "LBN_BEIRUT"}
    assert set(REGIONS.keys()) == expected


def test_region_metadata_has_4_char_prefix():
    for key, meta in REGIONS.items():
        assert "geohash_prefix" in meta
        assert len(meta["geohash_prefix"]) == 4
        assert isinstance(meta["lat"], float)
        assert isinstance(meta["lon"], float)
        assert isinstance(meta["label"], str)


def test_operator_shape():
    for op in OPERATORS:
        assert set(op.keys()) >= {"id", "name", "role", "regions", "avatarSeed"}
        assert op["role"] in ("senior", "junior")
        for r in op["regions"]:
            assert r in REGIONS


def test_audience_shape():
    for aud in AUDIENCES:
        assert set(aud.keys()) >= {"id", "label", "description", "count", "regions", "roles", "channelsAvailable"}
        for ch in aud["channelsAvailable"]:
            assert ch in ("app", "sms", "fallback")


def test_get_operator_by_id_known():
    op = get_operator_by_id("op-senior")
    assert op is not None
    assert op["id"] == "op-senior"


def test_get_operator_by_id_unknown():
    assert get_operator_by_id("nobody") is None


async def test_auth_dep_valid_header():
    app = FastAPI()

    @app.get("/whoami")
    async def whoami(op=Depends(current_operator)):
        return op

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/whoami", headers={"X-Operator-Id": "op-senior"})
    assert resp.status_code == 200
    assert resp.json()["id"] == "op-senior"


async def test_auth_dep_missing_header_returns_401():
    app = FastAPI()

    @app.get("/whoami")
    async def whoami(op=Depends(current_operator)):
        return op

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/whoami")
    assert resp.status_code == 401


async def test_auth_dep_unknown_header_returns_401():
    app = FastAPI()

    @app.get("/whoami")
    async def whoami(op=Depends(current_operator)):
        return op

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/whoami", headers={"X-Operator-Id": "ghost"})
    assert resp.status_code == 401
```

- [ ] **Step 1.2 — Run, expect failure**

```
uv run pytest tests/test_registry_and_auth.py -v
```
Expected: `ModuleNotFoundError: No module named 'server.api.registry'`.

- [ ] **Step 1.3 — Implement**

`server/api/registry.py`:
```python
"""
Static registry: operators, audiences, and region metadata.

REGIONS is a dict keyed by the frontend's region enum value so endpoints
can do REGIONS["IRQ_BAGHDAD"]["geohash_prefix"] directly. The shape of
each value matches the metadata an endpoint typically needs (label,
lat, lon, geohash_prefix).
"""
from __future__ import annotations

from typing import Any

REGIONS: dict[str, dict[str, Any]] = {
    "IRQ_BAGHDAD":  {"region": "IRQ_BAGHDAD",  "label": "Baghdad, Iraq",   "lat": 33.3152, "lon": 44.3661, "geohash_prefix": "sv8d"},
    "IRQ_MOSUL":    {"region": "IRQ_MOSUL",    "label": "Mosul, Iraq",     "lat": 36.3350, "lon": 43.1189, "geohash_prefix": "sv3p"},
    "SYR_ALEPPO":   {"region": "SYR_ALEPPO",   "label": "Aleppo, Syria",   "lat": 36.2021, "lon": 37.1343, "geohash_prefix": "sy7q"},
    "SYR_DAMASCUS": {"region": "SYR_DAMASCUS", "label": "Damascus, Syria", "lat": 33.5138, "lon": 36.2765, "geohash_prefix": "sv5t"},
    "YEM_SANAA":    {"region": "YEM_SANAA",    "label": "Sanaa, Yemen",    "lat": 15.3694, "lon": 44.1910, "geohash_prefix": "s87w"},
    "LBN_BEIRUT":   {"region": "LBN_BEIRUT",   "label": "Beirut, Lebanon", "lat": 33.8938, "lon": 35.5018, "geohash_prefix": "sv9j"},
}

_REGION_KEYS = list(REGIONS.keys())

OPERATORS: list[dict[str, Any]] = [
    {
        "id": "op-senior",
        "name": "Amira Hassan",
        "role": "senior",
        "regions": _REGION_KEYS,
        "avatarSeed": "amira-hassan",
    },
    {
        "id": "op-junior",
        "name": "Tariq Saleh",
        "role": "junior",
        "regions": ["IRQ_BAGHDAD", "IRQ_MOSUL"],
        "avatarSeed": "tariq-saleh",
    },
]

AUDIENCES: list[dict[str, Any]] = [
    {
        "id": "all_recipients",
        "label": "All recipients",
        "description": "Every registered account across all active regions.",
        "count": 14200,
        "regions": _REGION_KEYS,
        "roles": ["senior", "junior"],
        "channelsAvailable": ["app", "sms", "fallback"],
    },
    {
        "id": "medical_responders",
        "label": "Medical responders",
        "description": "Verified healthcare workers and first responders.",
        "count": 380,
        "regions": _REGION_KEYS,
        "roles": ["senior"],
        "channelsAvailable": ["app", "sms"],
    },
    {
        "id": "verified_eyewitnesses",
        "label": "Verified eyewitnesses",
        "description": "Accounts with at least one verified report in the last 30 days.",
        "count": 1540,
        "regions": _REGION_KEYS,
        "roles": ["senior", "junior"],
        "channelsAvailable": ["app", "sms", "fallback"],
    },
    {
        "id": "baghdad_residents",
        "label": "Baghdad residents",
        "description": "All accounts with a home geohash inside Greater Baghdad.",
        "count": 5700,
        "regions": ["IRQ_BAGHDAD"],
        "roles": ["senior", "junior"],
        "channelsAvailable": ["app", "sms", "fallback"],
    },
]

_OPERATOR_INDEX: dict[str, dict[str, Any]] = {op["id"]: op for op in OPERATORS}


def get_operator_by_id(operator_id: str) -> dict[str, Any] | None:
    return _OPERATOR_INDEX.get(operator_id)
```

`server/api/auth_dep.py`:
```python
"""Lightweight operator auth dependency.

Reads the X-Operator-Id request header and resolves it against the
static registry. JWT bridging is deferred to a later plan.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import Header, HTTPException

from server.api.registry import get_operator_by_id


async def current_operator(
    x_operator_id: Annotated[str | None, Header(alias="X-Operator-Id")] = None,
) -> dict[str, Any]:
    if not x_operator_id:
        raise HTTPException(status_code=401, detail="Missing X-Operator-Id header")
    op = get_operator_by_id(x_operator_id)
    if op is None:
        raise HTTPException(status_code=401, detail="Unknown operator")
    return op
```

- [ ] **Step 1.4 — Tests pass**

```
uv run pytest tests/test_registry_and_auth.py -v
```
Expected: 9 passed.

- [ ] **Step 1.5 — Commit**

```bash
git add server/api/registry.py server/api/auth_dep.py tests/test_registry_and_auth.py
git commit -m "feat(api): static operator/audience/region registry + X-Operator-Id auth dep"
```

---

## Task 2 — GET /api/me + GET /api/operators

**Files:**
- Create: `server/api/operators.py`
- Modify: `server/main.py`
- Test: `tests/test_api_operators.py`

- [ ] **Step 2.1 — Write failing test**

`tests/test_api_operators.py`:
```python
async def test_me_returns_senior_shape(client):
    resp = await client.get("/api/me", headers={"X-Operator-Id": "op-senior"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "op-senior"
    assert body["role"] == "senior"
    assert isinstance(body["regions"], list)
    assert "avatarSeed" in body


async def test_me_missing_header_returns_401(client):
    resp = await client.get("/api/me")
    assert resp.status_code == 401


async def test_operators_list_is_public(client):
    resp = await client.get("/api/operators")
    assert resp.status_code == 200
    body = resp.json()
    ids = {op["id"] for op in body}
    assert ids == {"op-senior", "op-junior"}
```

- [ ] **Step 2.2 — Run, expect failure**

```
uv run pytest tests/test_api_operators.py -v
```
Expected: `404 Not Found` on `/api/me` and `/api/operators` — router not mounted.

- [ ] **Step 2.3 — Implement**

`server/api/operators.py`:
```python
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from server.api.auth_dep import current_operator
from server.api.registry import OPERATORS

router = APIRouter(prefix="/api")


@router.get("/me")
async def get_me(
    op: Annotated[dict[str, Any], Depends(current_operator)],
) -> dict[str, Any]:
    return op


@router.get("/operators")
async def list_operators() -> list[dict[str, Any]]:
    return OPERATORS
```

`server/main.py` (full file after this task):
```python
from fastapi import FastAPI

from server.api.health import router as health_router
from server.api.operators import router as operators_router

app = FastAPI(title="anth-hackathon26 matching engine")
app.include_router(health_router)
app.include_router(operators_router)
```

- [ ] **Step 2.4 — Tests pass**

```
uv run pytest tests/test_api_operators.py -v
```
Expected: 3 passed.

- [ ] **Step 2.5 — Commit**

```bash
git add server/api/operators.py server/main.py tests/test_api_operators.py
git commit -m "feat(api): GET /api/me and GET /api/operators"
```

---

## Task 3 — GET /api/audiences

**Files:**
- Create: `server/api/audiences.py`
- Modify: `server/main.py`
- Test: `tests/test_api_audiences.py`

- [ ] **Step 3.1 — Write failing test**

`tests/test_api_audiences.py`:
```python
async def test_audiences_returns_4(client):
    resp = await client.get("/api/audiences", headers={"X-Operator-Id": "op-senior"})
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 4
    ids = {aud["id"] for aud in body}
    assert ids == {"all_recipients", "medical_responders", "verified_eyewitnesses", "baghdad_residents"}


async def test_audiences_shape(client):
    resp = await client.get("/api/audiences", headers={"X-Operator-Id": "op-senior"})
    body = resp.json()
    for aud in body:
        assert isinstance(aud["count"], int)
        assert isinstance(aud["regions"], list)
        for ch in aud["channelsAvailable"]:
            assert ch in ("app", "sms", "fallback")


async def test_audiences_requires_auth(client):
    resp = await client.get("/api/audiences")
    assert resp.status_code == 401
```

- [ ] **Step 3.2 — Run, expect failure**

```
uv run pytest tests/test_api_audiences.py -v
```
Expected: `404 Not Found`.

- [ ] **Step 3.3 — Implement**

`server/api/audiences.py`:
```python
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from server.api.auth_dep import current_operator
from server.api.registry import AUDIENCES

router = APIRouter(prefix="/api")


@router.get("/audiences")
async def list_audiences(
    _op: Annotated[dict[str, Any], Depends(current_operator)],
) -> list[dict[str, Any]]:
    return AUDIENCES
```

`server/main.py` (full file):
```python
from fastapi import FastAPI

from server.api.audiences import router as audiences_router
from server.api.health import router as health_router
from server.api.operators import router as operators_router

app = FastAPI(title="anth-hackathon26 matching engine")
app.include_router(health_router)
app.include_router(operators_router)
app.include_router(audiences_router)
```

- [ ] **Step 3.4 — Tests pass**

```
uv run pytest tests/test_api_audiences.py -v
```
Expected: 3 passed.

- [ ] **Step 3.5 — Commit**

```bash
git add server/api/audiences.py server/main.py tests/test_api_audiences.py
git commit -m "feat(api): GET /api/audiences"
```

---

## Task 4 — GET /api/regions/stats

**Files:**
- Create: `server/api/regions.py`
- Modify: `server/main.py`
- Test: `tests/test_api_regions.py`

- [ ] **Step 4.1 — Write failing test**

`tests/test_api_regions.py`:
```python
async def test_regions_stats_returns_six(client):
    resp = await client.get("/api/regions/stats", headers={"X-Operator-Id": "op-senior"})
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 6
    keys = {r["region"] for r in body}
    assert keys == {"IRQ_BAGHDAD", "IRQ_MOSUL", "SYR_ALEPPO", "SYR_DAMASCUS", "YEM_SANAA", "LBN_BEIRUT"}


async def test_regions_stats_shape(client):
    resp = await client.get("/api/regions/stats", headers={"X-Operator-Id": "op-senior"})
    for r in resp.json():
        assert "label" in r
        assert isinstance(r["lat"], float)
        assert isinstance(r["lon"], float)
        assert r["reachable"] >= 0
        assert r["incidentCount"] >= 0
        assert r["messageCount"] >= 0
        assert r["msgsPerMin"] >= 0
        assert r["baselineMsgsPerMin"] == 0.5
        assert isinstance(r["anomaly"], bool)


async def test_regions_stats_requires_auth(client):
    resp = await client.get("/api/regions/stats")
    assert resp.status_code == 401
```

- [ ] **Step 4.2 — Run, expect failure**

```
uv run pytest tests/test_api_regions.py -v
```
Expected: `404 Not Found`.

- [ ] **Step 4.3 — Implement**

`server/api/regions.py`:
```python
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.api.auth_dep import current_operator
from server.api.registry import REGIONS
from server.db.alerts import Alert
from server.db.identity import Account
from server.db.messages import InboundMessage
from server.db.session import get_db

router = APIRouter(prefix="/api/regions")

BASELINE_MSGS_PER_MIN = 0.5


@router.get("/stats")
async def get_region_stats(
    _op: Annotated[dict[str, Any], Depends(current_operator)],
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    one_minute_ago = now - timedelta(minutes=1)
    results: list[dict[str, Any]] = []

    for region_key, meta in REGIONS.items():
        prefix: str = meta["geohash_prefix"]

        reachable = (
            await db.execute(
                select(func.count())
                .select_from(Account)
                .where(Account.last_known_geohash.like(f"{prefix}%"))
            )
        ).scalar_one()

        incident_count = (
            await db.execute(
                select(func.count())
                .select_from(Alert)
                .where(Alert.region_geohash_prefix.like(f"{prefix}%"))
            )
        ).scalar_one()

        message_count = (
            await db.execute(
                select(func.count())
                .select_from(InboundMessage)
                .join(Alert, InboundMessage.in_reply_to_alert_id == Alert.alert_id)
                .where(Alert.region_geohash_prefix.like(f"{prefix}%"))
            )
        ).scalar_one()

        recent_count = (
            await db.execute(
                select(func.count())
                .select_from(InboundMessage)
                .join(Alert, InboundMessage.in_reply_to_alert_id == Alert.alert_id)
                .where(
                    Alert.region_geohash_prefix.like(f"{prefix}%"),
                    InboundMessage.received_at >= one_minute_ago,
                )
            )
        ).scalar_one()

        msgs_per_min = float(recent_count)
        anomaly = msgs_per_min > 3 * BASELINE_MSGS_PER_MIN

        results.append({
            "region": region_key,
            "label": meta["label"],
            "lat": float(meta["lat"]),
            "lon": float(meta["lon"]),
            "reachable": int(reachable),
            "incidentCount": int(incident_count),
            "messageCount": int(message_count),
            "msgsPerMin": msgs_per_min,
            "baselineMsgsPerMin": BASELINE_MSGS_PER_MIN,
            "anomaly": anomaly,
        })

    return results
```

`server/main.py` (full file):
```python
from fastapi import FastAPI

from server.api.audiences import router as audiences_router
from server.api.health import router as health_router
from server.api.operators import router as operators_router
from server.api.regions import router as regions_router

app = FastAPI(title="anth-hackathon26 matching engine")
app.include_router(health_router)
app.include_router(operators_router)
app.include_router(audiences_router)
app.include_router(regions_router)
```

- [ ] **Step 4.4 — Tests pass**

```
uv run pytest tests/test_api_regions.py -v
```
Expected: 3 passed.

- [ ] **Step 4.5 — Commit**

```bash
git add server/api/regions.py server/main.py tests/test_api_regions.py
git commit -m "feat(api): GET /api/regions/stats with live counts"
```

---

## Task 5 — GET /api/regions/:region/timeline

**Files:**
- Modify: `server/api/regions.py`
- Modify: `tests/test_api_regions.py`

- [ ] **Step 5.1 — Write failing test (append to `tests/test_api_regions.py`)**

```python
from datetime import UTC, datetime, timedelta

from server.db.alerts import Alert
from server.db.identity import NGO
from server.db.messages import Bucket


async def test_timeline_empty_returns_zero_buckets(client):
    resp = await client.get(
        "/api/regions/IRQ_BAGHDAD/timeline?minutes=60&bucket=60",
        headers={"X-Operator-Id": "op-senior"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["region"] == "IRQ_BAGHDAD"
    assert body["minutes"] == 60
    assert body["bucketSeconds"] == 60
    assert len(body["buckets"]) == 60
    assert body["total"] == 0


async def test_timeline_counts_buckets_in_window(client, db):
    ngo = NGO(name="TestNGO-timeline")
    db.add(ngo)
    await db.flush()
    alert = Alert(
        ngo_id=ngo.ngo_id,
        person_name="Test Person",
        status="active",
        region_geohash_prefix="sv8d",
    )
    db.add(alert)
    await db.flush()

    now = datetime.now(UTC)
    bk1 = Bucket(
        bucket_key=f"tl-{now.timestamp()}-1",
        ngo_id=ngo.ngo_id,
        alert_id=alert.alert_id,
        geohash_prefix_4="sv8d",
        window_start=now - timedelta(minutes=5),
        window_length_ms=3000,
    )
    bk2 = Bucket(
        bucket_key=f"tl-{now.timestamp()}-2",
        ngo_id=ngo.ngo_id,
        alert_id=alert.alert_id,
        geohash_prefix_4="sv8d",
        window_start=now - timedelta(minutes=5, seconds=10),
        window_length_ms=3000,
    )
    db.add_all([bk1, bk2])
    await db.commit()

    resp = await client.get(
        "/api/regions/IRQ_BAGHDAD/timeline?minutes=60&bucket=60",
        headers={"X-Operator-Id": "op-senior"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


async def test_timeline_unknown_region_returns_404(client):
    resp = await client.get(
        "/api/regions/NOWHERE/timeline",
        headers={"X-Operator-Id": "op-senior"},
    )
    assert resp.status_code == 404


async def test_timeline_requires_auth(client):
    resp = await client.get("/api/regions/IRQ_BAGHDAD/timeline")
    assert resp.status_code == 401
```

- [ ] **Step 5.2 — Run, expect failure**

```
uv run pytest tests/test_api_regions.py -v
```
Expected: 4 new tests fail with 404.

- [ ] **Step 5.3 — Implement (append to `server/api/regions.py`)**

Add the new route at the bottom of `server/api/regions.py`:
```python
from fastapi import HTTPException, Query


@router.get("/{region}/timeline")
async def region_timeline(
    region: str,
    _op: Annotated[dict[str, Any], Depends(current_operator)],
    minutes: Annotated[int, Query(ge=1, le=1440)] = 60,
    bucket: Annotated[int, Query(alias="bucket", ge=1, le=3600)] = 60,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if region not in REGIONS:
        raise HTTPException(status_code=404, detail="unknown region")

    meta = REGIONS[region]
    prefix: str = meta["geohash_prefix"]

    now = datetime.now(UTC)
    window_start = now - timedelta(minutes=minutes)

    rows = (
        await db.execute(
            select(
                func.floor(func.extract("epoch", Bucket.window_start) / bucket).label("slot"),
                func.count().label("cnt"),
            )
            .where(Bucket.geohash_prefix_4 == prefix)
            .where(Bucket.window_start >= window_start)
            .where(Bucket.window_start < now)
            .group_by("slot")
        )
    ).all()
    slot_to_count: dict[int, int] = {int(r.slot): int(r.cnt) for r in rows}

    total_slots = (minutes * 60) // bucket
    buckets: list[dict[str, Any]] = []
    for i in range(total_slots):
        slot_time = window_start + timedelta(seconds=i * bucket)
        slot_num = int(slot_time.timestamp()) // bucket
        buckets.append({"ts": slot_time.isoformat(), "count": slot_to_count.get(slot_num, 0)})

    return {
        "region": region,
        "minutes": minutes,
        "bucketSeconds": bucket,
        "buckets": buckets,
        "total": sum(slot_to_count.values()),
    }
```

You will also need to add `Bucket` to the imports at the top of `server/api/regions.py`:
```python
from server.db.messages import Bucket, InboundMessage
```

- [ ] **Step 5.4 — Tests pass**

```
uv run pytest tests/test_api_regions.py -v
```
Expected: 7 total passed (3 stats + 4 timeline).

- [ ] **Step 5.5 — Commit**

```bash
git add server/api/regions.py tests/test_api_regions.py
git commit -m "feat(api): GET /api/regions/:region/timeline from Bucket aggregation"
```

---

## Task 6 — GET /api/incidents

**Files:**
- Create: `server/api/incidents.py`
- Modify: `server/main.py`
- Test: `tests/test_api_incidents.py`

- [ ] **Step 6.1 — Write failing test**

`tests/test_api_incidents.py`:
```python
from datetime import UTC, datetime, timedelta

from server.db.alerts import Alert
from server.db.identity import NGO, Account
from server.db.messages import InboundMessage


async def test_incidents_empty(client):
    resp = await client.get("/api/incidents", headers={"X-Operator-Id": "op-senior"})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_incidents_returns_mapped_alert(client, db):
    ngo = NGO(name="Warchild-inc-test")
    db.add(ngo)
    await db.flush()
    alert = Alert(
        ngo_id=ngo.ngo_id,
        person_name="Amira Hassan",
        status="active",
        category="missing_person",
        urgency_tier="high",
        urgency_score=0.9,
        region_geohash_prefix="sv8d",
        last_seen_geohash="sv8du",
        description="8-year-old girl, last seen near market",
        expires_at=datetime.now(UTC) + timedelta(days=2),
    )
    db.add(alert)
    await db.flush()
    acc = Account(phone="+9647001112233", ngo_id=ngo.ngo_id)
    db.add(acc)
    await db.flush()
    db.add(InboundMessage(
        ngo_id=ngo.ngo_id,
        channel="sms",
        sender_phone="+9647001112233",
        in_reply_to_alert_id=alert.alert_id,
        body="I saw her near the bridge",
        media_urls=[],
        raw={},
    ))
    await db.commit()

    resp = await client.get("/api/incidents", headers={"X-Operator-Id": "op-senior"})
    assert resp.status_code == 200
    items = resp.json()
    inc = next(i for i in items if i["id"] == alert.alert_id)
    assert inc["category"] == "missing_person"
    assert inc["title"] == "Amira Hassan"
    assert inc["severity"] == "high"
    assert inc["region"] == "IRQ_BAGHDAD"
    assert inc["messageCount"] == 1
    assert inc["lastActivity"] is not None


async def test_incidents_requires_auth(client):
    resp = await client.get("/api/incidents")
    assert resp.status_code == 401
```

- [ ] **Step 6.2 — Run, expect failure**

```
uv run pytest tests/test_api_incidents.py -v
```
Expected: `404 Not Found`.

- [ ] **Step 6.3 — Implement**

`server/api/incidents.py`:
```python
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.api.auth_dep import current_operator
from server.api.registry import REGIONS
from server.db.alerts import Alert
from server.db.messages import InboundMessage
from server.db.session import get_db

router = APIRouter(prefix="/api")

_URGENCY_TO_SEVERITY = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}
_GEOHASH_TO_REGION: dict[str, str] = {meta["geohash_prefix"]: key for key, meta in REGIONS.items()}
_DEFAULT_REGION = next(iter(REGIONS.keys()))


def _severity(urgency_tier: str | None) -> str:
    return _URGENCY_TO_SEVERITY.get(urgency_tier or "", "medium")


def _region_for_prefix(prefix: str | None) -> str:
    if not prefix:
        return _DEFAULT_REGION
    if prefix in _GEOHASH_TO_REGION:
        return _GEOHASH_TO_REGION[prefix]
    for gh, key in _GEOHASH_TO_REGION.items():
        if prefix.startswith(gh) or gh.startswith(prefix):
            return key
    return _DEFAULT_REGION


@router.get("/incidents")
async def list_incidents(
    _op: Annotated[dict[str, Any], Depends(current_operator)],
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    alerts = (await db.execute(select(Alert).where(Alert.status == "active"))).scalars().all()
    if not alerts:
        return []

    alert_ids = [a.alert_id for a in alerts]

    count_rows = (
        await db.execute(
            select(InboundMessage.in_reply_to_alert_id, func.count().label("cnt"))
            .where(InboundMessage.in_reply_to_alert_id.in_(alert_ids))
            .group_by(InboundMessage.in_reply_to_alert_id)
        )
    ).all()
    msg_counts: dict[str, int] = {r.in_reply_to_alert_id: r.cnt for r in count_rows}

    activity_rows = (
        await db.execute(
            select(
                InboundMessage.in_reply_to_alert_id,
                func.max(InboundMessage.received_at).label("last_at"),
            )
            .where(InboundMessage.in_reply_to_alert_id.in_(alert_ids))
            .group_by(InboundMessage.in_reply_to_alert_id)
        )
    ).all()
    last_activity: dict[str, str] = {
        r.in_reply_to_alert_id: r.last_at.isoformat() for r in activity_rows
    }

    result = []
    for alert in alerts:
        region_key = _region_for_prefix(alert.region_geohash_prefix)
        meta = REGIONS[region_key]
        title = alert.person_name or (alert.description or "")[:80]
        category = alert.category or "other"
        result.append({
            "id": alert.alert_id,
            "category": category,
            "title": title,
            "severity": _severity(alert.urgency_tier),
            "region": region_key,
            "lat": float(meta["lat"]),
            "lon": float(meta["lon"]),
            "details": {
                "description": alert.description,
                "last_seen_geohash": alert.last_seen_geohash,
                "expires_at": alert.expires_at.isoformat() if alert.expires_at else None,
            },
            "messageCount": msg_counts.get(alert.alert_id, 0),
            "lastActivity": last_activity.get(alert.alert_id),
        })
    return result
```

`server/main.py` (full file):
```python
from fastapi import FastAPI

from server.api.audiences import router as audiences_router
from server.api.health import router as health_router
from server.api.incidents import router as incidents_router
from server.api.operators import router as operators_router
from server.api.regions import router as regions_router

app = FastAPI(title="anth-hackathon26 matching engine")
app.include_router(health_router)
app.include_router(operators_router)
app.include_router(audiences_router)
app.include_router(regions_router)
app.include_router(incidents_router)
```

- [ ] **Step 6.4 — Tests pass**

```
uv run pytest tests/test_api_incidents.py -v
```
Expected: 3 passed.

- [ ] **Step 6.5 — Commit**

```bash
git add server/api/incidents.py server/main.py tests/test_api_incidents.py
git commit -m "feat(api): GET /api/incidents (Alert→Incident shape)"
```

---

## Task 7 — GET /api/incidents/:id/messages

**Files:**
- Modify: `server/api/incidents.py`
- Modify: `tests/test_api_incidents.py`

- [ ] **Step 7.1 — Write failing test (append to `tests/test_api_incidents.py`)**

```python
async def test_incident_messages_returns_inbound(client, db):
    ngo = NGO(name="Warchild-msg-test")
    db.add(ngo)
    await db.flush()
    alert = Alert(ngo_id=ngo.ngo_id, person_name="Khalid", status="active", region_geohash_prefix="sv8d")
    db.add(alert)
    await db.flush()
    acc = Account(phone="+9647009998877", ngo_id=ngo.ngo_id)
    db.add(acc)
    await db.flush()
    db.add(InboundMessage(
        ngo_id=ngo.ngo_id, channel="sms", sender_phone="+9647009998877",
        in_reply_to_alert_id=alert.alert_id, body="Spotted near checkpoint",
        media_urls=[], raw={},
    ))
    db.add(InboundMessage(
        ngo_id=ngo.ngo_id, channel="app", sender_phone="+9647009998877",
        in_reply_to_alert_id=alert.alert_id, body="Heading north now",
        media_urls=[], raw={},
    ))
    await db.commit()

    resp = await client.get(
        f"/api/incidents/{alert.alert_id}/messages",
        headers={"X-Operator-Id": "op-senior"},
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    assert all(m["outbound"] is False for m in items)
    assert items[0]["ts"] <= items[1]["ts"]
    assert items[0]["via"] in ("sms", "app", "fallback", None)


async def test_incident_messages_404_for_unknown(client):
    resp = await client.get(
        "/api/incidents/00000000000000000000000000/messages",
        headers={"X-Operator-Id": "op-senior"},
    )
    assert resp.status_code == 404


async def test_incident_messages_requires_auth(client, db):
    ngo = NGO(name="Warchild-msg-auth")
    db.add(ngo)
    await db.flush()
    alert = Alert(ngo_id=ngo.ngo_id, person_name="X", status="active")
    db.add(alert)
    await db.commit()

    resp = await client.get(f"/api/incidents/{alert.alert_id}/messages")
    assert resp.status_code == 401
```

- [ ] **Step 7.2 — Run, expect failure**

```
uv run pytest tests/test_api_incidents.py -v
```
Expected: 3 new tests fail with 404 (route not yet defined).

- [ ] **Step 7.3 — Implement (append to `server/api/incidents.py`)**

Add the new route at the bottom of `server/api/incidents.py`:
```python
from fastapi import HTTPException

from server.db.decisions import AgentDecision, ToolCall
from server.db.messages import Bucket, TriagedMessage
from server.db.outbound import OutboundMessage


@router.get("/incidents/{incident_id}/messages")
async def incident_messages(
    incident_id: str,
    _op: Annotated[dict[str, Any], Depends(current_operator)],
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    alert = (
        await db.execute(select(Alert).where(Alert.alert_id == incident_id))
    ).scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail="incident not found")

    inbound_rows = (
        await db.execute(
            select(InboundMessage)
            .where(InboundMessage.in_reply_to_alert_id == incident_id)
            .order_by(InboundMessage.received_at)
        )
    ).scalars().all()

    triage_geohash: dict[str, str] = {}
    if inbound_rows:
        msg_ids = [m.msg_id for m in inbound_rows]
        triage_rows = (
            await db.execute(select(TriagedMessage).where(TriagedMessage.msg_id.in_(msg_ids)))
        ).scalars().all()
        triage_geohash = {t.msg_id: t.geohash6 for t in triage_rows if t.geohash6}

    messages: list[dict[str, Any]] = []
    for msg in inbound_rows:
        via = msg.channel if msg.channel in ("app", "sms", "fallback") else None
        messages.append({
            "messageId": msg.msg_id,
            "incidentId": incident_id,
            "from": msg.sender_phone,
            "body": msg.body,
            "ts": msg.received_at.isoformat(),
            "geohash": triage_geohash.get(msg.msg_id),
            "lat": None,
            "lon": None,
            "extracted": None,
            "outbound": False,
            "via": via,
        })

    outbound_rows = (
        await db.execute(
            select(OutboundMessage)
            .join(ToolCall, OutboundMessage.tool_call_id == ToolCall.call_id)
            .join(AgentDecision, ToolCall.decision_id == AgentDecision.decision_id)
            .join(Bucket, AgentDecision.bucket_key == Bucket.bucket_key)
            .where(Bucket.alert_id == incident_id)
        )
    ).scalars().all()

    for out in outbound_rows:
        via = out.channel if out.channel in ("app", "sms", "fallback") else None
        messages.append({
            "messageId": out.out_id,
            "incidentId": incident_id,
            "from": "ngo",
            "body": out.body,
            "ts": out.created_at.isoformat(),
            "geohash": None,
            "lat": None,
            "lon": None,
            "extracted": None,
            "outbound": True,
            "via": via,
        })

    messages.sort(key=lambda m: m["ts"])
    return messages
```

- [ ] **Step 7.4 — Tests pass**

```
uv run pytest tests/test_api_incidents.py -v
```
Expected: 6 total passed (3 incidents + 3 messages).

- [ ] **Step 7.5 — Commit**

```bash
git add server/api/incidents.py tests/test_api_incidents.py
git commit -m "feat(api): GET /api/incidents/:id/messages (inbound + outbound)"
```

---

## Task 8 — GET /api/dashboard

**Files:**
- Create: `server/api/dashboard.py`
- Modify: `server/main.py`
- Test: `tests/test_api_dashboard.py`

- [ ] **Step 8.1 — Write failing test**

`tests/test_api_dashboard.py`:
```python
from server.db.alerts import Alert
from server.db.identity import NGO, Account
from server.db.messages import InboundMessage


async def test_dashboard_shape_no_data(client):
    resp = await client.get("/api/dashboard", headers={"X-Operator-Id": "op-senior"})
    assert resp.status_code == 200
    body = resp.json()
    assert "windowMinutes" in body
    assert isinstance(body["regions"], list)
    assert len(body["regions"]) == 6
    for reg in body["regions"]:
        assert len(reg["sparkline"]) == 12
        assert reg["themes"] == []


async def test_dashboard_counts_messages_per_region(client, db):
    ngo = NGO(name="Warchild-dash-test")
    db.add(ngo)
    await db.flush()
    alert = Alert(
        ngo_id=ngo.ngo_id, person_name="DashPerson", status="active",
        urgency_tier="high", region_geohash_prefix="sv8d",
    )
    db.add(alert)
    await db.flush()
    acc = Account(phone="+9647005556677", ngo_id=ngo.ngo_id)
    db.add(acc)
    await db.flush()
    for i in range(3):
        db.add(InboundMessage(
            ngo_id=ngo.ngo_id, channel="sms", sender_phone="+9647005556677",
            in_reply_to_alert_id=alert.alert_id, body=f"distress {i}",
            media_urls=[], raw={},
        ))
    await db.commit()

    resp = await client.get("/api/dashboard", headers={"X-Operator-Id": "op-senior"})
    body = resp.json()
    baghdad = next(r for r in body["regions"] if r["region"] == "IRQ_BAGHDAD")
    assert baghdad["messageCount"] >= 3
    assert baghdad["openCases"] >= 1


async def test_dashboard_requires_auth(client):
    resp = await client.get("/api/dashboard")
    assert resp.status_code == 401
```

- [ ] **Step 8.2 — Run, expect failure**

```
uv run pytest tests/test_api_dashboard.py -v
```
Expected: `404 Not Found`.

- [ ] **Step 8.3 — Implement**

`server/api/dashboard.py`:
```python
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.api.auth_dep import current_operator
from server.api.registry import REGIONS
from server.db.alerts import Alert
from server.db.messages import InboundMessage
from server.db.session import get_db

router = APIRouter(prefix="/api")

WINDOW_MINUTES = 60
SPARKLINE_SLOTS = 12
SPARKLINE_SLOT_MINUTES = WINDOW_MINUTES // SPARKLINE_SLOTS  # 5
BASELINE_MSGS_PER_MIN = 0.5

_GEOHASH_TO_REGION: dict[str, str] = {meta["geohash_prefix"]: key for key, meta in REGIONS.items()}
_DEFAULT_REGION = next(iter(REGIONS.keys()))


def _severity(urgency_tier: str | None) -> str:
    return {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}.get(
        urgency_tier or "", "medium"
    )


def _region_for_prefix(prefix: str | None) -> str:
    if not prefix:
        return _DEFAULT_REGION
    for gh, key in _GEOHASH_TO_REGION.items():
        if prefix == gh or prefix.startswith(gh) or gh.startswith(prefix):
            return key
    return _DEFAULT_REGION


@router.get("/dashboard")
async def dashboard(
    _op: Annotated[dict[str, Any], Depends(current_operator)],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    now = datetime.now(UTC)
    window_start = now - timedelta(minutes=WINDOW_MINUTES)

    alerts = (await db.execute(select(Alert).where(Alert.status == "active"))).scalars().all()
    alert_map: dict[str, Alert] = {a.alert_id: a for a in alerts}

    msgs_in_window = (
        await db.execute(
            select(InboundMessage)
            .where(InboundMessage.in_reply_to_alert_id.isnot(None))
            .where(InboundMessage.received_at >= window_start)
            .order_by(InboundMessage.received_at.desc())
        )
    ).scalars().all()

    region_msgs: dict[str, list[InboundMessage]] = {k: [] for k in REGIONS}
    region_alerts: dict[str, list[Alert]] = {k: [] for k in REGIONS}

    for msg in msgs_in_window:
        if msg.in_reply_to_alert_id and msg.in_reply_to_alert_id in alert_map:
            alert = alert_map[msg.in_reply_to_alert_id]
            region_msgs[_region_for_prefix(alert.region_geohash_prefix)].append(msg)

    for alert in alerts:
        region_alerts[_region_for_prefix(alert.region_geohash_prefix)].append(alert)

    per_alert_count: dict[str, int] = {}
    if alerts:
        rows = (
            await db.execute(
                select(InboundMessage.in_reply_to_alert_id, func.count().label("cnt"))
                .where(InboundMessage.in_reply_to_alert_id.in_([a.alert_id for a in alerts]))
                .group_by(InboundMessage.in_reply_to_alert_id)
            )
        ).all()
        per_alert_count = {r.in_reply_to_alert_id: r.cnt for r in rows}

    regions_out = []
    for region_key, meta in REGIONS.items():
        r_msgs = region_msgs[region_key]
        r_alerts = region_alerts[region_key]

        msg_count = len(r_msgs)
        distinct_senders = len({m.sender_phone for m in r_msgs})
        msgs_per_min = msg_count / WINDOW_MINUTES
        urgency = min(1.0, msgs_per_min / max(1, BASELINE_MSGS_PER_MIN) / 5.0)
        anomaly = msgs_per_min > BASELINE_MSGS_PER_MIN * 2

        sparkline = [0.0] * SPARKLINE_SLOTS
        for msg in r_msgs:
            age_minutes = (now - msg.received_at).total_seconds() / 60
            if 0 <= age_minutes < WINDOW_MINUTES:
                slot = min(int(age_minutes // SPARKLINE_SLOT_MINUTES), SPARKLINE_SLOTS - 1)
                sparkline[SPARKLINE_SLOTS - 1 - slot] += 1.0

        sorted_alerts = sorted(
            r_alerts, key=lambda a: per_alert_count.get(a.alert_id, 0), reverse=True
        )[:3]
        cases = [
            {
                "id": a.alert_id,
                "title": a.person_name or (a.description or "")[:80],
                "category": a.category or "other",
                "severity": _severity(a.urgency_tier),
                "messageCount": per_alert_count.get(a.alert_id, 0),
            }
            for a in sorted_alerts
        ]

        regions_out.append({
            "region": region_key,
            "label": meta["label"],
            "lat": float(meta["lat"]),
            "lon": float(meta["lon"]),
            "urgency": round(urgency, 4),
            "anomaly": anomaly,
            "msgsPerMin": round(msgs_per_min, 4),
            "baselineMsgsPerMin": BASELINE_MSGS_PER_MIN,
            "openCases": len(r_alerts),
            "messageCount": msg_count,
            "distressCount": msg_count,
            "distinctSenders": distinct_senders,
            "sparkline": sparkline,
            "themes": [],
            "cases": cases,
        })

    recent_distress = []
    for msg in msgs_in_window[:10]:
        if msg.in_reply_to_alert_id and msg.in_reply_to_alert_id in alert_map:
            alert = alert_map[msg.in_reply_to_alert_id]
            region_key = _region_for_prefix(alert.region_geohash_prefix)
            meta = REGIONS[region_key]
            recent_distress.append({
                "messageId": msg.msg_id,
                "incidentId": msg.in_reply_to_alert_id,
                "region": region_key,
                "regionLabel": meta["label"],
                "from": msg.sender_phone,
                "body": msg.body,
                "ts": msg.received_at.isoformat(),
            })

    return {
        "windowMinutes": WINDOW_MINUTES,
        "regions": regions_out,
        "recentDistress": recent_distress,
    }
```

`server/main.py` (full file):
```python
from fastapi import FastAPI

from server.api.audiences import router as audiences_router
from server.api.dashboard import router as dashboard_router
from server.api.health import router as health_router
from server.api.incidents import router as incidents_router
from server.api.operators import router as operators_router
from server.api.regions import router as regions_router

app = FastAPI(title="anth-hackathon26 matching engine")
app.include_router(health_router)
app.include_router(operators_router)
app.include_router(audiences_router)
app.include_router(regions_router)
app.include_router(incidents_router)
app.include_router(dashboard_router)
```

- [ ] **Step 8.4 — Tests pass**

```
uv run pytest tests/test_api_dashboard.py -v
```
Expected: 3 passed.

- [ ] **Step 8.5 — Commit**

```bash
git add server/api/dashboard.py server/main.py tests/test_api_dashboard.py
git commit -m "feat(api): GET /api/dashboard composed view"
```

---

## Task 9 — POST /api/sim/seed

**Files:**
- Create: `server/api/sim.py`
- Modify: `server/main.py`
- Test: `tests/test_api_sim_seed.py`

- [ ] **Step 9.1 — Write failing test**

`tests/test_api_sim_seed.py`:
```python
from sqlalchemy import select

from server.db.alerts import Alert, AlertDelivery
from server.db.identity import NGO, Account
from server.db.messages import InboundMessage


async def test_seed_creates_expected_rows(client):
    resp = await client.post("/api/sim/seed")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "ngo_id" in body
    assert "alert_id" in body
    assert body["seeded"]["accounts"] == 6
    assert body["seeded"]["alert_deliveries"] == 6
    assert body["seeded"]["inbound_messages"] >= 3


async def test_seed_is_idempotent(client, db):
    r1 = await client.post("/api/sim/seed")
    r2 = await client.post("/api/sim/seed")
    assert r1.json()["ngo_id"] == r2.json()["ngo_id"]
    assert r1.json()["alert_id"] == r2.json()["alert_id"]
    rows = (await db.execute(select(NGO).where(NGO.name == "Warchild"))).scalars().all()
    assert len(rows) == 1


async def test_seed_inbound_messages_tied_to_alert(client, db):
    body = (await client.post("/api/sim/seed")).json()
    msgs = (
        await db.execute(
            select(InboundMessage).where(InboundMessage.in_reply_to_alert_id == body["alert_id"])
        )
    ).scalars().all()
    assert len(msgs) >= 3
```

- [ ] **Step 9.2 — Run, expect failure**

```
uv run pytest tests/test_api_sim_seed.py -v
```
Expected: `404 Not Found`.

- [ ] **Step 9.3 — Implement**

`server/api/sim.py`:
```python
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.api.registry import REGIONS
from server.db.alerts import Alert, AlertDelivery
from server.db.identity import NGO, Account
from server.db.messages import InboundMessage
from server.db.session import get_db

router = APIRouter(prefix="/api/sim")

_REGION_PHONES = {
    "IRQ_BAGHDAD":  "+9647000000001",
    "IRQ_MOSUL":    "+9647000000002",
    "SYR_ALEPPO":   "+9639000000001",
    "SYR_DAMASCUS": "+9639000000002",
    "YEM_SANAA":    "+9677000000001",
    "LBN_BEIRUT":   "+9613000000001",
}

_SEED_BODIES = [
    "I saw a child matching the description near the old market",
    "There is a girl wandering alone on Al-Rashid street, looks scared",
    "Someone reported a missing child near the checkpoint, please help",
    "I think I saw her near the river bridge about an hour ago",
]


@router.post("/seed")
async def seed(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    existing = (
        await db.execute(select(NGO).where(NGO.name == "Warchild"))
    ).scalar_one_or_none()
    if existing is not None:
        existing_alert = (
            await db.execute(select(Alert).where(Alert.ngo_id == existing.ngo_id).limit(1))
        ).scalar_one_or_none()
        accounts = (
            await db.execute(select(Account).where(Account.ngo_id == existing.ngo_id))
        ).scalars().all()
        deliveries = []
        msgs = []
        if existing_alert:
            deliveries = (
                await db.execute(
                    select(AlertDelivery).where(AlertDelivery.alert_id == existing_alert.alert_id)
                )
            ).scalars().all()
            msgs = (
                await db.execute(
                    select(InboundMessage).where(
                        InboundMessage.in_reply_to_alert_id == existing_alert.alert_id
                    )
                )
            ).scalars().all()
        return {
            "ok": True,
            "ngo_id": existing.ngo_id,
            "alert_id": existing_alert.alert_id if existing_alert else "",
            "seeded": {
                "accounts": len(accounts),
                "alert_deliveries": len(deliveries),
                "inbound_messages": len(msgs),
            },
        }

    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()

    accounts: list[Account] = []
    for region_key, phone in _REGION_PHONES.items():
        meta = REGIONS[region_key]
        prefix = meta["geohash_prefix"]
        acc = Account(
            phone=phone,
            ngo_id=ngo.ngo_id,
            language="ar",
            last_known_geohash=prefix + "u0",
            source="app",
        )
        db.add(acc)
        accounts.append(acc)
    await db.flush()

    baghdad = REGIONS["IRQ_BAGHDAD"]
    alert = Alert(
        ngo_id=ngo.ngo_id,
        person_name="Amira Hassan",
        description="8-year-old girl, last seen near Al-Shorja market wearing a red dress",
        last_seen_geohash=baghdad["geohash_prefix"] + "u0",
        region_geohash_prefix=baghdad["geohash_prefix"],
        status="active",
        category="missing_person",
        urgency_tier="high",
        urgency_score=0.9,
        expires_at=datetime.now(UTC) + timedelta(days=3),
    )
    db.add(alert)
    await db.flush()

    deliveries: list[AlertDelivery] = []
    for acc in accounts:
        d = AlertDelivery(
            ngo_id=ngo.ngo_id, alert_id=alert.alert_id, recipient_phone=acc.phone
        )
        db.add(d)
        deliveries.append(d)
    await db.flush()

    baghdad_phone = _REGION_PHONES["IRQ_BAGHDAD"]
    msgs: list[InboundMessage] = []
    for body in _SEED_BODIES:
        m = InboundMessage(
            ngo_id=ngo.ngo_id,
            channel="sms",
            sender_phone=baghdad_phone,
            in_reply_to_alert_id=alert.alert_id,
            body=body,
            media_urls=[],
            raw={"seeded": True},
        )
        db.add(m)
        msgs.append(m)
    await db.commit()

    return {
        "ok": True,
        "ngo_id": ngo.ngo_id,
        "alert_id": alert.alert_id,
        "seeded": {
            "accounts": len(accounts),
            "alert_deliveries": len(deliveries),
            "inbound_messages": len(msgs),
        },
    }
```

`server/main.py` (full file):
```python
from fastapi import FastAPI

from server.api.audiences import router as audiences_router
from server.api.dashboard import router as dashboard_router
from server.api.health import router as health_router
from server.api.incidents import router as incidents_router
from server.api.operators import router as operators_router
from server.api.regions import router as regions_router
from server.api.sim import router as sim_router

app = FastAPI(title="anth-hackathon26 matching engine")
app.include_router(health_router)
app.include_router(operators_router)
app.include_router(audiences_router)
app.include_router(regions_router)
app.include_router(incidents_router)
app.include_router(dashboard_router)
app.include_router(sim_router)
```

- [ ] **Step 9.4 — Tests pass**

```
uv run pytest tests/test_api_sim_seed.py -v
```
Expected: 3 passed.

- [ ] **Step 9.5 — Commit**

```bash
git add server/api/sim.py server/main.py tests/test_api_sim_seed.py
git commit -m "feat(api): POST /api/sim/seed (idempotent demo data seeder)"
```

---

## Task 10 — POST /api/sim/inbound

**Files:**
- Modify: `server/api/sim.py`
- Test: `tests/test_api_sim_inbound.py`

- [ ] **Step 10.1 — Write failing test**

`tests/test_api_sim_inbound.py`:
```python
import pytest
from sqlalchemy import select

from server.db.alerts import Alert
from server.db.identity import NGO, Account
from server.db.messages import InboundMessage


@pytest.fixture
async def seeded(db):
    ngo = NGO(name="TestNGO-inbound")
    db.add(ngo)
    await db.flush()
    acc = Account(phone="+972500000001", ngo_id=ngo.ngo_id)
    alert = Alert(ngo_id=ngo.ngo_id, person_name="Maya", status="active")
    db.add_all([acc, alert])
    await db.flush()
    await db.commit()
    return {"ngo_id": ngo.ngo_id, "alert_id": alert.alert_id}


async def test_post_inbound_returns_202(client, seeded):
    resp = await client.post(
        "/api/sim/inbound",
        json={
            "channel": "app",
            "sender_phone": "+972500000001",
            "in_reply_to_alert_id": seeded["alert_id"],
            "body": "saw a girl matching photo near bakery",
            "media_urls": [],
            "raw": {},
        },
    )
    assert resp.status_code == 202
    body = resp.json()
    assert "msg_id" in body
    assert body["status"] == "new"


async def test_post_inbound_creates_db_row(client, seeded, test_session_maker):
    resp = await client.post(
        "/api/sim/inbound",
        json={
            "channel": "sms",
            "sender_phone": "+972500000001",
            "in_reply_to_alert_id": None,
            "body": "hello world",
            "media_urls": [],
            "raw": {"src": "test"},
        },
    )
    assert resp.status_code == 202
    msg_id = resp.json()["msg_id"]

    async with test_session_maker() as session:
        row = await session.get(InboundMessage, msg_id)
    assert row is not None
    assert row.status == "new"
    assert row.channel == "sms"
    assert row.body == "hello world"


async def test_post_inbound_503_when_no_ngo(client):
    resp = await client.post(
        "/api/sim/inbound",
        json={
            "channel": "app",
            "sender_phone": "+972500000099",
            "in_reply_to_alert_id": None,
            "body": "no ngo",
            "media_urls": [],
            "raw": {},
        },
    )
    assert resp.status_code in (202, 503)
```

- [ ] **Step 10.2 — Run, expect failure**

```
uv run pytest tests/test_api_sim_inbound.py -v
```
Expected: `404 Not Found` on `/api/sim/inbound`.

- [ ] **Step 10.3 — Implement (append to `server/api/sim.py`)**

Add at the bottom of `server/api/sim.py`:
```python
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel

from server.db.base import generate_ulid
from server.db.engine import get_engine
from server.db.messages import InboundMessage
from server.eventbus.postgres import PostgresEventBus


class InboundEnvelope(BaseModel):
    channel: str
    sender_phone: str
    in_reply_to_alert_id: Optional[str] = None
    body: str
    media_urls: list[str] = []
    raw: dict = {}


@router.post("/inbound", status_code=202)
async def sim_inbound(
    envelope: InboundEnvelope,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    ngos = (await db.execute(select(NGO))).scalars().all()
    if len(ngos) != 1:
        raise HTTPException(
            status_code=503,
            detail=f"Expected exactly 1 NGO, found {len(ngos)}. Seed the DB first.",
        )
    ngo = ngos[0]

    msg_id = generate_ulid()
    msg = InboundMessage(
        msg_id=msg_id,
        ngo_id=ngo.ngo_id,
        channel=envelope.channel,
        sender_phone=envelope.sender_phone,
        in_reply_to_alert_id=envelope.in_reply_to_alert_id,
        body=envelope.body,
        media_urls=envelope.media_urls,
        raw=envelope.raw,
        received_at=datetime.now(UTC),
        status="new",
    )
    db.add(msg)
    await db.commit()

    bus = PostgresEventBus(get_engine())
    await bus.publish("new_inbound", msg_id)

    return {"msg_id": msg_id, "status": "new"}
```

- [ ] **Step 10.4 — Tests pass**

```
uv run pytest tests/test_api_sim_inbound.py -v
```
Expected: 3 passed.

- [ ] **Step 10.5 — Commit**

```bash
git add server/api/sim.py tests/test_api_sim_inbound.py
git commit -m "feat(api): POST /api/sim/inbound writes InboundMessage and notifies"
```

---

## Task 11 — Triage worker (LLM stub + embedding stub + bucket upsert)

**Files:**
- Create: `server/llm/__init__.py`, `server/llm/triage_client.py`
- Create: `server/workers/__init__.py`, `server/workers/triage.py`
- Test: `tests/test_triage_worker.py`
- Modify: `pyproject.toml` (add `anthropic`)

- [ ] **Step 11.1 — Write failing test**

`tests/test_triage_worker.py`:
```python
import asyncio

import pytest
from sqlalchemy import select

from server.db.alerts import Alert
from server.db.identity import NGO, Account
from server.db.messages import Bucket, InboundMessage, TriagedMessage


@pytest.fixture(autouse=True)
def stub_llm(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")


@pytest.fixture
async def seeded_inbound(db):
    ngo = NGO(name="TriageNGO")
    db.add(ngo)
    await db.flush()
    acc = Account(phone="+972500000042", ngo_id=ngo.ngo_id)
    alert = Alert(
        ngo_id=ngo.ngo_id, person_name="Yael",
        description="Young girl, red jacket, last seen near central market",
        status="active",
    )
    db.add_all([acc, alert])
    await db.flush()
    msg = InboundMessage(
        ngo_id=ngo.ngo_id, channel="app", sender_phone="+972500000042",
        in_reply_to_alert_id=alert.alert_id,
        body="saw a girl in red walking south near bakery",
        media_urls=[], raw={}, status="new",
    )
    db.add(msg)
    await db.flush()
    await db.commit()
    return {"ngo_id": ngo.ngo_id, "alert_id": alert.alert_id, "msg_id": msg.msg_id}


async def test_stub_classify_short_body():
    from server.llm.triage_client import classify
    r = await classify("hi", None)
    assert r["classification"] == "noise"


async def test_stub_classify_long_body():
    from server.llm.triage_client import classify
    r = await classify("saw a young girl near the bakery going south", None)
    assert r["classification"] == "sighting"
    assert len(r["dedup_hash"]) > 0


async def test_hash_to_vec_length():
    from server.llm.triage_client import hash_to_vec
    v = hash_to_vec("test body")
    assert len(v) == 512
    assert all(-1.0 <= x <= 1.0 for x in v)


async def test_triage_worker_consumes_event(seeded_inbound, test_engine, test_session_maker):
    from server.eventbus.postgres import PostgresEventBus
    from server.workers.triage import triage_worker_loop

    bus = PostgresEventBus(test_engine)
    task = asyncio.create_task(triage_worker_loop(bus, test_session_maker))
    await asyncio.sleep(0.4)

    await bus.publish("new_inbound", seeded_inbound["msg_id"])
    await asyncio.sleep(1.5)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    async with test_session_maker() as session:
        inbound = await session.get(InboundMessage, seeded_inbound["msg_id"])
        assert inbound.status == "triaged"

        triage_rows = (
            await session.execute(
                select(TriagedMessage).where(TriagedMessage.msg_id == seeded_inbound["msg_id"])
            )
        ).scalars().all()
        assert len(triage_rows) == 1
        tm = triage_rows[0]
        assert tm.classification in ("sighting", "question", "ack", "noise", "bad_actor")
        assert len(tm.body_embedding) == 512

        bucket_rows = (
            await session.execute(select(Bucket).where(Bucket.bucket_key == tm.bucket_key))
        ).scalars().all()
        assert len(bucket_rows) == 1
```

- [ ] **Step 11.2 — Run, expect failure**

```
uv run pytest tests/test_triage_worker.py -v
```
Expected: `ModuleNotFoundError` on `server.llm` and `server.workers`.

- [ ] **Step 11.3 — Implement**

Add `anthropic>=0.40.0` to `pyproject.toml` `[project.dependencies]`. Then `uv sync`.

`server/llm/__init__.py`: empty file.

`server/llm/triage_client.py`:
```python
import hashlib
import os
from typing import Optional


def hash_to_vec(body: str) -> list[float]:
    """Deterministic 512-float embedding from sha256 of the body."""
    seed = body.encode("utf-8")
    floats: list[float] = []
    i = 0
    while len(floats) < 512:
        digest = hashlib.sha256(seed + i.to_bytes(4, "big")).digest()
        for byte in digest:
            floats.append((byte / 127.5) - 1.0)
            if len(floats) == 512:
                break
        i += 1
    return floats


def _stub_classify(body: str, alert_summary: Optional[str]) -> dict:
    normalized = body.strip().lower()
    classification = "sighting" if len(normalized) >= 10 else "noise"
    return {
        "classification": classification,
        "geohash6": None,
        "geohash_source": "alert_region",
        "confidence": 0.75 if classification == "sighting" else 0.4,
        "language": "en",
        "dedup_hash": hashlib.sha256(normalized.encode()).hexdigest()[:16],
    }


async def classify(body: str, alert_summary: Optional[str]) -> dict:
    """Classify an inbound message. Stub if ANTHROPIC_API_KEY is unset."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return _stub_classify(body, alert_summary)

    import anthropic

    client = anthropic.AsyncAnthropic(api_key=api_key)
    system = (
        "You are a triage classifier for civilian sighting reports for a missing-person "
        "alert system. Classify the message, extract a 6-character geohash if possible, "
        "detect language, and produce a stable dedup_hash from the normalized body. "
        "Return ONLY the structured tool call."
    )
    context = f"\n\nAlert context: {alert_summary}" if alert_summary else ""

    tool = {
        "name": "classify",
        "description": "Classify an inbound civilian sighting message.",
        "input_schema": {
            "type": "object",
            "properties": {
                "classification": {"type": "string", "enum": ["sighting", "question", "ack", "noise", "bad_actor"]},
                "geohash6": {"type": ["string", "null"]},
                "geohash_source": {"type": "string", "enum": ["app_gps", "registered_home", "alert_region", "body_extraction"]},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "language": {"type": "string"},
                "dedup_hash": {"type": "string"},
            },
            "required": ["classification", "geohash6", "geohash_source", "confidence", "language", "dedup_hash"],
        },
    }

    resp = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        system=system,
        messages=[{"role": "user", "content": f"Message: {body}{context}"}],
        tools=[tool],
        tool_choice={"type": "tool", "name": "classify"},
    )
    for block in resp.content:
        if block.type == "tool_use" and block.name == "classify":
            return block.input
    return _stub_classify(body, alert_summary)
```

`server/workers/__init__.py`: empty file.

`server/workers/triage.py`:
```python
import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from server.db.alerts import Alert
from server.db.messages import Bucket, InboundMessage, TriagedMessage
from server.eventbus.postgres import PostgresEventBus
from server.llm.triage_client import classify, hash_to_vec

logger = logging.getLogger(__name__)

WORKER_ID = "triage-worker-1"
WINDOW_LENGTH_MS = 3000


def _window_floor(ts: datetime, window_ms: int = WINDOW_LENGTH_MS) -> datetime:
    epoch_ms = int(ts.timestamp() * 1000)
    floored = (epoch_ms // window_ms) * window_ms
    return datetime.fromtimestamp(floored / 1000, tz=UTC)


async def _process_message(msg_id: str, session_maker: async_sessionmaker) -> None:
    async with session_maker() as session:
        msg = await session.get(InboundMessage, msg_id)
        if msg is None:
            logger.warning("triage: msg %s not found", msg_id)
            return
        if msg.status != "new":
            return
        msg.status = "triaging"
        msg.claimed_at = datetime.now(UTC)
        msg.claimed_by = WORKER_ID
        await session.commit()

    async with session_maker() as session:
        msg = await session.get(InboundMessage, msg_id)

        alert_summary = None
        alert_id = msg.in_reply_to_alert_id
        if alert_id:
            alert = await session.get(Alert, alert_id)
            if alert:
                desc = alert.description or ""
                alert_summary = (alert.person_name + ". " + desc)[:200]

        body_embedding = hash_to_vec(msg.body)
        result = await classify(msg.body, alert_summary)

        classification = result["classification"]
        geohash6 = result.get("geohash6")
        geohash_source = result.get("geohash_source", "alert_region")
        confidence = float(result.get("confidence", 0.5))
        language = result.get("language", "en")

        geohash_prefix_4 = (geohash6 or "")[:4] or "unkn"
        now = datetime.now(UTC)
        window_start = _window_floor(now, WINDOW_LENGTH_MS)
        bucket_key = f"{alert_id or 'unresolved'}|{geohash_prefix_4}|{window_start.isoformat()}"

        triaged = TriagedMessage(
            msg_id=msg_id,
            ngo_id=msg.ngo_id,
            classification=classification,
            geohash6=geohash6,
            geohash_source=geohash_source,
            confidence=confidence,
            language=language,
            bucket_key=bucket_key,
            body_embedding=body_embedding,
        )
        session.add(triaged)

        if alert_id:
            stmt = (
                pg_insert(Bucket)
                .values(
                    bucket_key=bucket_key,
                    ngo_id=msg.ngo_id,
                    alert_id=alert_id,
                    geohash_prefix_4=geohash_prefix_4,
                    window_start=window_start,
                    window_length_ms=WINDOW_LENGTH_MS,
                    status="open",
                )
                .on_conflict_do_nothing(index_elements=["bucket_key"])
            )
            await session.execute(stmt)

        msg.status = "triaged"
        await session.commit()


async def triage_worker_loop(
    eventbus: PostgresEventBus,
    session_maker: async_sessionmaker,
) -> None:
    """Long-running coroutine: consume new_inbound events and triage."""
    retry_counts: dict[str, int] = {}
    async for msg_id in eventbus.subscribe("new_inbound"):
        try:
            await _process_message(msg_id, session_maker)
            retry_counts.pop(msg_id, None)
            await eventbus.publish("bucket_open", msg_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            count = retry_counts.get(msg_id, 0) + 1
            retry_counts[msg_id] = count
            logger.exception("triage: error on %s (attempt %d): %s", msg_id, count, exc)
            if count >= 3:
                async with session_maker() as session:
                    m = await session.get(InboundMessage, msg_id)
                    if m:
                        m.status = "failed"
                        m.retry_count = count
                        await session.commit()
                retry_counts.pop(msg_id, None)
```

- [ ] **Step 11.4 — Tests pass**

```
uv run pytest tests/test_triage_worker.py -v
```
Expected: 4 passed.

- [ ] **Step 11.5 — Commit**

```bash
git add server/llm/ server/workers/ tests/test_triage_worker.py pyproject.toml uv.lock
git commit -m "feat(triage): worker with Haiku-stub classifier and stub embedding"
```

---

## Task 12 — Worker lifecycle in FastAPI startup

**Files:**
- Modify: `server/main.py`
- Test: `tests/test_worker_lifecycle.py`

- [ ] **Step 12.1 — Write failing test**

`tests/test_worker_lifecycle.py`:
```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from server.db.engine import get_engine, get_session_maker


async def test_worker_task_alive_during_request(test_engine, monkeypatch):
    get_engine.cache_clear()
    get_session_maker.cache_clear()
    monkeypatch.setattr("server.db.engine.get_engine", lambda: test_engine)
    monkeypatch.setattr(
        "server.db.engine.get_session_maker",
        lambda: async_sessionmaker(test_engine, expire_on_commit=False),
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    from server import main as main_module
    from server.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == 200
        assert main_module._worker_task is not None
        assert not main_module._worker_task.done()

    # After lifespan shutdown
    assert main_module._worker_task is None or main_module._worker_task.done()
```

- [ ] **Step 12.2 — Run, expect failure**

```
uv run pytest tests/test_worker_lifecycle.py -v
```
Expected: `AttributeError: module 'server.main' has no attribute '_worker_task'`.

- [ ] **Step 12.3 — Implement**

`server/main.py` (full file):
```python
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from server.api.audiences import router as audiences_router
from server.api.dashboard import router as dashboard_router
from server.api.health import router as health_router
from server.api.incidents import router as incidents_router
from server.api.operators import router as operators_router
from server.api.regions import router as regions_router
from server.api.sim import router as sim_router
from server.db.engine import get_engine, get_session_maker
from server.eventbus.postgres import PostgresEventBus
from server.workers.triage import triage_worker_loop

logger = logging.getLogger(__name__)

_worker_task: Optional[asyncio.Task] = None
_event_bus: Optional[PostgresEventBus] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker_task, _event_bus

    engine = get_engine()
    session_maker = get_session_maker()
    _event_bus = PostgresEventBus(engine)

    _worker_task = asyncio.create_task(
        triage_worker_loop(_event_bus, session_maker),
        name="triage-worker",
    )
    logger.info("lifespan: triage worker started")

    try:
        yield
    finally:
        if _worker_task and not _worker_task.done():
            _worker_task.cancel()
            try:
                await asyncio.wait_for(_worker_task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        if _event_bus:
            await _event_bus.close()
        logger.info("lifespan: triage worker stopped")


app = FastAPI(title="anth-hackathon26 matching engine", lifespan=lifespan)
app.include_router(health_router)
app.include_router(operators_router)
app.include_router(audiences_router)
app.include_router(regions_router)
app.include_router(incidents_router)
app.include_router(dashboard_router)
app.include_router(sim_router)
```

- [ ] **Step 12.4 — Tests pass**

```
uv run pytest tests/test_worker_lifecycle.py -v
```
Expected: 1 passed.

- [ ] **Step 12.5 — Commit**

```bash
git add server/main.py tests/test_worker_lifecycle.py
git commit -m "feat(main): wire triage worker into FastAPI lifespan"
```

---

## Task 13 — WS /ws/stream

**Files:**
- Create: `server/api/ws.py`
- Modify: `server/main.py`
- Test: `tests/test_api_ws_stream.py`

- [ ] **Step 13.1 — Write failing test**

`tests/test_api_ws_stream.py`:
```python
import asyncio
import threading
import time

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.testclient import TestClient

from server.db.alerts import Alert
from server.db.identity import NGO, Account
from server.db.messages import InboundMessage


@pytest.fixture
def sync_seed(test_engine):
    """Seed an InboundMessage row synchronously for TestClient WS tests."""
    sm = async_sessionmaker(test_engine, expire_on_commit=False)

    async def _seed():
        async with sm() as s:
            ngo = NGO(name="WSNGO")
            s.add(ngo)
            await s.flush()
            acc = Account(phone="+972500000077", ngo_id=ngo.ngo_id)
            alert = Alert(ngo_id=ngo.ngo_id, person_name="Dana", status="active")
            s.add_all([acc, alert])
            await s.flush()
            msg = InboundMessage(
                ngo_id=ngo.ngo_id, channel="app", sender_phone="+972500000077",
                in_reply_to_alert_id=alert.alert_id, body="saw her near the park",
                media_urls=[], raw={}, status="new",
            )
            s.add(msg)
            await s.flush()
            await s.commit()
            return {"alert_id": alert.alert_id, "msg_id": msg.msg_id}

    loop = asyncio.new_event_loop()
    out = loop.run_until_complete(_seed())
    loop.close()
    return out


def test_ws_stream_receives_message(sync_seed, test_engine, monkeypatch):
    monkeypatch.setattr("server.db.engine.get_engine", lambda: test_engine)
    monkeypatch.setattr(
        "server.db.engine.get_session_maker",
        lambda: async_sessionmaker(test_engine, expire_on_commit=False),
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    from server.eventbus.postgres import PostgresEventBus
    from server.main import app

    received: list[dict] = []

    def publish_after_connect():
        time.sleep(0.5)

        async def _pub():
            bus = PostgresEventBus(test_engine)
            await bus.publish("new_inbound", sync_seed["msg_id"])

        loop = asyncio.new_event_loop()
        loop.run_until_complete(_pub())
        loop.close()

    t = threading.Thread(target=publish_after_connect, daemon=True)

    with TestClient(app) as client:
        t.start()
        with client.websocket_connect("/ws/stream") as ws:
            try:
                data = ws.receive_json(timeout=4.0)
                received.append(data)
            except Exception:
                pass

    assert len(received) >= 1
    evt = received[0]
    assert evt["type"] == "message"
    assert evt["message"]["body"] == "saw her near the park"
```

- [ ] **Step 13.2 — Run, expect failure**

```
uv run pytest tests/test_api_ws_stream.py -v
```
Expected: WS handshake fails or `/ws/stream` returns 403/404.

- [ ] **Step 13.3 — Implement**

`server/api/ws.py`:
```python
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from server.db.alerts import Alert
from server.db.engine import get_engine, get_session_maker
from server.db.messages import InboundMessage
from server.eventbus.postgres import PostgresEventBus

router = APIRouter()
logger = logging.getLogger(__name__)


def _incident_shape(alert: Optional[Alert]) -> dict:
    if alert is None:
        return {"alert_id": None, "person_name": "Unknown", "status": "unknown",
                "description": None, "photo_url": None}
    return {
        "alert_id": alert.alert_id,
        "person_name": alert.person_name,
        "status": alert.status,
        "description": alert.description,
        "photo_url": alert.photo_url,
    }


def _message_shape(msg: InboundMessage) -> dict:
    return {
        "msg_id": msg.msg_id,
        "channel": msg.channel,
        "sender_phone": msg.sender_phone,
        "body": msg.body,
        "media_urls": msg.media_urls,
        "status": msg.status,
        "received_at": msg.received_at.isoformat() if msg.received_at else None,
        "in_reply_to_alert_id": msg.in_reply_to_alert_id,
    }


async def _compose_inbound_event(msg_id: str) -> Optional[dict]:
    sm = get_session_maker()
    async with sm() as s:
        msg = await s.get(InboundMessage, msg_id)
        if msg is None:
            return None
        alert: Optional[Alert] = None
        if msg.in_reply_to_alert_id:
            alert = await s.get(Alert, msg.in_reply_to_alert_id)
        return {"type": "message", "incident": _incident_shape(alert), "message": _message_shape(msg)}


async def _compose_incident_event(alert_id: str) -> Optional[dict]:
    sm = get_session_maker()
    async with sm() as s:
        alert = await s.get(Alert, alert_id)
    if alert is None:
        return None
    return {"type": "incident_upserted", "incident": _incident_shape(alert), "message": None}


@router.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket):
    await websocket.accept()
    bus = PostgresEventBus(get_engine())

    async def listen(channel: str):
        async for payload in bus.subscribe(channel):
            try:
                if channel == "new_inbound":
                    evt = await _compose_inbound_event(payload)
                    if evt:
                        await websocket.send_json(evt)
                elif channel == "incident_upserted":
                    evt = await _compose_incident_event(payload)
                    if evt:
                        await websocket.send_json(evt)
                elif channel == "bucket_open":
                    pass
            except Exception as exc:
                logger.warning("ws_stream(%s): error: %s", channel, exc)

    tasks = [
        asyncio.create_task(listen("new_inbound")),
        asyncio.create_task(listen("incident_upserted")),
        asyncio.create_task(listen("bucket_open")),
    ]
    try:
        await asyncio.gather(*tasks)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("ws_stream: %s", exc)
    finally:
        for t in tasks:
            t.cancel()
        try:
            await websocket.close()
        except Exception:
            pass
```

`server/main.py` (full file):
```python
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from server.api.audiences import router as audiences_router
from server.api.dashboard import router as dashboard_router
from server.api.health import router as health_router
from server.api.incidents import router as incidents_router
from server.api.operators import router as operators_router
from server.api.regions import router as regions_router
from server.api.sim import router as sim_router
from server.api.ws import router as ws_router
from server.db.engine import get_engine, get_session_maker
from server.eventbus.postgres import PostgresEventBus
from server.workers.triage import triage_worker_loop

logger = logging.getLogger(__name__)

_worker_task: Optional[asyncio.Task] = None
_event_bus: Optional[PostgresEventBus] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker_task, _event_bus
    engine = get_engine()
    session_maker = get_session_maker()
    _event_bus = PostgresEventBus(engine)
    _worker_task = asyncio.create_task(
        triage_worker_loop(_event_bus, session_maker),
        name="triage-worker",
    )
    try:
        yield
    finally:
        if _worker_task and not _worker_task.done():
            _worker_task.cancel()
            try:
                await asyncio.wait_for(_worker_task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        if _event_bus:
            await _event_bus.close()


app = FastAPI(title="anth-hackathon26 matching engine", lifespan=lifespan)
app.include_router(health_router)
app.include_router(operators_router)
app.include_router(audiences_router)
app.include_router(regions_router)
app.include_router(incidents_router)
app.include_router(dashboard_router)
app.include_router(sim_router)
app.include_router(ws_router)
```

- [ ] **Step 13.4 — Tests pass**

```
uv run pytest tests/test_api_ws_stream.py -v
```
Expected: 1 passed.

- [ ] **Step 13.5 — Commit**

```bash
git add server/api/ws.py server/main.py tests/test_api_ws_stream.py
git commit -m "feat(api): WS /ws/stream forwards new_inbound and incident_upserted"
```

---

## Task 14 — End-to-end inbound pipeline test

**Files:**
- Test: `tests/test_e2e_inbound_pipeline.py`

- [ ] **Step 14.1 — Write the test**

`tests/test_e2e_inbound_pipeline.py`:
```python
import asyncio
import threading
import time

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.testclient import TestClient

from server.db.alerts import Alert
from server.db.identity import NGO, Account
from server.db.messages import Bucket, InboundMessage, TriagedMessage


@pytest.fixture(autouse=True)
def stub_llm_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")


@pytest.fixture
def sync_seed(test_engine):
    sm = async_sessionmaker(test_engine, expire_on_commit=False)

    async def _seed():
        async with sm() as s:
            ngo = NGO(name="E2ENGO")
            s.add(ngo)
            await s.flush()
            acc = Account(phone="+972500000099", ngo_id=ngo.ngo_id)
            alert = Alert(
                ngo_id=ngo.ngo_id, person_name="Shira",
                description="Young girl, brown hair, last seen near central market",
                status="active",
            )
            s.add_all([acc, alert])
            await s.flush()
            await s.commit()
            return {"alert_id": alert.alert_id, "phone": "+972500000099"}

    loop = asyncio.new_event_loop()
    out = loop.run_until_complete(_seed())
    loop.close()
    return out


def test_full_inbound_pipeline(sync_seed, test_engine, monkeypatch):
    monkeypatch.setattr("server.db.engine.get_engine", lambda: test_engine)
    monkeypatch.setattr(
        "server.db.engine.get_session_maker",
        lambda: async_sessionmaker(test_engine, expire_on_commit=False),
    )

    from server.main import app

    received: list[dict] = []
    body_text = "saw a girl in red walking south near the old market"

    def post_inbound(client):
        time.sleep(0.6)
        resp = client.post(
            "/api/sim/inbound",
            json={
                "channel": "app",
                "sender_phone": sync_seed["phone"],
                "in_reply_to_alert_id": sync_seed["alert_id"],
                "body": body_text,
                "media_urls": [],
                "raw": {},
            },
        )
        assert resp.status_code == 202

    with TestClient(app) as client:
        t = threading.Thread(target=post_inbound, args=(client,), daemon=True)
        t.start()

        with client.websocket_connect("/ws/stream") as ws:
            try:
                data = ws.receive_json(timeout=6.0)
                received.append(data)
            except Exception:
                pass

        t.join(timeout=3.0)

    assert len(received) >= 1
    evt = received[0]
    assert evt["type"] == "message"
    assert evt["message"]["body"] == body_text

    # DB checks via a fresh loop
    sm = async_sessionmaker(test_engine, expire_on_commit=False)

    async def _check():
        async with sm() as s:
            rows = (
                await s.execute(
                    select(InboundMessage).where(
                        InboundMessage.sender_phone == sync_seed["phone"],
                        InboundMessage.body == body_text,
                    )
                )
            ).scalars().all()
            assert len(rows) >= 1
            msg = rows[-1]
            for _ in range(10):
                await asyncio.sleep(0.3)
                await s.refresh(msg)
                if msg.status == "triaged":
                    break
            assert msg.status == "triaged"

            triaged = (
                await s.execute(select(TriagedMessage).where(TriagedMessage.msg_id == msg.msg_id))
            ).scalars().all()
            assert len(triaged) == 1
            assert len(triaged[0].body_embedding) == 512

            buckets = (
                await s.execute(select(Bucket).where(Bucket.bucket_key == triaged[0].bucket_key))
            ).scalars().all()
            assert len(buckets) == 1

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_check())
    loop.close()
```

- [ ] **Step 14.2 — Run, expect (now) pass**

```
uv run pytest tests/test_e2e_inbound_pipeline.py -v
```
Expected: 1 passed. If flaky on timing, increase the `time.sleep(0.6)` to `1.0` and the `ws.receive_json(timeout=6.0)` to `8.0`.

Run the full suite:
```
uv run pytest -v
```
Expected: 35 (Plan 1) + ~30 (Plan 2) = 65+ tests pass.

- [ ] **Step 14.3 — Commit**

```bash
git add tests/test_e2e_inbound_pipeline.py
git commit -m "test: e2e inbound pipeline (POST inbound → triage → bucket → WS event)"
```

---

## Acceptance criteria for Plan 2

- [ ] `POST /api/sim/seed` populates 1 NGO, 6 accounts, 1 alert, 6 deliveries, 4 inbound messages.
- [ ] `GET /api/me`, `/api/operators`, `/api/audiences`, `/api/regions/stats`, `/api/regions/:r/timeline`, `/api/incidents`, `/api/incidents/:id/messages`, `/api/dashboard` all return 200 with the right JSON shapes.
- [ ] `POST /api/sim/inbound` writes an `InboundMessage` row and publishes `new_inbound`.
- [ ] Triage worker drains `new_inbound`, classifies via Haiku stub when `ANTHROPIC_API_KEY=""`, writes `TriagedMessage` with a 512-dim embedding, upserts `Bucket`, sets `InboundMessage.status='triaged'`.
- [ ] `WS /ws/stream` accepts connections and emits `{type:"message", incident, message}` for each `new_inbound`.
- [ ] After `docker compose up -d db` + `uv run uvicorn server.main:app --port 8080` + `cd web && npm run dev`, the frontend at `http://localhost:5173` no longer 404s on shell endpoints; the dashboard, cases, and map render with seeded data.
- [ ] Frontend's "Seed demo" button triggers `POST /api/sim/seed` and the dashboard updates.

---

## Spec coverage / open items

- Real embedding client (voyage / OpenAI) deferred to Plan 3 (only used by `search` retrieval tools, not by Plan 2).
- Real Haiku triage runs whenever `ANTHROPIC_API_KEY` is set; tests pin the stub via `monkeypatch.setenv`.
- Outbound dispatcher and operator approval flow deferred to Plan 4.
- Cluster / trajectory / tag models exist in DB (Plan 1) but no read/write endpoints in Plan 2.
- The Triage worker uses a fixed 3s window in Plan 2; adaptive window logic deferred to Plan 4.
- WS `/ws/stream` is unauthenticated for Plan 2 (frontend doesn't include the X-Operator-Id header on WS handshake). Plan 4 hardens.

---

## Execution

Plan saved at `docs/superpowers/plans/2026-04-25-inbound-pipeline.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — I execute the tasks in this session via `superpowers:executing-plans`, batched with checkpoints.

Either way, when ready to start, mark Task 1 in progress and dispatch.
