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
