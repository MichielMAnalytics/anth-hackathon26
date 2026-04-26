from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.db.base import generate_ulid
from server.db.engine import get_engine, get_session_maker
from server.db.identity import NGO
from server.db.messages import InboundMessage
from server.db.session import get_db
from server.eventbus.postgres import PostgresEventBus
from server.sim import replay as replay_mod
from server.sim.seeder import seed_rich

router = APIRouter(prefix="/api/sim")


@router.post("/seed")
async def seed(
    reset: bool = Query(default=False, description="Wipe Warchild and re-seed"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Populate the demo scene. Idempotent; pass ?reset=true to rebuild."""
    return await seed_rich(db, reset=reset)


@router.post("/replay/start")
async def replay_start(
    interval_sec: float = Query(default=6.0, ge=1.0, le=60.0, alias="intervalSec"),
) -> dict[str, Any]:
    """Start firing one inbound message every intervalSec seconds."""
    eventbus = PostgresEventBus(get_engine())
    sm = get_session_maker()
    return replay_mod.start_replay(sm, eventbus, interval_sec=interval_sec)


@router.post("/replay/stop")
async def replay_stop() -> dict[str, Any]:
    return await replay_mod.stop_replay()


@router.get("/replay/status")
async def replay_status() -> dict[str, Any]:
    return replay_mod.status()


class InboundEnvelope(BaseModel):
    channel: str
    sender_phone: str
    in_reply_to_alert_id: Optional[str] = None
    body: str
    media_urls: list[str] = []
    raw: dict = {}


@router.post("/inbound", status_code=202)
async def sim_inbound(
    envelope: InboundEnvelope,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    ngos = (await db.execute(select(NGO))).scalars().all()
    if len(ngos) != 1:
        raise HTTPException(
            status_code=503,
            detail=f"Expected exactly 1 NGO, found {len(ngos)}. Seed the DB first.",
        )
    ngo = ngos[0]

    msg_id = generate_ulid()
    msg = InboundMessage(
        msg_id=msg_id,
        ngo_id=ngo.ngo_id,
        channel=envelope.channel,
        sender_phone=envelope.sender_phone,
        in_reply_to_alert_id=envelope.in_reply_to_alert_id,
        body=envelope.body,
        media_urls=envelope.media_urls,
        raw=envelope.raw,
        received_at=datetime.now(UTC),
        status="new",
    )
    db.add(msg)
    await db.commit()

    bus = PostgresEventBus(get_engine())
    await bus.publish("new_inbound", msg_id)

    return {"msg_id": msg_id, "status": "new"}
