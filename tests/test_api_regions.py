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
