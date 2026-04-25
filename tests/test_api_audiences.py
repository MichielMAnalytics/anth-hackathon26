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
