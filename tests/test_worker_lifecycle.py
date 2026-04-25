import pytest
from asgi_lifespan import LifespanManager
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

    async with LifespanManager(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/health")
            assert resp.status_code == 200
            assert main_module._worker_task is not None
            assert not main_module._worker_task.done()

    # After lifespan shutdown
    assert main_module._worker_task is None or main_module._worker_task.done()
