"""Tests for the rich /api/sim/seed endpoint.

Asserts that one call populates a multi-region scene (alerts across regions,
historic agent decisions, pending suggestions) and that subsequent calls are
idempotent (no duplicates) unless reset=True is passed.
"""
import pytest_asyncio
from sqlalchemy import delete, select

from server.db.alerts import Alert, AlertDelivery
from server.db.decisions import AgentDecision, ToolCall
from server.db.identity import NGO, Account
from server.db.knowledge import SightingCluster, Tag, TagAssignment, Trajectory
from server.db.messages import Bucket, InboundMessage, TriagedMessage
from server.db.outbound import OutboundMessage, Sighting
from server.db.trust import BadActor

_SEED_NGO_NAME = "Warchild"


async def _purge_warchild(test_session_maker) -> None:
    async with test_session_maker() as s:
        ngo_ids = (
            await s.execute(select(NGO.ngo_id).where(NGO.name == _SEED_NGO_NAME))
        ).scalars().all()
        if not ngo_ids:
            return
        alert_ids = (
            await s.execute(select(Alert.alert_id).where(Alert.ngo_id.in_(ngo_ids)))
        ).scalars().all()
        bucket_keys = (
            await s.execute(select(Bucket.bucket_key).where(Bucket.ngo_id.in_(ngo_ids)))
        ).scalars().all()
        decision_ids = (
            await s.execute(
                select(AgentDecision.decision_id).where(
                    AgentDecision.ngo_id.in_(ngo_ids)
                )
            )
        ).scalars().all()
        tc_ids = (
            await s.execute(
                select(ToolCall.call_id).where(ToolCall.ngo_id.in_(ngo_ids))
            )
        ).scalars().all()
        if tc_ids:
            await s.execute(
                delete(OutboundMessage).where(OutboundMessage.tool_call_id.in_(tc_ids))
            )
            await s.execute(delete(ToolCall).where(ToolCall.call_id.in_(tc_ids)))
        if decision_ids:
            await s.execute(
                delete(AgentDecision).where(
                    AgentDecision.decision_id.in_(decision_ids)
                )
            )
        if alert_ids:
            await s.execute(
                delete(TagAssignment).where(TagAssignment.alert_id.in_(alert_ids))
            )
            await s.execute(
                delete(SightingCluster).where(SightingCluster.alert_id.in_(alert_ids))
            )
            await s.execute(delete(Trajectory).where(Trajectory.alert_id.in_(alert_ids)))
            await s.execute(delete(Sighting).where(Sighting.alert_id.in_(alert_ids)))
        await s.execute(delete(Tag).where(Tag.ngo_id.in_(ngo_ids)))
        if alert_ids:
            msg_ids = (
                await s.execute(
                    select(InboundMessage.msg_id).where(
                        InboundMessage.in_reply_to_alert_id.in_(alert_ids)
                    )
                )
            ).scalars().all()
            if msg_ids:
                await s.execute(
                    delete(TriagedMessage).where(TriagedMessage.msg_id.in_(msg_ids))
                )
                await s.execute(
                    delete(InboundMessage).where(InboundMessage.msg_id.in_(msg_ids))
                )
        if bucket_keys:
            await s.execute(delete(Bucket).where(Bucket.bucket_key.in_(bucket_keys)))
        if alert_ids:
            await s.execute(
                delete(AlertDelivery).where(AlertDelivery.alert_id.in_(alert_ids))
            )
            await s.execute(delete(Alert).where(Alert.alert_id.in_(alert_ids)))
        await s.execute(delete(BadActor).where(BadActor.ngo_id.in_(ngo_ids)))
        await s.execute(delete(Account).where(Account.ngo_id.in_(ngo_ids)))
        await s.execute(delete(NGO).where(NGO.ngo_id.in_(ngo_ids)))
        await s.commit()


@pytest_asyncio.fixture(autouse=True)
async def _isolate_seed(test_session_maker):
    await _purge_warchild(test_session_maker)
    yield
    await _purge_warchild(test_session_maker)


async def test_seed_populates_rich_scene(client):
    resp = await client.post("/api/sim/seed")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    seeded = body["seeded"]

    assert seeded["accounts"] >= 25
    assert seeded["alerts"] >= 6
    assert seeded["inbound_messages"] >= 30
    assert seeded["sightings"] >= 16
    assert seeded["clusters"] >= 1
    assert seeded["trajectories"] >= 1
    assert seeded["agent_decisions"] >= 6
    assert seeded["pending_suggestions"] >= 3
    assert seeded["bad_actors"] >= 1


async def test_seed_is_idempotent(client, test_session_maker):
    r1 = await client.post("/api/sim/seed")
    r2 = await client.post("/api/sim/seed")
    assert r1.json()["ngo_id"] == r2.json()["ngo_id"]
    assert r2.json().get("alreadyExisted") is True
    async with test_session_maker() as s:
        ngos = (await s.execute(select(NGO).where(NGO.name == "Warchild"))).scalars().all()
        assert len(ngos) == 1


async def test_seed_reset_wipes_and_rebuilds(client, test_session_maker):
    r1 = await client.post("/api/sim/seed")
    first_ngo = r1.json()["ngo_id"]
    r2 = await client.post("/api/sim/seed?reset=true")
    second_ngo = r2.json()["ngo_id"]
    assert first_ngo != second_ngo, "reset must produce a fresh NGO"
    async with test_session_maker() as s:
        ngos = (await s.execute(select(NGO).where(NGO.name == "Warchild"))).scalars().all()
        assert len(ngos) == 1


async def test_seed_creates_pending_toolcalls_for_inbox(client, test_session_maker):
    body = (await client.post("/api/sim/seed")).json()
    ngo_id = body["ngo_id"]
    async with test_session_maker() as s:
        pending = (
            await s.execute(
                select(ToolCall).where(
                    ToolCall.ngo_id == ngo_id,
                    ToolCall.approval_status == "pending",
                )
            )
        ).scalars().all()
        assert len(pending) >= 3
        names = {tc.tool_name for tc in pending}
        assert "send" in names
