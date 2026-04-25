from httpx import ASGITransport, AsyncClient

from server.main import app


async def test_health_returns_ok():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"status": "ok", "db": "ok"}
