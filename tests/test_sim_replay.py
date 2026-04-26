"""Tests for the live replay drip endpoints.

We don't run the loop end-to-end (it would race with the triage worker in
the test app); instead we exercise:
  - status returns idle initially
  - start kicks off a task and returns running=true with intervalSec
  - start is idempotent (second call returns same state)
  - stop cancels the task
  - one tick of _fire_one inserts an InboundMessage and publishes new_inbound
"""
from __future__ import annotations

import pytest_asyncio
from sqlalchemy import delete, select

from server.db.alerts import Alert, AlertDelivery
from server.db.decisions import AgentDecision, ToolCall
from server.db.identity import NGO, Account
from server.db.knowledge import SightingCluster, Tag, TagAssignment, Trajectory
from server.db.messages import Bucket, InboundMessage, TriagedMessage
from server.db.outbound import OutboundMessage, Sighting
from server.db.trust import BadActor


_NGO_NAME = "Warchild"


async def _purge(test_session_maker) -> None:
    async with test_session_maker() as s:
        ngo_ids = (
            await s.execute(select(NGO.ngo_id).where(NGO.name == _NGO_NAME))
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
            await s.execute(select(ToolCall.call_id).where(ToolCall.ngo_id.in_(ngo_ids)))
        ).scalars().all()
        if tc_ids:
            await s.execute(
                delete(OutboundMessage).where(OutboundMessage.tool_call_id.in_(tc_ids))
            )
            await s.execute(delete(ToolCall).where(ToolCall.call_id.in_(tc_ids)))
        if decision_ids:
            await s.execute(
                delete(AgentDecision).where(AgentDecision.decision_id.in_(decision_ids))
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


@pytest_asyncio.fixture
async def seeded(client, test_session_maker):
    await _purge(test_session_maker)
    body = (await client.post("/api/sim/seed?reset=true")).json()
    yield body
    # Make sure we stop any running replay before purging.
    await client.post("/api/sim/replay/stop")
    await _purge(test_session_maker)


async def test_replay_status_initially_idle(client, seeded):
    # Stop in case a prior test session left a runner.
    await client.post("/api/sim/replay/stop")
    resp = await client.get("/api/sim/replay/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["running"] is False


async def test_replay_start_then_stop(client, seeded):
    r = await client.post("/api/sim/replay/start?intervalSec=2")
    assert r.status_code == 200
    body = r.json()
    assert body["running"] is True
    assert body["intervalSec"] == 2.0

    # Idempotent: a second start does not double-launch.
    r2 = await client.post("/api/sim/replay/start?intervalSec=2")
    assert r2.json()["running"] is True

    stop = await client.post("/api/sim/replay/stop")
    assert stop.status_code == 200
    assert stop.json()["running"] is False


async def test_fire_one_inserts_inbound(client, seeded, test_session_maker):
    """Direct unit test of _fire_one — avoids running the loop in pytest."""
    from server.db.engine import get_engine
    from server.eventbus.postgres import PostgresEventBus
    from server.sim.replay import _fire_one

    eventbus = PostgresEventBus(get_engine())
    desc = await _fire_one(test_session_maker, eventbus)
    assert desc is not None
    assert desc["msgId"]
    assert desc["alertId"]
    assert desc["body"]

    async with test_session_maker() as s:
        msg = await s.get(InboundMessage, desc["msgId"])
        assert msg is not None
        assert msg.in_reply_to_alert_id == desc["alertId"]
        assert msg.body == desc["body"]
        assert msg.raw == {"replay": True}
        assert msg.status == "new"
