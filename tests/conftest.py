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
