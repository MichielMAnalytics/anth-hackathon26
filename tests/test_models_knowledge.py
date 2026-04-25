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
