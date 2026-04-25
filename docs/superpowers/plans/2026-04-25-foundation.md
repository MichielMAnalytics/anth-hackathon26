# Plan 1 — Foundation & Schema

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the matching engine's foundation — Postgres + pgvector via docker-compose, FastAPI skeleton, all 16 SQLAlchemy models with alembic migrations, the EventBus and SmsProvider abstractions with their first concrete implementations, and basic NGO operator JWT auth — so subsequent plans can implement the inbound pipeline, agent worker, dispatcher, and console without revisiting infrastructure.

**Architecture:** Two-container hackathon shape (`app` + `db`) per the spec. All workers later collapse into asyncio tasks inside the `app` FastAPI process. DB is the only stateful node; tables-as-queues pattern. EventBus and SmsProvider are Protocol-shaped at the type level; this plan ships one implementation of each (Postgres `LISTEN/NOTIFY` and `SimSmsProvider`) — both default and the only ones used by the demo.

**Tech Stack:**
- Python 3.12+, FastAPI 0.110+, uvicorn
- SQLAlchemy 2.0 async + asyncpg
- alembic for migrations
- pgvector (`pgvector/pgvector:pg16` Docker image, `pgvector` Python package)
- pydantic-settings for config, python-ulid for PKs
- python-jose + passlib for JWT auth
- pytest + pytest-asyncio + httpx for tests
- `uv` for package management
- `pgvector/pgvector:pg16` Docker image

---

## File structure (locked-in decomposition)

```
anth-hackathon26/
├── docker-compose.yml             # 2 services: app (later), db
├── pyproject.toml                 # all deps, pytest config, ruff config
├── alembic.ini                    # alembic config
├── .env.example                   # documented env vars
├── db/
│   └── init.sql                   # creates pgvector ext + matching_test DB
├── server/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entry
│   ├── config.py                  # Settings (pydantic-settings)
│   ├── db/
│   │   ├── __init__.py
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
│   │   ├── __init__.py
│   │   ├── base.py                # EventBus Protocol
│   │   └── postgres.py            # PostgresEventBus (LISTEN/NOTIFY)
│   ├── transports/
│   │   ├── __init__.py
│   │   ├── sms_base.py            # SmsProvider Protocol + SendResult
│   │   └── sim_sms.py             # SimSmsProvider in-process impl
│   ├── auth/
│   │   ├── __init__.py
│   │   └── ngo.py                 # JWT issue + verify, password hash
│   └── api/
│       ├── __init__.py
│       └── health.py              # GET /health
├── alembic/
│   ├── env.py                     # async-aware migration env
│   ├── script.py.mako
│   └── versions/                  # one file per task (migrations)
└── tests/
    ├── __init__.py
    ├── conftest.py                # db + client fixtures
    ├── test_smoke.py              # boot + import smoke
    ├── test_db_engine.py
    ├── test_health.py
    ├── test_models_identity.py
    ├── test_models_alerts.py
    ├── test_models_messages.py
    ├── test_models_decisions.py
    ├── test_models_outbound.py
    ├── test_models_knowledge.py
    ├── test_models_trust.py
    ├── test_indices.py
    ├── test_eventbus_postgres.py
    ├── test_sim_sms.py
    ├── test_auth_ngo.py
    └── test_e2e_foundation.py     # full stack smoke
```

Files that change together live together: each domain (`identity`, `alerts`, `messages`, …) has its own SQLAlchemy file and its own test file. `EventBus` and `SmsProvider` are Protocol-based with one implementation each.

---

## Task 0 — Tidy the existing scaffold

The repo already has a junior-dev "NGO Hub" demo: `server/` holds an in-memory FastAPI app (`main.py`, `audiences.py`, `dashboard.py`, `operators.py`, `schemas.py`, `seed.py`, `store.py`) and `pyproject.toml` is named `ngo-hub` with only `fastapi + uvicorn + pydantic`. The frontend in `web/` is good and stays as-is. We delete the dummy backend modules now so Task 1 starts from a clean slate, but we keep `server/__init__.py` so Task 1 can write into it.

**Files:**
- Delete: `server/main.py`, `server/audiences.py`, `server/dashboard.py`, `server/operators.py`, `server/schemas.py`, `server/seed.py`, `server/store.py`
- Keep: `server/__init__.py` (will be overwritten in Task 1.3), `web/`, `Dockerfile` (revisited in Task 17 if needed), `docker-compose.yml` (replaced in Task 2)

- [ ] **Step 0.1 — Verify expected files exist**

Run: `ls server/ web/src/lib/api.ts pyproject.toml docker-compose.yml`
Expected: all listed; the dummy server modules are present.

- [ ] **Step 0.2 — Delete dummy backend modules**

```bash
rm server/main.py server/audiences.py server/dashboard.py server/operators.py server/schemas.py server/seed.py server/store.py
```

- [ ] **Step 0.3 — Replace `server/__init__.py` with a minimal placeholder**

`server/__init__.py`:
```python
__version__ = "0.1.0"
```

- [ ] **Step 0.4 — Verify the working tree is clean of dummy code**

Run: `ls server/`
Expected: only `__init__.py`.

- [ ] **Step 0.5 — Commit the cleanup**

```bash
git add server/
git commit -m "chore: remove NGO Hub dummy backend; matching-engine rebuild starts here"
```

The frontend in `web/` is intentionally left intact. Plan 1 only stands up `/health`; the frontend will be broken-but-loadable until Plans 2–5 wire real endpoints to satisfy `web/src/lib/api.ts`.

---

## Task 1 — Project scaffold

**Files:**
- Replace: `pyproject.toml` (currently `ngo-hub` with minimal deps; we expand it)
- Already created in Task 0: `server/__init__.py`
- Create: `tests/__init__.py`, `tests/test_smoke.py`, `.env.example`
- Modify: `.gitignore` (already exists; ensure `.venv/`, `.env`, `__pycache__/` are present)

- [ ] **Step 1.1 — Write the failing smoke test**

`tests/test_smoke.py`:
```python
def test_server_module_importable():
    import server
    assert server is not None
```

- [ ] **Step 1.2 — Run it, expect failure**

Run: `uv run pytest tests/test_smoke.py -v`
Expected: `ModuleNotFoundError: No module named 'server'` (or pytest import error)

- [ ] **Step 1.3 — Replace project files**

Overwrite `pyproject.toml` (the existing `ngo-hub` content is replaced wholesale):
```toml
[project]
name = "matching-engine"
version = "0.1.0"
description = "P2P amber alert matching engine"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "sqlalchemy[asyncio]>=2.0.27",
    "asyncpg>=0.29",
    "alembic>=1.13",
    "pgvector>=0.2.5",
    "pydantic>=2.6",
    "pydantic-settings>=2.2",
    "python-ulid>=2.4",
    "python-jose[cryptography]>=3.3",
    "passlib[bcrypt]>=1.7.4",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.26",
    "ruff>=0.3",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
target-version = "py312"
line-length = 100
```

`server/__init__.py` already created in Task 0; nothing to do here.

`tests/__init__.py`:
```python
```

`.env.example`:
```bash
DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/matching
TEST_DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/matching_test
JWT_SECRET=change-me-in-prod
ANTHROPIC_API_KEY=
LOG_LEVEL=INFO
```

Append to `.gitignore` (the file already exists; only add lines that aren't there yet):
```
__pycache__/
*.pyc
.pytest_cache/
.venv/
.env
*.egg-info/
dist/
build/
```
Run: `cat .gitignore` — verify all eight entries are present (deduplicate manually if any duplicate after append).

- [ ] **Step 1.4 — Install deps and run test, expect pass**

Run: `uv sync --all-extras && uv run pytest tests/test_smoke.py -v`
Expected: 1 passed

- [ ] **Step 1.5 — Commit**

```bash
git add pyproject.toml tests/__init__.py tests/test_smoke.py .env.example .gitignore
git commit -m "feat: project scaffold with FastAPI/SQLAlchemy/pgvector deps"
```

---

## Task 2 — Docker Compose with Postgres + pgvector

The existing `docker-compose.yml` has a single `ngo-hub` service. We replace it with two services: `db` (Postgres + pgvector) for now, and `app` (matching engine) which will be wired up over later plans. For Plan 1 the `app` service is defined but we mostly run uvicorn locally during development; `docker compose up -d db` is the hot path.

**Files:**
- Replace: `docker-compose.yml`
- Create: `db/init.sql`, `tests/test_db_engine.py`
- Create: `server/config.py`, `server/db/__init__.py`, `server/db/engine.py`

- [ ] **Step 2.1 — Write the failing test**

`tests/test_db_engine.py`:
```python
import pytest
from sqlalchemy import text

from server.db.engine import get_engine


async def test_engine_connects_and_pgvector_loaded():
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1

        # pgvector extension must be loaded
        ext = await conn.execute(
            text("SELECT extname FROM pg_extension WHERE extname='vector'")
        )
        assert ext.scalar() == "vector"
    await engine.dispose()
```

- [ ] **Step 2.2 — Run, expect failure (no DB, no engine module)**

Run: `uv run pytest tests/test_db_engine.py -v`
Expected: `ModuleNotFoundError` or connection refused.

- [ ] **Step 2.3 — Replace docker-compose.yml; create init.sql, config, engine**

Overwrite `docker-compose.yml` (the existing `ngo-hub` service is replaced):
```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    container_name: matching-db
    environment:
      POSTGRES_DB: matching
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
    ports: ["5432:5432"]
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "app", "-d", "matching"]
      interval: 5s
      timeout: 5s
      retries: 10

  app:
    build: .
    image: matching-engine:latest
    container_name: matching-app
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+asyncpg://app:app@db:5432/matching
      JWT_SECRET: change-me
    ports: ["8080:8080"]

volumes:
  pgdata:
```

The Dockerfile already exists from the NGO Hub scaffold (multi-stage: web build → python runtime). It will be revisited in Task 17 to install the new deps; for Plan 1 we run uvicorn locally rather than via the `app` container.

`db/init.sql`:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE DATABASE matching_test;
\c matching_test
CREATE EXTENSION IF NOT EXISTS vector;
```

`server/config.py`:
```python
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(
        default="postgresql+asyncpg://app:app@localhost:5432/matching",
        alias="DATABASE_URL",
    )
    test_database_url: str = Field(
        default="postgresql+asyncpg://app:app@localhost:5432/matching_test",
        alias="TEST_DATABASE_URL",
    )
    jwt_secret: str = Field(default="dev-secret", alias="JWT_SECRET")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

`server/db/__init__.py`:
```python
```

`server/db/engine.py`:
```python
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from server.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url, future=True)


@lru_cache
def get_session_maker() -> async_sessionmaker:
    return async_sessionmaker(get_engine(), expire_on_commit=False)
```

- [ ] **Step 2.4 — Bring up the DB**

Run: `docker compose up -d db`
Expected: container starts; `docker compose ps` shows `db` service `healthy` after ~10s.

- [ ] **Step 2.5 — Run test, expect pass**

Run: `uv run pytest tests/test_db_engine.py -v`
Expected: 1 passed

- [ ] **Step 2.6 — Commit**

```bash
git add docker-compose.yml db/init.sql server/config.py server/db/ tests/test_db_engine.py
git commit -m "feat: docker-compose Postgres+pgvector and async SQLAlchemy engine"
```

---

## Task 3 — FastAPI app + /health endpoint

**Files:**
- Create: `server/main.py`, `server/api/__init__.py`, `server/api/health.py`, `server/db/session.py`, `tests/test_health.py`

- [ ] **Step 3.1 — Write the failing test**

`tests/test_health.py`:
```python
from httpx import ASGITransport, AsyncClient

from server.main import app


async def test_health_returns_ok():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"status": "ok", "db": "ok"}
```

- [ ] **Step 3.2 — Run, expect failure**

Run: `uv run pytest tests/test_health.py -v`
Expected: ImportError on `server.main`.

- [ ] **Step 3.3 — Implement**

`server/db/session.py`:
```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from server.db.engine import get_session_maker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with get_session_maker()() as session:
        yield session
```

`server/api/__init__.py`:
```python
```

`server/api/health.py`:
```python
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from server.db.session import get_db

router = APIRouter()


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    db_ok = (await db.execute(text("SELECT 1"))).scalar() == 1
    return {"status": "ok", "db": "ok" if db_ok else "fail"}
```

`server/main.py`:
```python
from fastapi import FastAPI

from server.api.health import router as health_router

app = FastAPI(title="anth-hackathon26 matching engine")
app.include_router(health_router)
```

- [ ] **Step 3.4 — Run test, expect pass**

Run: `uv run pytest tests/test_health.py -v`
Expected: 1 passed

- [ ] **Step 3.5 — Commit**

```bash
git add server/main.py server/api/ server/db/session.py tests/test_health.py
git commit -m "feat: FastAPI skeleton with /health endpoint"
```

---

## Task 4 — Pytest infrastructure (conftest with test DB + client)

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 4.1 — Write a placeholder test that uses the fixtures**

Append to `tests/test_db_engine.py`:
```python
async def test_test_db_url_is_separate(test_engine):
    # The test_engine fixture should point at matching_test, not matching.
    assert "matching_test" in str(test_engine.url)
```

- [ ] **Step 4.2 — Run, expect failure (fixture not defined)**

Run: `uv run pytest tests/test_db_engine.py::test_test_db_url_is_separate -v`
Expected: `fixture 'test_engine' not found`

- [ ] **Step 4.3 — Implement conftest**

`tests/conftest.py`:
```python
import asyncio
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from server.config import get_settings
from server.db.engine import get_engine, get_session_maker
from server.main import app


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    settings = get_settings()
    engine = create_async_engine(settings.test_database_url, future=True)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
async def test_session_maker(test_engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture
async def db(test_session_maker: async_sessionmaker) -> AsyncGenerator[AsyncSession, None]:
    async with test_session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(test_engine: AsyncEngine, monkeypatch) -> AsyncGenerator[AsyncClient, None]:
    # Point the running app at the test database for HTTP-level tests.
    get_engine.cache_clear()
    get_session_maker.cache_clear()
    monkeypatch.setattr("server.config.get_settings", lambda: get_settings())
    monkeypatch.setattr(
        "server.db.engine.get_engine",
        lambda: test_engine,
    )
    monkeypatch.setattr(
        "server.db.engine.get_session_maker",
        lambda: async_sessionmaker(test_engine, expire_on_commit=False),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
```

- [ ] **Step 4.4 — Run, expect pass**

Run: `uv run pytest tests/test_db_engine.py -v`
Expected: 2 passed

- [ ] **Step 4.5 — Commit**

```bash
git add tests/conftest.py tests/test_db_engine.py
git commit -m "test: pytest fixtures for test DB engine and HTTP client"
```

---

## Task 5 — Alembic setup (async-aware) + ULID base

**Files:**
- Create: `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/.gitkeep`
- Create: `server/db/base.py`

- [ ] **Step 5.1 — Write the failing test**

Create `tests/test_models_base.py`:
```python
from sqlalchemy import Column, String

from server.db.base import Base, ULIDPK, generate_ulid


class _Probe(Base):
    __tablename__ = "_probe_table"
    id: ULIDPK
    label = Column(String)


def test_ulid_generator_returns_26_char_string():
    u = generate_ulid()
    assert isinstance(u, str)
    assert len(u) == 26


def test_base_is_declarative():
    assert hasattr(Base, "metadata")
```

- [ ] **Step 5.2 — Run, expect failure**

Run: `uv run pytest tests/test_models_base.py -v`
Expected: ImportError on `server.db.base`.

- [ ] **Step 5.3 — Implement Base + ULID**

`server/db/base.py`:
```python
from datetime import datetime
from typing import Annotated

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, MappedColumn, mapped_column
from ulid import ULID


def generate_ulid() -> str:
    return str(ULID())


class Base(DeclarativeBase):
    """Declarative base with sensible Postgres defaults."""


# Type alias for ULID primary keys, consistent across all tables.
ULIDPK = Annotated[
    str,
    mapped_column(String(26), primary_key=True, default=generate_ulid),
]

# Created/updated timestamps used on every queue table.
CreatedAt = Annotated[
    datetime,
    mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False),
]

UpdatedAt = Annotated[
    datetime,
    mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
]
```

- [ ] **Step 5.4 — Initialize alembic**

Run: `uv run alembic init -t async alembic`
This creates `alembic/`, `alembic/env.py`, `alembic.ini`, `alembic/script.py.mako`, `alembic/versions/`.

Edit `alembic.ini`: comment out the `sqlalchemy.url` line (we read from env).

- [ ] **Step 5.5 — Wire alembic to our settings + Base**

Replace `alembic/env.py` content:
```python
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from server.config import get_settings
from server.db.base import Base
# Import all model modules so their tables are attached to Base.metadata.
# (Modules added in subsequent tasks; safe to import as they're created.)

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


run_migrations_online()
```

- [ ] **Step 5.6 — Generate empty initial migration to verify alembic plumbing**

Run:
```bash
uv run alembic revision -m "initial empty"
```
Expected: file created at `alembic/versions/<rev>_initial_empty.py`. Open it; the `upgrade()` and `downgrade()` bodies should be empty (just `pass`).

Run: `uv run alembic upgrade head`
Expected: completes silently. Verify `alembic_version` table exists:
```bash
docker compose exec db psql -U app -d matching -c "\dt"
```
Expected output includes `alembic_version`.

- [ ] **Step 5.7 — Run unit tests, expect pass**

Run: `uv run pytest tests/test_models_base.py -v`
Expected: 2 passed

- [ ] **Step 5.8 — Commit**

```bash
git add alembic.ini alembic/ server/db/base.py tests/test_models_base.py
git commit -m "feat: alembic async setup, Base declarative, ULID PK helper"
```

---

## Task 6 — Identity models (NGO + Account)

**Files:**
- Create: `server/db/identity.py`, `tests/test_models_identity.py`
- Create: `alembic/versions/<rev>_identity_tables.py`
- Modify: `alembic/env.py` (add import)

- [ ] **Step 6.1 — Write failing tests**

`tests/test_models_identity.py`:
```python
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from server.db.identity import NGO, Account


async def test_ngo_can_be_inserted_and_queried(db):
    ngo = NGO(name="Warchild", region_geohash_prefix="sv")
    db.add(ngo)
    await db.flush()

    fetched = (await db.execute(select(NGO).where(NGO.ngo_id == ngo.ngo_id))).scalar_one()
    assert fetched.name == "Warchild"
    assert len(fetched.ngo_id) == 26


async def test_account_phone_is_unique(db):
    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()

    a = Account(phone="+972501234567", ngo_id=ngo.ngo_id, language="he")
    db.add(a)
    await db.flush()

    dup = Account(phone="+972501234567", ngo_id=ngo.ngo_id, language="ar")
    db.add(dup)
    with pytest.raises(IntegrityError):
        await db.flush()
```

- [ ] **Step 6.2 — Run, expect failure**

Run: `uv run pytest tests/test_models_identity.py -v`
Expected: ImportError on `server.db.identity`.

- [ ] **Step 6.3 — Implement models**

`server/db/identity.py`:
```python
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.db.base import Base, CreatedAt, ULIDPK, UpdatedAt


class NGO(Base):
    __tablename__ = "ngo"

    ngo_id: Mapped[ULIDPK]
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    region_geohash_prefix: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    standing_orders: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    operator_pubkey: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]


class Account(Base):
    __tablename__ = "account"

    phone: Mapped[str] = mapped_column(String(32), primary_key=True)
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    account_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    home_geohash: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    last_known_geohash: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    push_token: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    app_last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    trust_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    channel_pref: Mapped[str] = mapped_column(String(16), default="auto", nullable=False)
    sms_fallback_after_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    source: Mapped[str] = mapped_column(String(16), default="app", nullable=False)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
```

- [ ] **Step 6.4 — Wire into alembic env**

Edit `alembic/env.py`, append after the existing imports:
```python
from server.db import identity  # noqa: F401  (registers tables on Base.metadata)
```

- [ ] **Step 6.5 — Generate + apply migration**

Run:
```bash
uv run alembic revision --autogenerate -m "identity tables"
uv run alembic upgrade head
```
Expected: a new `<rev>_identity_tables.py` file under `alembic/versions/`. After upgrade, `\dt` shows `ngo` and `account` tables.

**Apply to test DB too**, since fixtures hit `matching_test`:
```bash
DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/matching_test uv run alembic upgrade head
```

- [ ] **Step 6.6 — Run tests, expect pass**

Run: `uv run pytest tests/test_models_identity.py -v`
Expected: 2 passed

- [ ] **Step 6.7 — Commit**

```bash
git add server/db/identity.py alembic/env.py alembic/versions/ tests/test_models_identity.py
git commit -m "feat: NGO and Account models with migration"
```

---

## Task 7 — Alert + AlertDelivery models

**Files:**
- Create: `server/db/alerts.py`, `tests/test_models_alerts.py`
- Modify: `alembic/env.py`

- [ ] **Step 7.1 — Write failing tests**

`tests/test_models_alerts.py`:
```python
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from server.db.alerts import Alert, AlertDelivery
from server.db.identity import NGO, Account


async def test_alert_inserted_with_category_and_urgency(db):
    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()

    alert = Alert(
        ngo_id=ngo.ngo_id,
        person_name="Maya",
        last_seen_geohash="sv8d6",
        description="missing 8yo",
        region_geohash_prefix="sv8d",
        status="active",
        category="missing_child",
        urgency_tier="high",
        urgency_score=0.9,
        expires_at=datetime.now(UTC) + timedelta(days=2),
    )
    db.add(alert)
    await db.flush()

    fetched = (await db.execute(select(Alert).where(Alert.alert_id == alert.alert_id))).scalar_one()
    assert fetched.category == "missing_child"
    assert fetched.urgency_score == 0.9


async def test_alert_delivery_links_alert_and_recipient(db):
    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()
    acc = Account(phone="+972500000001", ngo_id=ngo.ngo_id)
    alert = Alert(ngo_id=ngo.ngo_id, person_name="X", status="active")
    db.add_all([acc, alert])
    await db.flush()

    delivery = AlertDelivery(
        ngo_id=ngo.ngo_id,
        alert_id=alert.alert_id,
        recipient_phone=acc.phone,
    )
    db.add(delivery)
    await db.flush()

    rows = (
        await db.execute(select(AlertDelivery).where(AlertDelivery.alert_id == alert.alert_id))
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].recipient_phone == "+972500000001"
```

- [ ] **Step 7.2 — Run, expect failure**

Run: `uv run pytest tests/test_models_alerts.py -v`
Expected: ImportError.

- [ ] **Step 7.3 — Implement**

`server/db/alerts.py`:
```python
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from server.db.base import Base, CreatedAt, ULIDPK, UpdatedAt


class Alert(Base):
    __tablename__ = "alert"

    alert_id: Mapped[ULIDPK]
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    person_name: Mapped[str] = mapped_column(String(200), nullable=False)
    photo_url: Mapped[Optional[str]] = mapped_column(String(1024))
    last_seen_geohash: Mapped[Optional[str]] = mapped_column(String(12))
    description: Mapped[Optional[str]] = mapped_column(Text)
    region_geohash_prefix: Mapped[Optional[str]] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    # Categorization (set by agent via categorize_alert; defaults nullable):
    category: Mapped[Optional[str]] = mapped_column(String(64))
    urgency_tier: Mapped[Optional[str]] = mapped_column(String(16))
    urgency_score: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]


class AlertDelivery(Base):
    __tablename__ = "alert_delivery"

    delivery_id: Mapped[ULIDPK]
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    alert_id: Mapped[str] = mapped_column(String(26), ForeignKey("alert.alert_id"), nullable=False)
    recipient_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    out_id: Mapped[Optional[str]] = mapped_column(String(26))   # FK→OutboundMessage added later
    sent_at: Mapped[CreatedAt]
```

- [ ] **Step 7.4 — Update alembic env**

Edit `alembic/env.py`, append:
```python
from server.db import alerts  # noqa: F401
```

- [ ] **Step 7.5 — Generate + apply migration (both DBs)**

```bash
uv run alembic revision --autogenerate -m "alert and alert_delivery"
uv run alembic upgrade head
DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/matching_test uv run alembic upgrade head
```

- [ ] **Step 7.6 — Run tests, expect pass**

Run: `uv run pytest tests/test_models_alerts.py -v`
Expected: 2 passed

- [ ] **Step 7.7 — Commit**

```bash
git add server/db/alerts.py alembic/env.py alembic/versions/ tests/test_models_alerts.py
git commit -m "feat: Alert and AlertDelivery models with categorization columns"
```

---

## Task 8 — Message models (InboundMessage, TriagedMessage, Bucket) with pgvector

**Files:**
- Create: `server/db/messages.py`, `tests/test_models_messages.py`
- Modify: `alembic/env.py`

- [ ] **Step 8.1 — Write failing tests**

`tests/test_models_messages.py`:
```python
import json

from sqlalchemy import select

from server.db.alerts import Alert
from server.db.identity import NGO, Account
from server.db.messages import Bucket, InboundMessage, TriagedMessage


async def test_inbound_message_with_jsonb_columns(db):
    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()
    acc = Account(phone="+972500000001", ngo_id=ngo.ngo_id)
    alert = Alert(ngo_id=ngo.ngo_id, person_name="Maya", status="active")
    db.add_all([acc, alert])
    await db.flush()

    msg = InboundMessage(
        ngo_id=ngo.ngo_id,
        channel="app",
        sender_phone=acc.phone,
        in_reply_to_alert_id=alert.alert_id,
        body="saw a girl matching photo",
        media_urls=["https://example/photo.jpg"],
        raw={"jwt_sub": "abc"},
        status="new",
    )
    db.add(msg)
    await db.flush()

    fetched = (
        await db.execute(select(InboundMessage).where(InboundMessage.msg_id == msg.msg_id))
    ).scalar_one()
    assert fetched.media_urls == ["https://example/photo.jpg"]
    assert fetched.raw == {"jwt_sub": "abc"}


async def test_triaged_message_holds_embedding(db):
    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()
    acc = Account(phone="+972500000002", ngo_id=ngo.ngo_id)
    db.add(acc)
    await db.flush()

    inbound = InboundMessage(
        ngo_id=ngo.ngo_id,
        channel="app",
        sender_phone=acc.phone,
        body="x",
    )
    db.add(inbound)
    await db.flush()

    triaged = TriagedMessage(
        msg_id=inbound.msg_id,
        ngo_id=ngo.ngo_id,
        classification="sighting",
        geohash6="sv8d6r",
        geohash_source="app_gps",
        confidence=0.9,
        language="he",
        trust_score=0.7,
        bucket_key="A1|sv8d|2026-04-25T10:00:00",
        body_embedding=[0.0] * 512,
    )
    db.add(triaged)
    await db.flush()

    fetched = (
        await db.execute(select(TriagedMessage).where(TriagedMessage.msg_id == inbound.msg_id))
    ).scalar_one()
    assert len(fetched.body_embedding) == 512


async def test_bucket_is_unique_per_key(db):
    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()
    alert = Alert(ngo_id=ngo.ngo_id, person_name="Maya", status="active")
    db.add(alert)
    await db.flush()

    from datetime import UTC, datetime
    b = Bucket(
        bucket_key="A1|sv8d|2026-04-25T10:00:00",
        ngo_id=ngo.ngo_id,
        alert_id=alert.alert_id,
        geohash_prefix_4="sv8d",
        window_start=datetime.now(UTC),
        window_length_ms=3000,
        status="open",
    )
    db.add(b)
    await db.flush()
    fetched = (await db.execute(select(Bucket).where(Bucket.bucket_key == b.bucket_key))).scalar_one()
    assert fetched.status == "open"
```

- [ ] **Step 8.2 — Run, expect failure**

Run: `uv run pytest tests/test_models_messages.py -v`
Expected: ImportError.

- [ ] **Step 8.3 — Implement**

`server/db/messages.py`:
```python
from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from server.db.base import Base, CreatedAt, ULIDPK


class InboundMessage(Base):
    __tablename__ = "inbound_message"

    msg_id: Mapped[ULIDPK]
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    sender_phone: Mapped[str] = mapped_column(
        String(32), ForeignKey("account.phone"), nullable=False
    )
    in_reply_to_alert_id: Mapped[Optional[str]] = mapped_column(
        String(26), ForeignKey("alert.alert_id")
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    media_urls: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    raw: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    received_at: Mapped[CreatedAt]
    status: Mapped[str] = mapped_column(String(16), default="new", nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    claimed_by: Mapped[Optional[str]] = mapped_column(String(64))


class TriagedMessage(Base):
    __tablename__ = "triaged_message"

    msg_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("inbound_message.msg_id"), primary_key=True
    )
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    classification: Mapped[str] = mapped_column(String(16), nullable=False)
    geohash6: Mapped[Optional[str]] = mapped_column(String(12))
    geohash_source: Mapped[Optional[str]] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    language: Mapped[Optional[str]] = mapped_column(String(8))
    duplicate_of: Mapped[Optional[str]] = mapped_column(String(26))
    trust_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    bucket_key: Mapped[str] = mapped_column(String(128), nullable=False)
    body_embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(512))
    created_at: Mapped[CreatedAt]


class Bucket(Base):
    __tablename__ = "bucket"

    bucket_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    alert_id: Mapped[str] = mapped_column(String(26), ForeignKey("alert.alert_id"), nullable=False)
    geohash_prefix_4: Mapped[Optional[str]] = mapped_column(String(4))
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_length_ms: Mapped[int] = mapped_column(Integer, default=3000, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="open", nullable=False)
    claimed_by: Mapped[Optional[str]] = mapped_column(String(64))
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[CreatedAt]
```

- [ ] **Step 8.4 — Wire into alembic + import vector type**

Edit `alembic/env.py`:
```python
from pgvector.sqlalchemy import Vector  # noqa: F401  (so autogenerate sees the type)
from server.db import messages  # noqa: F401
```

- [ ] **Step 8.5 — Migration**

```bash
uv run alembic revision --autogenerate -m "inbound_message triaged_message bucket"
uv run alembic upgrade head
DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/matching_test uv run alembic upgrade head
```

- [ ] **Step 8.6 — Tests**

Run: `uv run pytest tests/test_models_messages.py -v`
Expected: 3 passed

- [ ] **Step 8.7 — Commit**

```bash
git add server/db/messages.py alembic/env.py alembic/versions/ tests/test_models_messages.py
git commit -m "feat: InboundMessage, TriagedMessage, Bucket with pgvector embedding"
```

---

## Task 9 — Decision models (AgentDecision + ToolCall)

**Files:**
- Create: `server/db/decisions.py`, `tests/test_models_decisions.py`
- Modify: `alembic/env.py`

- [ ] **Step 9.1 — Write failing tests**

`tests/test_models_decisions.py`:
```python
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from server.db.alerts import Alert
from server.db.decisions import AgentDecision, ToolCall
from server.db.identity import NGO


async def _seed_bucket(db):
    from datetime import UTC, datetime
    from server.db.messages import Bucket

    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()
    alert = Alert(ngo_id=ngo.ngo_id, person_name="Maya", status="active")
    db.add(alert)
    await db.flush()
    b = Bucket(
        bucket_key=f"{alert.alert_id}|sv8d|2026-04-25T10",
        ngo_id=ngo.ngo_id,
        alert_id=alert.alert_id,
        geohash_prefix_4="sv8d",
        window_start=datetime.now(UTC),
    )
    db.add(b)
    await db.flush()
    return ngo, alert, b


async def test_agent_decision_unique_per_bucket(db):
    ngo, alert, b = await _seed_bucket(db)
    d1 = AgentDecision(
        ngo_id=ngo.ngo_id,
        bucket_key=b.bucket_key,
        model="claude-sonnet-4-6",
        prompt_hash="abc",
        reasoning_summary="ok",
        tool_calls=[],
        turns=[],
        total_turns=1,
        latency_ms=1500,
        cost_usd=0.04,
    )
    db.add(d1)
    await db.flush()

    d2 = AgentDecision(
        ngo_id=ngo.ngo_id,
        bucket_key=b.bucket_key,
        model="claude-sonnet-4-6",
        prompt_hash="abc",
        reasoning_summary="dup",
        tool_calls=[],
        turns=[],
        total_turns=1,
        latency_ms=1500,
        cost_usd=0.04,
    )
    db.add(d2)
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_tool_call_idempotency_key_unique(db):
    ngo, alert, b = await _seed_bucket(db)
    d = AgentDecision(
        ngo_id=ngo.ngo_id,
        bucket_key=b.bucket_key,
        model="claude-sonnet-4-6",
        prompt_hash="abc",
        reasoning_summary="ok",
        tool_calls=[],
        turns=[],
        total_turns=1,
        latency_ms=1500,
        cost_usd=0.04,
    )
    db.add(d)
    await db.flush()

    tc1 = ToolCall(
        ngo_id=ngo.ngo_id,
        decision_id=d.decision_id,
        tool_name="send",
        args={"a": 1},
        idempotency_key="key-123",
        mode="execute",
        approval_status="auto_executed",
    )
    db.add(tc1)
    await db.flush()

    tc2 = ToolCall(
        ngo_id=ngo.ngo_id,
        decision_id=d.decision_id,
        tool_name="send",
        args={"a": 1},
        idempotency_key="key-123",
        mode="execute",
        approval_status="auto_executed",
    )
    db.add(tc2)
    with pytest.raises(IntegrityError):
        await db.flush()
```

- [ ] **Step 9.2 — Run, expect failure**

Run: `uv run pytest tests/test_models_decisions.py -v`
Expected: ImportError.

- [ ] **Step 9.3 — Implement**

`server/db/decisions.py`:
```python
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from server.db.base import Base, CreatedAt, ULIDPK


class AgentDecision(Base):
    __tablename__ = "agent_decision"
    __table_args__ = (UniqueConstraint("bucket_key", name="uq_agent_decision_bucket_key"),)

    decision_id: Mapped[ULIDPK]
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    bucket_key: Mapped[str] = mapped_column(
        String(128), ForeignKey("bucket.bucket_key"), nullable=False
    )
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reasoning_summary: Mapped[Optional[str]] = mapped_column(Text)
    tool_calls: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    turns: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    total_turns: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[CreatedAt]


class ToolCall(Base):
    __tablename__ = "tool_call"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_tool_call_idempotency_key"),
    )

    call_id: Mapped[ULIDPK]
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    decision_id: Mapped[Optional[str]] = mapped_column(
        String(26), ForeignKey("agent_decision.decision_id")
    )
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    args: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    approval_status: Mapped[str] = mapped_column(String(16), nullable=False)
    decided_by: Mapped[Optional[str]] = mapped_column(String(64))
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revised_from_call_id: Mapped[Optional[str]] = mapped_column(
        String(26), ForeignKey("tool_call.call_id")
    )
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    claimed_by: Mapped[Optional[str]] = mapped_column(String(64))
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[CreatedAt]
```

- [ ] **Step 9.4 — Wire alembic**

Edit `alembic/env.py`, append:
```python
from server.db import decisions  # noqa: F401
```

- [ ] **Step 9.5 — Migration**

```bash
uv run alembic revision --autogenerate -m "agent_decision tool_call"
uv run alembic upgrade head
DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/matching_test uv run alembic upgrade head
```

- [ ] **Step 9.6 — Tests**

Run: `uv run pytest tests/test_models_decisions.py -v`
Expected: 2 passed

- [ ] **Step 9.7 — Commit**

```bash
git add server/db/decisions.py alembic/env.py alembic/versions/ tests/test_models_decisions.py
git commit -m "feat: AgentDecision and ToolCall with idempotency unique constraint"
```

---

## Task 10 — Output models (OutboundMessage + Sighting with embedding)

**Files:**
- Create: `server/db/outbound.py`, `tests/test_models_outbound.py`
- Modify: `alembic/env.py`

- [ ] **Step 10.1 — Write failing tests**

`tests/test_models_outbound.py`:
```python
from sqlalchemy import select

from server.db.alerts import Alert
from server.db.identity import NGO, Account
from server.db.outbound import OutboundMessage, Sighting


async def test_outbound_with_attempt_chain(db):
    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()
    acc = Account(phone="+972500000003", ngo_id=ngo.ngo_id)
    db.add(acc)
    await db.flush()

    push = OutboundMessage(
        ngo_id=ngo.ngo_id,
        recipient_phone=acc.phone,
        channel="app",
        body="hello",
        status="sending",
        attempt=1,
    )
    db.add(push)
    await db.flush()

    sms_fallback = OutboundMessage(
        ngo_id=ngo.ngo_id,
        recipient_phone=acc.phone,
        channel="sms",
        body="hello",
        status="queued",
        attempt=2,
        previous_out_id=push.out_id,
    )
    db.add(sms_fallback)
    await db.flush()

    rows = (
        await db.execute(
            select(OutboundMessage).where(OutboundMessage.recipient_phone == acc.phone)
        )
    ).scalars().all()
    assert len(rows) == 2


async def test_sighting_holds_embedding_and_photo_urls(db):
    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()
    alert = Alert(ngo_id=ngo.ngo_id, person_name="Maya", status="active")
    db.add(alert)
    await db.flush()

    s = Sighting(
        ngo_id=ngo.ngo_id,
        alert_id=alert.alert_id,
        observer_phone="+972500000004",
        geohash="sv8d6r",
        notes="bakery, walking south, red jacket",
        confidence=0.85,
        photo_urls=["https://x/y.jpg"],
        notes_embedding=[0.1] * 512,
    )
    db.add(s)
    await db.flush()

    fetched = (await db.execute(select(Sighting).where(Sighting.sighting_id == s.sighting_id))).scalar_one()
    assert fetched.photo_urls == ["https://x/y.jpg"]
    assert len(fetched.notes_embedding) == 512
```

- [ ] **Step 10.2 — Run, expect failure**

Run: `uv run pytest tests/test_models_outbound.py -v`
Expected: ImportError.

- [ ] **Step 10.3 — Implement**

`server/db/outbound.py`:
```python
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from server.db.base import Base, CreatedAt, ULIDPK


class OutboundMessage(Base):
    __tablename__ = "outbound_message"

    out_id: Mapped[ULIDPK]
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    tool_call_id: Mapped[Optional[str]] = mapped_column(String(26), ForeignKey("tool_call.call_id"))
    recipient_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[Optional[str]] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(16), default="queued", nullable=False)
    provider_msg_id: Mapped[Optional[str]] = mapped_column(String(128))
    error: Mapped[Optional[str]] = mapped_column(Text)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    previous_out_id: Mapped[Optional[str]] = mapped_column(
        String(26), ForeignKey("outbound_message.out_id")
    )
    created_at: Mapped[CreatedAt]


class Sighting(Base):
    __tablename__ = "sighting"

    sighting_id: Mapped[ULIDPK]
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    alert_id: Mapped[str] = mapped_column(String(26), ForeignKey("alert.alert_id"), nullable=False)
    observer_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    geohash: Mapped[str] = mapped_column(String(12), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    photo_urls: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    notes_embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(512))
    recorded_at: Mapped[CreatedAt]
```

- [ ] **Step 10.4 — Wire alembic**

Edit `alembic/env.py`, append:
```python
from server.db import outbound  # noqa: F401
```

- [ ] **Step 10.5 — Migration**

```bash
uv run alembic revision --autogenerate -m "outbound_message sighting"
uv run alembic upgrade head
DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/matching_test uv run alembic upgrade head
```

- [ ] **Step 10.6 — Tests**

Run: `uv run pytest tests/test_models_outbound.py -v`
Expected: 2 passed

- [ ] **Step 10.7 — Commit**

```bash
git add server/db/outbound.py alembic/env.py alembic/versions/ tests/test_models_outbound.py
git commit -m "feat: OutboundMessage and Sighting models with embedding column"
```

---

## Task 11 — Knowledge models (SightingCluster, Trajectory, Tag, TagAssignment)

**Files:**
- Create: `server/db/knowledge.py`, `tests/test_models_knowledge.py`
- Modify: `alembic/env.py`

- [ ] **Step 11.1 — Write failing tests**

`tests/test_models_knowledge.py`:
```python
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from server.db.alerts import Alert
from server.db.identity import NGO
from server.db.knowledge import SightingCluster, Tag, TagAssignment, Trajectory


async def _seed(db):
    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()
    alert = Alert(ngo_id=ngo.ngo_id, person_name="Maya", status="active")
    db.add(alert)
    await db.flush()
    return ngo, alert


async def test_sighting_cluster_with_member_ids(db):
    ngo, alert = await _seed(db)
    cluster = SightingCluster(
        ngo_id=ngo.ngo_id,
        alert_id=alert.alert_id,
        label="Yafo St bakery",
        center_geohash="sv8d6r",
        radius_m=200,
        sighting_ids=["S1", "S2", "S3"],
        sighting_count=3,
        mean_confidence=0.85,
        status="active",
        embedding=[0.0] * 512,
    )
    db.add(cluster)
    await db.flush()

    fetched = (
        await db.execute(select(SightingCluster).where(SightingCluster.cluster_id == cluster.cluster_id))
    ).scalar_one()
    assert fetched.sighting_ids == ["S1", "S2", "S3"]
    assert len(fetched.embedding) == 512


async def test_trajectory_points_jsonb(db):
    ngo, alert = await _seed(db)
    t = Trajectory(
        ngo_id=ngo.ngo_id,
        alert_id=alert.alert_id,
        points=[
            {"geohash": "sv8d6r", "time": "2026-04-25T10:00:00Z", "source_sighting_ids": ["S1"]},
            {"geohash": "sv8d6q", "time": "2026-04-25T10:05:00Z", "source_sighting_ids": ["S2"]},
        ],
        direction_deg=180.0,
        speed_kmh=3.0,
        confidence=0.7,
        status="active",
    )
    db.add(t)
    await db.flush()
    fetched = (
        await db.execute(select(Trajectory).where(Trajectory.trajectory_id == t.trajectory_id))
    ).scalar_one()
    assert len(fetched.points) == 2


async def test_tag_unique_within_namespace(db):
    ngo, _ = await _seed(db)
    t1 = Tag(
        ngo_id=ngo.ngo_id, namespace="message", name="vehicle_sighting", created_by="agent"
    )
    db.add(t1)
    await db.flush()
    t2 = Tag(
        ngo_id=ngo.ngo_id, namespace="message", name="vehicle_sighting", created_by="agent"
    )
    db.add(t2)
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_tag_assignment_idempotent(db):
    ngo, alert = await _seed(db)
    tag = Tag(
        ngo_id=ngo.ngo_id, namespace="alert", name="trajectory_hint", created_by="agent"
    )
    db.add(tag)
    await db.flush()

    a1 = TagAssignment(
        ngo_id=ngo.ngo_id,
        tag_id=tag.tag_id,
        entity_type="alert",
        entity_id=alert.alert_id,
        confidence=0.9,
        applied_by="agent",
        alert_id=alert.alert_id,
    )
    db.add(a1)
    await db.flush()

    a2 = TagAssignment(
        ngo_id=ngo.ngo_id,
        tag_id=tag.tag_id,
        entity_type="alert",
        entity_id=alert.alert_id,
        confidence=0.95,
        applied_by="agent",
        alert_id=alert.alert_id,
    )
    db.add(a2)
    with pytest.raises(IntegrityError):
        await db.flush()
```

- [ ] **Step 11.2 — Run, expect failure**

Run: `uv run pytest tests/test_models_knowledge.py -v`
Expected: ImportError.

- [ ] **Step 11.3 — Implement**

`server/db/knowledge.py`:
```python
from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from server.db.base import Base, CreatedAt, ULIDPK, UpdatedAt


class SightingCluster(Base):
    __tablename__ = "sighting_cluster"

    cluster_id: Mapped[ULIDPK]
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    alert_id: Mapped[str] = mapped_column(String(26), ForeignKey("alert.alert_id"), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    center_geohash: Mapped[str] = mapped_column(String(12), nullable=False)
    radius_m: Mapped[int] = mapped_column(Integer, nullable=False)
    time_window_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    time_window_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sighting_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    sighting_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mean_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    merged_into: Mapped[Optional[str]] = mapped_column(
        String(26), ForeignKey("sighting_cluster.cluster_id")
    )
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(512))
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    last_member_added_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class Trajectory(Base):
    __tablename__ = "trajectory"

    trajectory_id: Mapped[ULIDPK]
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    alert_id: Mapped[str] = mapped_column(String(26), ForeignKey("alert.alert_id"), nullable=False)
    points: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)
    direction_deg: Mapped[Optional[float]] = mapped_column(Float)
    speed_kmh: Mapped[Optional[float]] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    last_extended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[CreatedAt]


class Tag(Base):
    __tablename__ = "tag"
    __table_args__ = (
        UniqueConstraint("ngo_id", "namespace", "name", name="uq_tag_ngo_ns_name"),
    )

    tag_id: Mapped[ULIDPK]
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    namespace: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(16), default="agent", nullable=False)
    created_at: Mapped[CreatedAt]


class TagAssignment(Base):
    __tablename__ = "tag_assignment"
    __table_args__ = (
        UniqueConstraint(
            "tag_id", "entity_type", "entity_id", name="uq_tag_assignment_tag_entity"
        ),
    )

    assignment_id: Mapped[ULIDPK]
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    tag_id: Mapped[str] = mapped_column(String(26), ForeignKey("tag.tag_id"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(26), nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    applied_by: Mapped[str] = mapped_column(String(16), default="agent", nullable=False)
    applied_by_id: Mapped[Optional[str]] = mapped_column(String(64))
    alert_id: Mapped[Optional[str]] = mapped_column(String(26), ForeignKey("alert.alert_id"))
    created_at: Mapped[CreatedAt]
```

- [ ] **Step 11.4 — Wire alembic**

Edit `alembic/env.py`, append:
```python
from server.db import knowledge  # noqa: F401
```

- [ ] **Step 11.5 — Migration**

```bash
uv run alembic revision --autogenerate -m "sighting_cluster trajectory tag tag_assignment"
uv run alembic upgrade head
DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/matching_test uv run alembic upgrade head
```

- [ ] **Step 11.6 — Tests**

Run: `uv run pytest tests/test_models_knowledge.py -v`
Expected: 4 passed

- [ ] **Step 11.7 — Commit**

```bash
git add server/db/knowledge.py alembic/env.py alembic/versions/ tests/test_models_knowledge.py
git commit -m "feat: SightingCluster, Trajectory, Tag, TagAssignment models"
```

---

## Task 12 — Trust model (BadActor)

**Files:**
- Create: `server/db/trust.py`, `tests/test_models_trust.py`
- Modify: `alembic/env.py`

- [ ] **Step 12.1 — Write failing test**

`tests/test_models_trust.py`:
```python
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from server.db.identity import NGO
from server.db.trust import BadActor


async def test_bad_actor_with_expiry(db):
    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()

    ba = BadActor(
        phone="+972500000099",
        ngo_id=ngo.ngo_id,
        reason="repeated false sightings",
        marked_by="agent",
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db.add(ba)
    await db.flush()

    fetched = (
        await db.execute(select(BadActor).where(BadActor.phone == "+972500000099"))
    ).scalar_one()
    assert fetched.reason == "repeated false sightings"
```

- [ ] **Step 12.2 — Run, expect failure**

Run: `uv run pytest tests/test_models_trust.py -v`
Expected: ImportError.

- [ ] **Step 12.3 — Implement**

`server/db/trust.py`:
```python
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from server.db.base import Base, CreatedAt


class BadActor(Base):
    __tablename__ = "bad_actor"

    phone: Mapped[str] = mapped_column(String(32), primary_key=True)
    ngo_id: Mapped[str] = mapped_column(String(26), ForeignKey("ngo.ngo_id"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    marked_by: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[CreatedAt]
```

- [ ] **Step 12.4 — Wire alembic + migrate**

Edit `alembic/env.py`, append:
```python
from server.db import trust  # noqa: F401
```

```bash
uv run alembic revision --autogenerate -m "bad_actor"
uv run alembic upgrade head
DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/matching_test uv run alembic upgrade head
```

- [ ] **Step 12.5 — Tests**

Run: `uv run pytest tests/test_models_trust.py -v`
Expected: 1 passed

- [ ] **Step 12.6 — Commit**

```bash
git add server/db/trust.py alembic/env.py alembic/versions/ tests/test_models_trust.py
git commit -m "feat: BadActor model"
```

---

## Task 13 — Hot-path indices (HNSW + partial + prefix LIKE)

**Files:**
- Create: `tests/test_indices.py`
- Create: `alembic/versions/<rev>_hot_path_indices.py` (manually written, not autogenerated)

- [ ] **Step 13.1 — Write failing test**

`tests/test_indices.py`:
```python
from sqlalchemy import text


REQUIRED_INDEXES = {
    # name pattern → table
    "ix_account_last_known_geohash_pattern": "account",
    "ix_account_home_geohash_pattern": "account",
    "ix_triaged_message_bucket_key": "triaged_message",
    "ix_triaged_message_sender_received": "inbound_message",
    "ix_agent_decision_alert_created": "agent_decision",
    "ix_inbound_message_status_new": "inbound_message",
    "ix_bucket_status_window": "bucket",
    "ix_outbound_message_recipient_created": "outbound_message",
    "ix_alert_delivery_alert_recipient": "alert_delivery",
    "ix_tool_call_pending": "tool_call",
    "ix_triaged_message_body_embedding_hnsw": "triaged_message",
    "ix_sighting_notes_embedding_hnsw": "sighting",
    "ix_sighting_cluster_embedding_hnsw": "sighting_cluster",
    "ix_sighting_alert_geohash_recorded": "sighting",
    "ix_sighting_observer_recorded": "sighting",
    "ix_sighting_cluster_alert_status_added": "sighting_cluster",
    "ix_sighting_cluster_alert_geohash_active": "sighting_cluster",
    "ix_trajectory_alert_status_extended": "trajectory",
    "ix_tag_assignment_entity": "tag_assignment",
    "ix_tag_assignment_tag_entity_alert": "tag_assignment",
    "ix_alert_active_urgency": "alert",
}


async def test_all_required_indexes_exist(db):
    found = (
        await db.execute(
            text(
                "SELECT indexname FROM pg_indexes WHERE schemaname='public'"
            )
        )
    ).scalars().all()
    missing = [name for name in REQUIRED_INDEXES if name not in found]
    assert not missing, f"missing indices: {missing}"
```

- [ ] **Step 13.2 — Run, expect failure**

Run: `uv run pytest tests/test_indices.py -v`
Expected: failure listing missing indices.

- [ ] **Step 13.3 — Hand-write the migration**

Run: `uv run alembic revision -m "hot_path_indices"`

Replace the generated `upgrade()` and `downgrade()` with:
```python
from alembic import op


def upgrade() -> None:
    # Account geo prefix lookups (LIKE 'sv8d%')
    op.execute(
        "CREATE INDEX ix_account_last_known_geohash_pattern "
        "ON account (last_known_geohash text_pattern_ops)"
    )
    op.execute(
        "CREATE INDEX ix_account_home_geohash_pattern "
        "ON account (home_geohash text_pattern_ops)"
    )

    # Bucket reads
    op.execute(
        "CREATE INDEX ix_triaged_message_bucket_key ON triaged_message (bucket_key)"
    )

    # Per-sender history (note: sender_phone lives on inbound_message)
    op.execute(
        "CREATE INDEX ix_triaged_message_sender_received "
        "ON inbound_message (sender_phone, received_at DESC)"
    )

    # Recent decisions per alert (alert_id is denormalized via bucket join in code;
    # for direct support, index on bucket_key — alert_id resolved at read time).
    # We add an alert_id column index via a subquery-friendly partial in code if needed.
    op.execute(
        "CREATE INDEX ix_agent_decision_alert_created "
        "ON agent_decision (bucket_key, created_at DESC)"
    )

    # Worker claim queues
    op.execute(
        "CREATE INDEX ix_inbound_message_status_new "
        "ON inbound_message (status, received_at) WHERE status = 'new'"
    )
    op.execute(
        "CREATE INDEX ix_bucket_status_window "
        "ON bucket (status, window_start) WHERE status = 'open'"
    )
    op.execute(
        "CREATE INDEX ix_tool_call_pending "
        "ON tool_call (approval_status, status) WHERE status = 'pending'"
    )

    # Outbound history
    op.execute(
        "CREATE INDEX ix_outbound_message_recipient_created "
        "ON outbound_message (recipient_phone, created_at DESC)"
    )

    # AlertDelivery roster lookups
    op.execute(
        "CREATE INDEX ix_alert_delivery_alert_recipient "
        "ON alert_delivery (alert_id, recipient_phone)"
    )

    # HNSW vector indices (cosine distance)
    op.execute(
        "CREATE INDEX ix_triaged_message_body_embedding_hnsw "
        "ON triaged_message USING hnsw (body_embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_sighting_notes_embedding_hnsw "
        "ON sighting USING hnsw (notes_embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_sighting_cluster_embedding_hnsw "
        "ON sighting_cluster USING hnsw (embedding vector_cosine_ops)"
    )

    # Sighting + cluster geo / observer lookups
    op.execute(
        "CREATE INDEX ix_sighting_alert_geohash_recorded "
        "ON sighting (alert_id, geohash text_pattern_ops, recorded_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_sighting_observer_recorded "
        "ON sighting (observer_phone, recorded_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_sighting_cluster_alert_status_added "
        "ON sighting_cluster (alert_id, status, last_member_added_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_sighting_cluster_alert_geohash_active "
        "ON sighting_cluster (alert_id, center_geohash text_pattern_ops) "
        "WHERE status = 'active'"
    )
    op.execute(
        "CREATE INDEX ix_trajectory_alert_status_extended "
        "ON trajectory (alert_id, status, last_extended_at DESC)"
    )

    # Tag lookups
    op.execute(
        "CREATE INDEX ix_tag_assignment_entity "
        "ON tag_assignment (entity_type, entity_id)"
    )
    op.execute(
        "CREATE INDEX ix_tag_assignment_tag_entity_alert "
        "ON tag_assignment (tag_id, entity_type, alert_id)"
    )

    # Heartbeat scheduler scan for active alerts
    op.execute(
        "CREATE INDEX ix_alert_active_urgency "
        "ON alert (ngo_id, status, urgency_tier) WHERE status = 'active'"
    )


def downgrade() -> None:
    for name in [
        "ix_account_last_known_geohash_pattern",
        "ix_account_home_geohash_pattern",
        "ix_triaged_message_bucket_key",
        "ix_triaged_message_sender_received",
        "ix_agent_decision_alert_created",
        "ix_inbound_message_status_new",
        "ix_bucket_status_window",
        "ix_tool_call_pending",
        "ix_outbound_message_recipient_created",
        "ix_alert_delivery_alert_recipient",
        "ix_triaged_message_body_embedding_hnsw",
        "ix_sighting_notes_embedding_hnsw",
        "ix_sighting_cluster_embedding_hnsw",
        "ix_sighting_alert_geohash_recorded",
        "ix_sighting_observer_recorded",
        "ix_sighting_cluster_alert_status_added",
        "ix_sighting_cluster_alert_geohash_active",
        "ix_trajectory_alert_status_extended",
        "ix_tag_assignment_entity",
        "ix_tag_assignment_tag_entity_alert",
        "ix_alert_active_urgency",
    ]:
        op.execute(f"DROP INDEX IF EXISTS {name}")
```

- [ ] **Step 13.4 — Apply migration to both DBs**

```bash
uv run alembic upgrade head
DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/matching_test uv run alembic upgrade head
```

- [ ] **Step 13.5 — Run tests, expect pass**

Run: `uv run pytest tests/test_indices.py -v`
Expected: 1 passed

- [ ] **Step 13.6 — Commit**

```bash
git add alembic/versions/ tests/test_indices.py
git commit -m "feat: hot-path indices (HNSW, partial queues, prefix LIKE)"
```

---

## Task 14 — EventBus Protocol + Postgres LISTEN/NOTIFY implementation

**Files:**
- Create: `server/eventbus/__init__.py`, `server/eventbus/base.py`, `server/eventbus/postgres.py`
- Create: `tests/test_eventbus_postgres.py`

- [ ] **Step 14.1 — Write failing test**

`tests/test_eventbus_postgres.py`:
```python
import asyncio

from server.eventbus.postgres import PostgresEventBus


async def test_publish_subscribe_round_trip(test_engine):
    bus = PostgresEventBus(test_engine)
    received: list[str] = []

    stop = asyncio.Event()

    async def consumer():
        async for payload in bus.subscribe("test_channel"):
            received.append(payload)
            stop.set()
            break

    task = asyncio.create_task(consumer())
    # give the LISTEN time to register
    await asyncio.sleep(0.2)

    await bus.publish("test_channel", "hello")
    await asyncio.wait_for(stop.wait(), timeout=2.0)

    task.cancel()
    assert received == ["hello"]
    await bus.close()
```

- [ ] **Step 14.2 — Run, expect failure**

Run: `uv run pytest tests/test_eventbus_postgres.py -v`
Expected: ImportError on `server.eventbus.postgres`.

- [ ] **Step 14.3 — Implement Protocol + Postgres backend**

`server/eventbus/__init__.py`:
```python
```

`server/eventbus/base.py`:
```python
from collections.abc import AsyncIterator
from typing import Protocol


class EventBus(Protocol):
    async def publish(self, channel: str, payload: str) -> None: ...

    def subscribe(self, channel: str) -> AsyncIterator[str]: ...

    async def close(self) -> None: ...
```

`server/eventbus/postgres.py`:
```python
import asyncio
from collections.abc import AsyncIterator

import asyncpg
from sqlalchemy.ext.asyncio import AsyncEngine


class PostgresEventBus:
    """Postgres LISTEN/NOTIFY-backed event bus.

    Used by workers to wake up on new rows without polling. Channel names
    are postgres identifiers, so use ASCII-safe names like 'new_inbound',
    'bucket_open', 'toolcalls_pending', 'suggestions_pending'.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    def _dsn(self) -> str:
        # Convert SQLAlchemy URL to plain DSN for asyncpg.
        url = self._engine.url
        return (
            f"postgresql://{url.username}:{url.password}@{url.host}:{url.port}/{url.database}"
        )

    async def publish(self, channel: str, payload: str) -> None:
        conn = await asyncpg.connect(self._dsn())
        try:
            # asyncpg parameterizes via $1; for NOTIFY we have to compose carefully.
            # Channel must be a safe identifier; payload is escaped.
            await conn.execute(
                f"NOTIFY {channel}, $1",  # noqa: S608  (channel is from trusted code)
                payload,
            )
        finally:
            await conn.close()

    async def subscribe(self, channel: str) -> AsyncIterator[str]:
        conn = await asyncpg.connect(self._dsn())
        queue: asyncio.Queue[str] = asyncio.Queue()

        def listener(_conn, _pid, _channel, payload):
            queue.put_nowait(payload)

        try:
            await conn.add_listener(channel, listener)
            while True:
                yield await queue.get()
        finally:
            await conn.remove_listener(channel, listener)
            await conn.close()

    async def close(self) -> None:
        # Per-call connections; nothing to dispose globally.
        return None
```

- [ ] **Step 14.4 — Run test, expect pass**

Run: `uv run pytest tests/test_eventbus_postgres.py -v`
Expected: 1 passed

If flaky due to timing, increase the `asyncio.sleep(0.2)` in the test to 0.5.

- [ ] **Step 14.5 — Commit**

```bash
git add server/eventbus/ tests/test_eventbus_postgres.py
git commit -m "feat: EventBus Protocol and Postgres LISTEN/NOTIFY backend"
```

---

## Task 15 — SmsProvider Protocol + SimSmsProvider

**Files:**
- Create: `server/transports/__init__.py`, `server/transports/sms_base.py`, `server/transports/sim_sms.py`
- Create: `tests/test_sim_sms.py`

- [ ] **Step 15.1 — Write failing test**

`tests/test_sim_sms.py`:
```python
from server.transports.sim_sms import SimSmsProvider


async def test_sim_send_records_messages():
    sim = SimSmsProvider()
    r1 = await sim.send(to="+972500000001", body="hello", idempotency_key="k1")
    r2 = await sim.send(to="+972500000002", body="bonjour", idempotency_key="k2")

    assert r1.provider_msg_id and r2.provider_msg_id
    assert len(sim.sent) == 2
    assert sim.sent[0].to == "+972500000001"
    assert sim.sent[0].body == "hello"


async def test_sim_send_idempotency_returns_same_id():
    sim = SimSmsProvider()
    r1 = await sim.send(to="+972500000001", body="hi", idempotency_key="k1")
    r2 = await sim.send(to="+972500000001", body="hi", idempotency_key="k1")

    assert r1.provider_msg_id == r2.provider_msg_id
    assert len(sim.sent) == 1   # second call deduped


async def test_sim_inbound_handler_returns_none():
    # SimSmsProvider drives inbound through its own UI / API, not via webhook.
    sim = SimSmsProvider()
    assert sim.inbound_handler() is None
```

- [ ] **Step 15.2 — Run, expect failure**

Run: `uv run pytest tests/test_sim_sms.py -v`
Expected: ImportError.

- [ ] **Step 15.3 — Implement Protocol + Sim**

`server/transports/__init__.py`:
```python
```

`server/transports/sms_base.py`:
```python
from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class SendResult:
    provider_msg_id: str
    accepted: bool = True
    error: Optional[str] = None


@dataclass
class SentMessage:
    to: str
    body: str
    media: list[str]
    idempotency_key: Optional[str]
    provider_msg_id: str


class SmsProvider(Protocol):
    async def send(
        self,
        to: str,
        body: str,
        media: Optional[list[str]] = None,
        idempotency_key: Optional[str] = None,
    ) -> SendResult: ...

    def inbound_handler(self) -> object | None:
        """Returns an ASGI app to mount, or None for sim providers
        that drive inbound through their own UI."""
        ...
```

`server/transports/sim_sms.py`:
```python
import uuid
from typing import Optional

from server.transports.sms_base import SendResult, SentMessage


class SimSmsProvider:
    """In-process SMS provider for the hackathon demo.

    Outbound: appends to `self.sent` and returns a fake provider_msg_id.
    Inbound: not handled here — the simulator drives the API tier directly
    via the in-process app channel.
    """

    def __init__(self) -> None:
        self.sent: list[SentMessage] = []
        self._idem: dict[str, str] = {}

    async def send(
        self,
        to: str,
        body: str,
        media: Optional[list[str]] = None,
        idempotency_key: Optional[str] = None,
    ) -> SendResult:
        if idempotency_key and idempotency_key in self._idem:
            return SendResult(provider_msg_id=self._idem[idempotency_key])
        provider_msg_id = f"sim-{uuid.uuid4().hex}"
        if idempotency_key:
            self._idem[idempotency_key] = provider_msg_id
        self.sent.append(
            SentMessage(
                to=to,
                body=body,
                media=media or [],
                idempotency_key=idempotency_key,
                provider_msg_id=provider_msg_id,
            )
        )
        return SendResult(provider_msg_id=provider_msg_id)

    def inbound_handler(self) -> None:
        return None
```

- [ ] **Step 15.4 — Tests**

Run: `uv run pytest tests/test_sim_sms.py -v`
Expected: 3 passed

- [ ] **Step 15.5 — Commit**

```bash
git add server/transports/ tests/test_sim_sms.py
git commit -m "feat: SmsProvider Protocol and SimSmsProvider with idempotency"
```

---

## Task 16 — NGO operator JWT auth

**Files:**
- Create: `server/auth/__init__.py`, `server/auth/ngo.py`, `tests/test_auth_ngo.py`

- [ ] **Step 16.1 — Write failing tests**

`tests/test_auth_ngo.py`:
```python
import pytest

from server.auth.ngo import (
    InvalidTokenError,
    create_operator_token,
    hash_password,
    verify_operator_token,
    verify_password,
)


def test_password_hash_and_verify_round_trip():
    h = hash_password("hunter2")
    assert verify_password("hunter2", h)
    assert not verify_password("wrong", h)


def test_token_round_trip_returns_operator_id():
    token = create_operator_token(operator_id="op-1", ngo_id="N1")
    payload = verify_operator_token(token)
    assert payload["operator_id"] == "op-1"
    assert payload["ngo_id"] == "N1"


def test_invalid_token_raises():
    with pytest.raises(InvalidTokenError):
        verify_operator_token("not.a.token")
```

- [ ] **Step 16.2 — Run, expect failure**

Run: `uv run pytest tests/test_auth_ngo.py -v`
Expected: ImportError.

- [ ] **Step 16.3 — Implement**

`server/auth/__init__.py`:
```python
```

`server/auth/ngo.py`:
```python
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.hash import bcrypt

from server.config import get_settings


class InvalidTokenError(Exception):
    pass


def hash_password(plain: str) -> str:
    return bcrypt.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.verify(plain, hashed)


def create_operator_token(operator_id: str, ngo_id: str, ttl_minutes: int = 60 * 12) -> str:
    payload = {
        "operator_id": operator_id,
        "ngo_id": ngo_id,
        "iat": int(datetime.now(UTC).timestamp()),
        "exp": int((datetime.now(UTC) + timedelta(minutes=ttl_minutes)).timestamp()),
    }
    return jwt.encode(payload, get_settings().jwt_secret, algorithm="HS256")


def verify_operator_token(token: str) -> dict:
    try:
        return jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except JWTError as e:
        raise InvalidTokenError(str(e)) from e
```

- [ ] **Step 16.4 — Tests**

Run: `uv run pytest tests/test_auth_ngo.py -v`
Expected: 3 passed

- [ ] **Step 16.5 — Commit**

```bash
git add server/auth/ tests/test_auth_ngo.py
git commit -m "feat: NGO operator JWT auth with bcrypt password hash"
```

---

## Task 17 — End-to-end foundation smoke test

**Files:**
- Create: `tests/test_e2e_foundation.py`

- [ ] **Step 17.1 — Write the integration smoke test**

`tests/test_e2e_foundation.py`:
```python
"""End-to-end smoke test: verifies the entire foundation works as one piece."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text

from server.auth.ngo import create_operator_token, verify_operator_token
from server.db.alerts import Alert
from server.db.identity import NGO, Account
from server.db.messages import Bucket
from server.transports.sim_sms import SimSmsProvider


async def test_health_endpoint_responds(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "db": "ok"}


async def test_full_data_round_trip_through_test_db(db):
    # Insert an NGO, an alert, a recipient, and a synthetic bucket.
    ngo = NGO(name="Warchild", region_geohash_prefix="sv")
    db.add(ngo)
    await db.flush()

    acc = Account(
        phone="+972500000001",
        ngo_id=ngo.ngo_id,
        language="he",
        home_geohash="sv8d6q",
    )
    alert = Alert(
        ngo_id=ngo.ngo_id,
        person_name="Maya",
        last_seen_geohash="sv8d6",
        status="active",
        category="missing_child",
        urgency_tier="high",
        urgency_score=0.9,
        expires_at=datetime.now(UTC) + timedelta(days=2),
    )
    db.add_all([acc, alert])
    await db.flush()

    b = Bucket(
        bucket_key=f"{alert.alert_id}|sv8d|hb1",
        ngo_id=ngo.ngo_id,
        alert_id=alert.alert_id,
        geohash_prefix_4="sv8d",
        window_start=datetime.now(UTC),
    )
    db.add(b)
    await db.flush()

    # Hot-path index check: a prefix LIKE query for region recipients.
    rows = (
        await db.execute(
            select(Account).where(Account.home_geohash.like("sv8d%"))
        )
    ).scalars().all()
    assert len(rows) == 1


async def test_pgvector_query_runs(db):
    # Sanity: the pgvector cosine-distance operator is callable.
    result = (
        await db.execute(
            text("SELECT '[1,0,0]'::vector <=> '[0,1,0]'::vector AS d")
        )
    ).scalar()
    assert 0.0 < float(result) < 2.0


async def test_auth_token_round_trip():
    tok = create_operator_token(operator_id="op-1", ngo_id="ngo-x")
    payload = verify_operator_token(tok)
    assert payload["ngo_id"] == "ngo-x"


async def test_sim_sms_provider_records_send():
    sim = SimSmsProvider()
    r = await sim.send(to="+972500000099", body="ping", idempotency_key="i1")
    assert r.provider_msg_id.startswith("sim-")
    assert sim.sent[0].body == "ping"
```

- [ ] **Step 17.2 — Run the full test suite**

Run: `uv run pytest tests/ -v`
Expected: all tests pass. There should be roughly 20–25 tests across all files.

- [ ] **Step 17.3 — Update Dockerfile for the new deps**

The current `Dockerfile` was written for the dummy NGO Hub (`pip install fastapi uvicorn pydantic`). Replace the Python-stage `RUN pip install` line with one that installs from `pyproject.toml` plus the alembic migration entrypoint:

In `Dockerfile`, replace:
```dockerfile
RUN pip install --no-cache-dir "fastapi>=0.115" "uvicorn[standard]>=0.32" "pydantic>=2.9"
```
with:
```dockerfile
COPY pyproject.toml .
RUN pip install --no-cache-dir uv && uv sync --no-dev --frozen-lockfile || pip install --no-cache-dir .
```

Also append the alembic + db config copies before the `CMD`:
```dockerfile
COPY alembic.ini .
COPY alembic/ ./alembic/
COPY db/ ./db/
```

And update the port: `EXPOSE 8080` → `EXPOSE 8000` (or update compose to 8000:8000) — pick one and keep the README in sync.

Build to verify:
```bash
docker compose build app
```
Expected: build succeeds.

- [ ] **Step 17.4 — Boot smoke test**

Run:
```bash
docker compose up -d db
sleep 3
uv run alembic upgrade head
uv run uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
```

In another terminal:
```bash
curl -s localhost:8000/health
```
Expected output: `{"status":"ok","db":"ok"}`

Stop the server with Ctrl-C.

- [ ] **Step 17.5 — Verify schema completeness**

```bash
docker compose exec db psql -U app -d matching -c "\dt"
```
Expected output lists: `account`, `agent_decision`, `alembic_version`, `alert`, `alert_delivery`, `bad_actor`, `bucket`, `inbound_message`, `ngo`, `outbound_message`, `sighting`, `sighting_cluster`, `tag`, `tag_assignment`, `tool_call`, `trajectory`, `triaged_message` (17 tables including alembic_version).

```bash
docker compose exec db psql -U app -d matching -c "\di"
```
Expected: 21+ user indexes (PKs, uniques, plus our 21 hot-path indexes).

```bash
docker compose exec db psql -U app -d matching -c "\dx"
```
Expected output includes the `vector` extension.

- [ ] **Step 17.6 — Commit**

```bash
git add tests/test_e2e_foundation.py Dockerfile
git commit -m "test: end-to-end foundation smoke (db + auth + sim sms + pgvector)"
```

---

## Acceptance criteria for Plan 1

When all 17 tasks pass, the following must be true:

- [ ] `docker compose up -d db` brings up Postgres 16 with pgvector loaded.
- [ ] `uv run alembic upgrade head` creates all 16 application tables plus `alembic_version`.
- [ ] All 21 hot-path indexes exist (HNSW on three vector columns; partial on three queue tables; prefix LIKE on geohashes; B-tree composite on per-sender/per-recipient/per-alert lookups).
- [ ] `uv run uvicorn server.main:app` boots and `GET /health` returns `{"status":"ok","db":"ok"}`.
- [ ] `uv run pytest tests/ -v` passes ~25 tests covering: smoke import, DB connect + pgvector, /health, all model CRUD + uniqueness, hot-path indices presence, EventBus pub/sub round trip, SimSmsProvider send + idempotency, JWT auth round trip, end-to-end foundation.
- [ ] No code outside the spec's scope (no inbound webhook, no triage, no agent worker, no dispatcher, no console UI) — Plan 2 covers those.

---

## Self-review

**Spec coverage scan:**
- §3 Topology — partially covered (DB, FastAPI, SimSms; workers come in later plans). ✓ scoped correctly to Plan 1.
- §4.5 Data Tier — covered (Postgres + pgvector, alembic). ✓
- §6 Data model — all 16 tables + indices + Alert.category/urgency/score. ✓
- §8 EventBus — Postgres LISTEN/NOTIFY backend. ✓ (Redis backend deferred to prod; in-process asyncio backend not needed since we use Postgres NOTIFY directly.)
- §11 Adapter contracts — `SmsProvider` Protocol + `SimSmsProvider`. ✓ (`AppPusher` is implementation-only, deferred to Plan 4.)
- NGO operator auth — JWT round trip. ✓
- §13 Hackathon scope items 1, 2, 3 — covered.

**Placeholder scan:** No `TODO`, no `TBD`, every code block is complete.

**Type consistency:** Models cross-reference correctly:
- `Account.phone` PK is referenced by `InboundMessage.sender_phone` FK. ✓
- `NGO.ngo_id` referenced by every other table's `ngo_id` FK. ✓
- `Alert.alert_id` referenced by `AlertDelivery`, `Bucket`, `Sighting`, `SightingCluster`, `Trajectory`, `TagAssignment.alert_id`. ✓
- `Bucket.bucket_key` referenced by `AgentDecision.bucket_key` (UNIQUE). ✓
- `AgentDecision.decision_id` referenced by `ToolCall.decision_id`. ✓
- `ToolCall.idempotency_key` UNIQUE — enforced. ✓
- `ToolCall.call_id` self-referenced via `revised_from_call_id`. ✓
- `OutboundMessage.tool_call_id` references `ToolCall.call_id`. ✓
- `OutboundMessage.previous_out_id` self-references. ✓
- `SightingCluster.merged_into` self-references. ✓
- `Tag` UNIQUE(`ngo_id`, `namespace`, `name`). ✓
- `TagAssignment` UNIQUE(`tag_id`, `entity_type`, `entity_id`). ✓

**Scope check:** Plan 1 produces a working backend skeleton (boots, has schema, has auth, has sim transport) that Plan 2 can build the inbound pipeline onto. No blocking dependencies on later plans.

---

## What Plan 2 will build

- API tier inbound handlers: app WSS receive, sim SMS inbound hook (since the sim's inbound is in-process, it calls into an internal endpoint).
- `InboundMessage` write path with Twilio-style sender resolution.
- Triage worker: bare `anthropic` client, Haiku classification + structured output, `voyage-3-lite` embedding generation, bucket assignment with adaptive window, `BadActor` gate.
- `bucket_open` notification publish on each new bucket.
- Tests: send a message via app WS, verify `InboundMessage` written, verify `TriagedMessage` produced with embedding, verify `Bucket` created and `bucket_open` notified.
