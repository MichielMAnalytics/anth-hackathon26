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
