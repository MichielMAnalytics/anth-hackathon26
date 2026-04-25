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


from datetime import UTC, datetime, timedelta

from sqlalchemy import delete as sa_delete

from server.db.alerts import Alert
from server.db.identity import NGO
from server.db.messages import Bucket


async def _purge_sv8d_buckets(db) -> None:
    """Delete all sv8d Bucket rows so timeline tests start from a clean slate."""
    await db.execute(sa_delete(Bucket).where(Bucket.geohash_prefix_4 == "sv8d"))
    await db.commit()


async def test_timeline_empty_returns_zero_buckets(client, db):
    await _purge_sv8d_buckets(db)
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
    await _purge_sv8d_buckets(db)
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

    # clean up committed data so other tests see a clean slate
    await _purge_sv8d_buckets(db)


async def test_timeline_unknown_region_returns_404(client):
    resp = await client.get(
        "/api/regions/NOWHERE/timeline",
        headers={"X-Operator-Id": "op-senior"},
    )
    assert resp.status_code == 404


async def test_timeline_requires_auth(client):
    resp = await client.get("/api/regions/IRQ_BAGHDAD/timeline")
    assert resp.status_code == 401
