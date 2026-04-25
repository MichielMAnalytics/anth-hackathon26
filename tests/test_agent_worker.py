"""Stub-mode unit test for the Agent Worker.

Seeds an NGO + Account + Alert + Bucket + TriagedMessage, then drives the
agent through one decision and verifies an `AgentDecision` row + at least
one `ToolCall` row are written, with execute-mode side-effects applied
(Sighting row created when a sighting message is in the bucket).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select

from server.db.alerts import Alert
from server.db.decisions import AgentDecision, ToolCall
from server.db.identity import NGO, Account
from server.db.messages import Bucket, InboundMessage, TriagedMessage
from server.db.outbound import Sighting
from server.eventbus.postgres import PostgresEventBus
from server.workers.agent import _handle_one_bucket
from server.workers.agent_context import load_context


_PHONE = "+972500009912"
_NGO_NAME = "AgentTestNGO"


@pytest.fixture(autouse=True)
def stub_llm(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")


async def _purge(session_maker) -> None:
    async with session_maker() as s:
        ngo_ids = (
            await s.execute(select(NGO.ngo_id).where(NGO.name == _NGO_NAME))
        ).scalars().all()
        if ngo_ids:
            alert_ids = (
                await s.execute(select(Alert.alert_id).where(Alert.ngo_id.in_(ngo_ids)))
            ).scalars().all()
            if alert_ids:
                bucket_keys = (
                    await s.execute(
                        select(Bucket.bucket_key).where(Bucket.alert_id.in_(alert_ids))
                    )
                ).scalars().all()
                if bucket_keys:
                    decision_ids = (
                        await s.execute(
                            select(AgentDecision.decision_id).where(
                                AgentDecision.bucket_key.in_(bucket_keys)
                            )
                        )
                    ).scalars().all()
                    if decision_ids:
                        await s.execute(
                            delete(ToolCall).where(
                                ToolCall.decision_id.in_(decision_ids)
                            )
                        )
                        await s.execute(
                            delete(AgentDecision).where(
                                AgentDecision.decision_id.in_(decision_ids)
                            )
                        )
                await s.execute(delete(Sighting).where(Sighting.alert_id.in_(alert_ids)))
                await s.execute(delete(Bucket).where(Bucket.alert_id.in_(alert_ids)))
                await s.execute(
                    delete(TriagedMessage).where(
                        TriagedMessage.bucket_key.in_(bucket_keys or [""])
                    )
                )
                await s.execute(
                    delete(InboundMessage).where(
                        InboundMessage.in_reply_to_alert_id.in_(alert_ids)
                    )
                )
                await s.execute(delete(Alert).where(Alert.alert_id.in_(alert_ids)))
            await s.execute(delete(Account).where(Account.phone == _PHONE))
            await s.execute(delete(NGO).where(NGO.ngo_id.in_(ngo_ids)))
        await s.commit()


@pytest.fixture
async def seeded(test_session_maker):
    await _purge(test_session_maker)
    async with test_session_maker() as s:
        ngo = NGO(name=_NGO_NAME)
        s.add(ngo)
        await s.flush()
        acc = Account(phone=_PHONE, ngo_id=ngo.ngo_id)
        alert = Alert(
            ngo_id=ngo.ngo_id,
            person_name="Tamar",
            description="Missing girl, last seen near old market",
            status="active",
            last_seen_geohash="sv8d6f",
        )
        s.add_all([acc, alert])
        await s.flush()
        msg = InboundMessage(
            ngo_id=ngo.ngo_id,
            channel="app",
            sender_phone=_PHONE,
            in_reply_to_alert_id=alert.alert_id,
            body="saw a girl in red walking south near bakery",
            media_urls=[],
            raw={},
            status="triaged",
        )
        s.add(msg)
        await s.flush()
        bucket_key = f"{alert.alert_id}|sv8d|{datetime.now(UTC).isoformat()}"
        bucket = Bucket(
            bucket_key=bucket_key,
            ngo_id=ngo.ngo_id,
            alert_id=alert.alert_id,
            geohash_prefix_4="sv8d",
            window_start=datetime.now(UTC),
            window_length_ms=3000,
            status="open",
        )
        s.add(bucket)
        triaged = TriagedMessage(
            msg_id=msg.msg_id,
            ngo_id=ngo.ngo_id,
            classification="sighting",
            geohash6="sv8d6f",
            geohash_source="body_extraction",
            confidence=0.78,
            language="en",
            bucket_key=bucket_key,
        )
        s.add(triaged)
        await s.commit()
        yield {
            "ngo_id": ngo.ngo_id,
            "alert_id": alert.alert_id,
            "bucket_key": bucket_key,
            "msg_id": msg.msg_id,
        }
    await _purge(test_session_maker)


async def test_stub_agent_writes_decision_and_toolcalls(test_engine, test_session_maker, seeded):
    bucket_key = seeded["bucket_key"]

    bus = PostgresEventBus(test_engine)
    async with test_session_maker() as s:
        bucket = await s.get(Bucket, bucket_key)
        assert bucket is not None

    # Drive one decision pass directly (no eventbus subscribe).
    await _handle_one_bucket(bucket, test_session_maker, bus, sdk_client=None)

    async with test_session_maker() as s:
        decision = (
            await s.execute(
                select(AgentDecision).where(AgentDecision.bucket_key == bucket_key)
            )
        ).scalars().first()
        assert decision is not None
        assert decision.model == "stub"
        assert decision.tool_calls

        calls = (
            await s.execute(
                select(ToolCall).where(ToolCall.decision_id == decision.decision_id)
            )
        ).scalars().all()
        assert len(calls) >= 1
        call_names = {c.tool_name for c in calls}
        assert "record_sighting" in call_names
        assert "send" in call_names

        sightings = (
            await s.execute(select(Sighting).where(Sighting.alert_id == seeded["alert_id"]))
        ).scalars().all()
        assert len(sightings) == 1
        assert sightings[0].observer_phone == _PHONE

        refreshed_bucket = await s.get(Bucket, bucket_key)
        assert refreshed_bucket.status == "done"


async def test_stub_agent_emits_noop_for_empty_bucket(test_session_maker, test_engine):
    """Heartbeat-style bucket with no triaged messages → noop tool call."""
    # Use a unique NGO for this test.
    name = "AgentTestNGO_HB"
    async with test_session_maker() as s:
        ngo = NGO(name=name)
        s.add(ngo)
        await s.flush()
        alert = Alert(
            ngo_id=ngo.ngo_id, person_name="HeartbeatPerson", status="active"
        )
        s.add(alert)
        await s.flush()
        bucket_key = f"heartbeat:{alert.alert_id}:{datetime.now(UTC).isoformat()}"
        bucket = Bucket(
            bucket_key=bucket_key,
            ngo_id=ngo.ngo_id,
            alert_id=alert.alert_id,
            geohash_prefix_4=None,
            window_start=datetime.now(UTC),
            window_length_ms=0,
            status="open",
        )
        s.add(bucket)
        await s.commit()
        ngo_id = ngo.ngo_id
        alert_id = alert.alert_id

    try:
        bus = PostgresEventBus(test_engine)
        async with test_session_maker() as s:
            bucket = await s.get(Bucket, bucket_key)
        await _handle_one_bucket(bucket, test_session_maker, bus, sdk_client=None)

        async with test_session_maker() as s:
            decision = (
                await s.execute(
                    select(AgentDecision).where(AgentDecision.bucket_key == bucket_key)
                )
            ).scalars().first()
            assert decision is not None
            calls = (
                await s.execute(
                    select(ToolCall).where(ToolCall.decision_id == decision.decision_id)
                )
            ).scalars().all()
            assert any(c.tool_name == "noop" for c in calls)
    finally:
        async with test_session_maker() as s:
            decision_ids = (
                await s.execute(
                    select(AgentDecision.decision_id).where(
                        AgentDecision.bucket_key == bucket_key
                    )
                )
            ).scalars().all()
            if decision_ids:
                await s.execute(
                    delete(ToolCall).where(ToolCall.decision_id.in_(decision_ids))
                )
                await s.execute(
                    delete(AgentDecision).where(
                        AgentDecision.decision_id.in_(decision_ids)
                    )
                )
            await s.execute(delete(Bucket).where(Bucket.bucket_key == bucket_key))
            await s.execute(delete(Alert).where(Alert.alert_id == alert_id))
            await s.execute(delete(NGO).where(NGO.ngo_id == ngo_id))
            await s.commit()
