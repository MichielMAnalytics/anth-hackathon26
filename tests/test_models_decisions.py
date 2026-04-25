import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from server.db.alerts import Alert
from server.db.decisions import AgentDecision, ToolCall
from server.db.identity import NGO


async def _seed_bucket(db):
    from datetime import UTC, datetime
    from server.db.messages import Bucket

    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()
    alert = Alert(ngo_id=ngo.ngo_id, person_name="Maya", status="active")
    db.add(alert)
    await db.flush()
    b = Bucket(
        bucket_key=f"{alert.alert_id}|sv8d|2026-04-25T10",
        ngo_id=ngo.ngo_id,
        alert_id=alert.alert_id,
        geohash_prefix_4="sv8d",
        window_start=datetime.now(UTC),
    )
    db.add(b)
    await db.flush()
    return ngo, alert, b


async def test_agent_decision_unique_per_bucket(db):
    ngo, alert, b = await _seed_bucket(db)
    d1 = AgentDecision(
        ngo_id=ngo.ngo_id,
        bucket_key=b.bucket_key,
        model="claude-sonnet-4-6",
        prompt_hash="abc",
        reasoning_summary="ok",
        tool_calls=[],
        turns=[],
        total_turns=1,
        latency_ms=1500,
        cost_usd=0.04,
    )
    db.add(d1)
    await db.flush()

    d2 = AgentDecision(
        ngo_id=ngo.ngo_id,
        bucket_key=b.bucket_key,
        model="claude-sonnet-4-6",
        prompt_hash="abc",
        reasoning_summary="dup",
        tool_calls=[],
        turns=[],
        total_turns=1,
        latency_ms=1500,
        cost_usd=0.04,
    )
    db.add(d2)
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_tool_call_idempotency_key_unique(db):
    ngo, alert, b = await _seed_bucket(db)
    d = AgentDecision(
        ngo_id=ngo.ngo_id,
        bucket_key=b.bucket_key,
        model="claude-sonnet-4-6",
        prompt_hash="abc",
        reasoning_summary="ok",
        tool_calls=[],
        turns=[],
        total_turns=1,
        latency_ms=1500,
        cost_usd=0.04,
    )
    db.add(d)
    await db.flush()

    tc1 = ToolCall(
        ngo_id=ngo.ngo_id,
        decision_id=d.decision_id,
        tool_name="send",
        args={"a": 1},
        idempotency_key="key-123",
        mode="execute",
        approval_status="auto_executed",
    )
    db.add(tc1)
    await db.flush()

    tc2 = ToolCall(
        ngo_id=ngo.ngo_id,
        decision_id=d.decision_id,
        tool_name="send",
        args={"a": 1},
        idempotency_key="key-123",
        mode="execute",
        approval_status="auto_executed",
    )
    db.add(tc2)
    with pytest.raises(IntegrityError):
        await db.flush()
