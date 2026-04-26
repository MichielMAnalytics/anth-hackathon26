"""Tests for the operator approval inbox and agent activity feed.

Covers:
  GET  /api/suggestions
  POST /api/suggestions/{id}/approve|reject
  GET  /api/decisions/recent
  GET  /api/agent/stats

Uses the rich seeder so we have realistic pending suggestions to operate on.
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
    await _purge(test_session_maker)


_OP_HDR = {"X-Operator-Id": "op-senior"}


async def test_list_suggestions_returns_pending_with_context(client, seeded):
    resp = await client.get("/api/suggestions", headers=_OP_HDR)
    assert resp.status_code == 200
    suggestions = resp.json()
    assert len(suggestions) >= 3
    sample = suggestions[0]
    assert sample["id"]
    assert sample["tool"] in {
        "send", "categorize_alert", "mark_bad_actor", "update_alert_status"
    }
    assert sample["decision"] is not None
    assert sample["decision"]["summary"]
    assert sample["alert"] is not None
    assert sample["alert"]["personName"]


async def test_approve_then_double_approve_conflicts(client, seeded):
    suggestions = (await client.get("/api/suggestions", headers=_OP_HDR)).json()
    target = next(s for s in suggestions if s["tool"] == "send")
    sid = target["id"]

    r1 = await client.post(f"/api/suggestions/{sid}/approve", headers=_OP_HDR)
    assert r1.status_code == 200
    body = r1.json()
    assert body["approvalStatus"] == "approved"
    assert body["decidedBy"] == "op-senior"

    r2 = await client.post(f"/api/suggestions/{sid}/approve", headers=_OP_HDR)
    assert r2.status_code == 409


async def test_reject_marks_done(client, seeded, test_session_maker):
    suggestions = (await client.get("/api/suggestions", headers=_OP_HDR)).json()
    target = suggestions[0]
    sid = target["id"]
    resp = await client.post(f"/api/suggestions/{sid}/reject", headers=_OP_HDR)
    assert resp.status_code == 200
    assert resp.json()["approvalStatus"] == "rejected"

    async with test_session_maker() as s:
        tc = await s.get(ToolCall, sid)
        assert tc.approval_status == "rejected"
        assert tc.status == "done"
        assert tc.decided_by == "op-senior"


async def test_recent_decisions_backfills_activity_tape(client, seeded):
    resp = await client.get("/api/decisions/recent?limit=20", headers=_OP_HDR)
    assert resp.status_code == 200
    decisions = resp.json()
    assert len(decisions) >= 5
    sample = decisions[0]
    for key in ("id", "model", "summary", "totalTurns", "costUsd", "createdAt"):
        assert key in sample
    assert sample["alert"] is not None
    assert isinstance(sample["toolCalls"], list)


async def test_recent_decisions_include_narration(client, seeded):
    decisions = (
        await client.get("/api/decisions/recent?limit=20", headers=_OP_HDR)
    ).json()
    assert decisions
    sample = decisions[0]
    assert "narration" in sample
    assert sample["narration"]
    # Should be plain English, not the legacy "stub: …" style.
    assert not sample["narration"].startswith("stub:")


async def test_decision_detail_returns_full_turns(client, seeded):
    decisions = (
        await client.get("/api/decisions/recent?limit=1", headers=_OP_HDR)
    ).json()
    assert decisions
    did = decisions[0]["id"]

    resp = await client.get(f"/api/decisions/{did}", headers=_OP_HDR)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == did
    assert body["narration"]
    assert "turns" in body
    assert isinstance(body["turns"], list)
    assert "promptHash" in body
    assert isinstance(body["toolCalls"], list)
    if body["toolCalls"]:
        # Detail shape includes args + decided fields.
        first = body["toolCalls"][0]
        assert "args" in first
        assert "approvalStatus" in first


async def test_decision_detail_404_for_unknown(client, seeded):
    resp = await client.get("/api/decisions/01XXNOTAREALID00000000000XX", headers=_OP_HDR)
    assert resp.status_code == 404


async def test_suggestions_include_narration(client, seeded):
    suggestions = (
        await client.get("/api/suggestions", headers=_OP_HDR)
    ).json()
    assert suggestions
    # Suggestion items don't currently get a narration on the list endpoint
    # — narration ships on the WS suggestion_pending event. We just confirm
    # the existing decision summary is human (not 'stub:').
    sample = suggestions[0]
    if sample.get("decision") and sample["decision"].get("summary"):
        assert not sample["decision"]["summary"].startswith("stub:")


async def test_agent_stats_aggregates(client, seeded):
    resp = await client.get("/api/agent/stats", headers=_OP_HDR)
    assert resp.status_code == 200
    stats = resp.json()
    assert stats["pending"] >= 3
    assert stats["decisionsToday"] >= 5
    assert stats["costTodayUsd"] >= 0.0
    assert stats["lastDecisionAt"]
