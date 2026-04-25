from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.api.registry import REGIONS
from server.db.alerts import Alert, AlertDelivery
from server.db.base import generate_ulid
from server.db.engine import get_engine
from server.db.identity import NGO, Account
from server.db.messages import InboundMessage
from server.db.session import get_db
from server.eventbus.postgres import PostgresEventBus

router = APIRouter(prefix="/api/sim")

_REGION_PHONES = {
    "IRQ_BAGHDAD":  "+9647000000001",
    "IRQ_MOSUL":    "+9647000000002",
    "SYR_ALEPPO":   "+9639000000001",
    "SYR_DAMASCUS": "+9639000000002",
    "YEM_SANAA":    "+9677000000001",
    "LBN_BEIRUT":   "+9613000000001",
}

_SEED_BODIES = [
    "I saw a child matching the description near the old market",
    "There is a girl wandering alone on Al-Rashid street, looks scared",
    "Someone reported a missing child near the checkpoint, please help",
    "I think I saw her near the river bridge about an hour ago",
]


@router.post("/seed")
async def seed(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    existing = (
        await db.execute(select(NGO).where(NGO.name == "Warchild"))
    ).scalar_one_or_none()
    if existing is not None:
        existing_alert = (
            await db.execute(select(Alert).where(Alert.ngo_id == existing.ngo_id).limit(1))
        ).scalar_one_or_none()
        accounts = (
            await db.execute(select(Account).where(Account.ngo_id == existing.ngo_id))
        ).scalars().all()
        deliveries = []
        msgs = []
        if existing_alert:
            deliveries = (
                await db.execute(
                    select(AlertDelivery).where(AlertDelivery.alert_id == existing_alert.alert_id)
                )
            ).scalars().all()
            msgs = (
                await db.execute(
                    select(InboundMessage).where(
                        InboundMessage.in_reply_to_alert_id == existing_alert.alert_id
                    )
                )
            ).scalars().all()
        return {
            "ok": True,
            "ngo_id": existing.ngo_id,
            "alert_id": existing_alert.alert_id if existing_alert else "",
            "seeded": {
                "accounts": len(accounts),
                "alert_deliveries": len(deliveries),
                "inbound_messages": len(msgs),
            },
        }

    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()

    accounts: list[Account] = []
    for region_key, phone in _REGION_PHONES.items():
        meta = REGIONS[region_key]
        prefix = meta["geohash_prefix"]
        acc = Account(
            phone=phone,
            ngo_id=ngo.ngo_id,
            language="ar",
            last_known_geohash=prefix + "u0",
            source="app",
        )
        db.add(acc)
        accounts.append(acc)
    await db.flush()

    baghdad = REGIONS["IRQ_BAGHDAD"]
    alert = Alert(
        ngo_id=ngo.ngo_id,
        person_name="Amira Hassan",
        description="8-year-old girl, last seen near Al-Shorja market wearing a red dress",
        last_seen_geohash=baghdad["geohash_prefix"] + "u0",
        region_geohash_prefix=baghdad["geohash_prefix"],
        status="active",
        category="missing_person",
        urgency_tier="high",
        urgency_score=0.9,
        expires_at=datetime.now(UTC) + timedelta(days=3),
    )
    db.add(alert)
    await db.flush()

    deliveries: list[AlertDelivery] = []
    for acc in accounts:
        d = AlertDelivery(
            ngo_id=ngo.ngo_id, alert_id=alert.alert_id, recipient_phone=acc.phone
        )
        db.add(d)
        deliveries.append(d)
    await db.flush()

    baghdad_phone = _REGION_PHONES["IRQ_BAGHDAD"]
    msgs: list[InboundMessage] = []
    for body in _SEED_BODIES:
        m = InboundMessage(
            ngo_id=ngo.ngo_id,
            channel="sms",
            sender_phone=baghdad_phone,
            in_reply_to_alert_id=alert.alert_id,
            body=body,
            media_urls=[],
            raw={"seeded": True},
        )
        db.add(m)
        msgs.append(m)
    await db.commit()

    return {
        "ok": True,
        "ngo_id": ngo.ngo_id,
        "alert_id": alert.alert_id,
        "seeded": {
            "accounts": len(accounts),
            "alert_deliveries": len(deliveries),
            "inbound_messages": len(msgs),
        },
    }


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
