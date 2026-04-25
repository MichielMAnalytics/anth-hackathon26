"""One-shot smoke test for the real-LLM agent path.

Seeds an alert + bucket + triaged sighting message, then runs ONE decision
via a real ClaudeSDKClient connected to Anthropic's API. Prints the resulting
AgentDecision (model, summary, tool calls) and exits.

Usage:
    ANTHROPIC_API_KEY=... uv run python scripts/smoke_real_agent.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from server.config import get_settings
from server.db.alerts import Alert
from server.db.decisions import AgentDecision, ToolCall
from server.db.identity import NGO, Account
from server.db.messages import Bucket, InboundMessage, TriagedMessage
from server.db.outbound import Sighting
from server.eventbus.postgres import PostgresEventBus
from server.workers.agent import _handle_one_bucket
from server.llm.agent_client import make_agent_options


PHONE = "+972500000777"
NGO_NAME = "RealSmokeNGO"


async def purge(sm) -> None:
    async with sm() as s:
        ngo_ids = (
            await s.execute(select(NGO.ngo_id).where(NGO.name == NGO_NAME))
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
            await s.execute(delete(Account).where(Account.phone == PHONE))
            await s.execute(delete(NGO).where(NGO.ngo_id.in_(ngo_ids)))
        await s.commit()


async def seed(sm) -> dict:
    async with sm() as s:
        ngo = NGO(name=NGO_NAME)
        s.add(ngo)
        await s.flush()
        s.add(Account(phone=PHONE, ngo_id=ngo.ngo_id, language="en"))
        alert = Alert(
            ngo_id=ngo.ngo_id,
            person_name="Tamar",
            description="Missing girl, last seen near old market wearing red jacket",
            status="active",
            last_seen_geohash="sv8d6f",
        )
        s.add(alert)
        await s.flush()
        msg = InboundMessage(
            ngo_id=ngo.ngo_id,
            channel="app",
            sender_phone=PHONE,
            in_reply_to_alert_id=alert.alert_id,
            body="I just saw a girl in red walking south near the bakery on Hahalutz street",
            media_urls=[],
            raw={},
            status="triaged",
        )
        s.add(msg)
        await s.flush()
        bucket_key = f"{alert.alert_id}|sv8d|{datetime.now(UTC).isoformat()}"
        s.add(
            Bucket(
                bucket_key=bucket_key,
                ngo_id=ngo.ngo_id,
                alert_id=alert.alert_id,
                geohash_prefix_4="sv8d",
                window_start=datetime.now(UTC),
                window_length_ms=3000,
                status="open",
            )
        )
        s.add(
            TriagedMessage(
                msg_id=msg.msg_id,
                ngo_id=ngo.ngo_id,
                classification="sighting",
                geohash6="sv8d6f",
                geohash_source="body_extraction",
                confidence=0.82,
                language="en",
                bucket_key=bucket_key,
            )
        )
        await s.commit()
        return {"bucket_key": bucket_key, "alert_id": alert.alert_id, "ngo_id": ngo.ngo_id}


async def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        print("ANTHROPIC_API_KEY not set; aborting", file=sys.stderr)
        return 1

    settings = get_settings()
    engine = create_async_engine(settings.test_database_url, future=True)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    bus = PostgresEventBus(engine)

    await purge(sm)
    seeded = await seed(sm)
    print(f"Seeded bucket={seeded['bucket_key']}")

    from claude_agent_sdk import ClaudeSDKClient

    client = ClaudeSDKClient(options=make_agent_options())
    await client.connect()
    print("ClaudeSDKClient connected. Running decision...")

    try:
        async with sm() as s:
            bucket = await s.get(Bucket, seeded["bucket_key"])

        await _handle_one_bucket(bucket, sm, bus, client)

        async with sm() as s:
            decision = (
                await s.execute(
                    select(AgentDecision).where(
                        AgentDecision.bucket_key == seeded["bucket_key"]
                    )
                )
            ).scalars().first()
            calls = (
                await s.execute(
                    select(ToolCall).where(ToolCall.decision_id == decision.decision_id)
                )
            ).scalars().all() if decision else []

        if decision is None:
            print("No AgentDecision was written.")
            return 2

        print("\n=== AgentDecision ===")
        print(f"  model:    {decision.model}")
        print(f"  turns:    {decision.total_turns}")
        print(f"  latency:  {decision.latency_ms} ms")
        print(f"  cost:     ${decision.cost_usd:.4f}")
        print(f"  summary:  {(decision.reasoning_summary or '')[:300]}")
        print(f"\n=== ToolCalls ({len(calls)}) ===")
        for c in calls:
            print(f"  {c.tool_name} mode={c.mode} approval={c.approval_status}")
            print(f"    args: {str(c.args)[:240]}")

        return 0
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
