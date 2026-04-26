"""Live replay drip — fires one varied InboundMessage every N seconds.

Used to make the demo dashboard breathe: the activity tape gets a fresh
agent decision every cycle, the header pill ticks up, region cards glow.

A single background task runs at a time. POST /api/sim/replay/start
ensures one is running; /stop cancels it; /status returns its state.
"""
from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from server.api.registry import REGIONS
from server.db.alerts import Alert
from server.db.base import generate_ulid
from server.db.identity import Account
from server.db.messages import InboundMessage
from server.eventbus.postgres import PostgresEventBus

logger = logging.getLogger(__name__)


# Message templates by alert category. Keep these short and varied so
# the activity tape reads naturally to a viewer.
_BODIES_BY_CATEGORY: dict[str, list[str]] = {
    "missing_person": [
        "Just saw a child matching the description near the bakery, walking south",
        "I think she's by the old market, sitting on the steps",
        "Witness reports child in a red dress at the bus stop",
        "Two of us spotted her near the river crossing about 10 minutes ago",
        "She might be near the pharmacy on the main street",
        "Found a child wandering alone, looks scared, near the park",
        "Searched our street, no sign of her yet",
        "Heard a child crying near the mosque, going to check",
    ],
    "medical": [
        "I have a pack of insulin pens, can deliver in 20 minutes",
        "Pharmacy on the corner is open and has stock",
        "We have a working generator, can share fuel for 2 hours",
        "Ambulance arriving in 15 minutes, hold the line",
        "Doctor available at the clinic on the main road",
    ],
    "safety": [
        "Hearing voices from under the rubble in the south corner",
        "Need more excavation tools, two more families are trapped",
        "Civil defense is on site, requesting backup teams",
        "Pulled a child out, alive, sending to hospital now",
        "South wall is unstable, all rescuers should evacuate",
    ],
    "resource_shortage": [
        "When will the water tankers arrive?",
        "Tanker just arrived but it only covers 20 households",
        "Municipality says repairs will take another 6 hours",
        "We have bottled water to spare for elderly neighbors",
    ],
}

_DEFAULT_BODIES = [
    "Update from the field — situation evolving",
    "We're on it, will report back",
    "No new information at this moment",
]


@dataclass
class ReplayState:
    task: Optional[asyncio.Task] = None
    started_at: Optional[datetime] = None
    interval_sec: float = 6.0
    fired: int = 0
    last_fired_at: Optional[datetime] = None
    last_body: Optional[str] = None
    last_alert_id: Optional[str] = None
    history: list[dict] = field(default_factory=list)


_STATE = ReplayState()


def get_state() -> ReplayState:
    return _STATE


def _pick_body(category: Optional[str]) -> str:
    pool = _BODIES_BY_CATEGORY.get(category or "", _DEFAULT_BODIES)
    return random.choice(pool)


async def _fire_one(
    session_maker: async_sessionmaker,
    eventbus: PostgresEventBus,
) -> Optional[dict]:
    """Pick an active alert + a sender + a body, insert InboundMessage,
    publish new_inbound. Returns a small descriptor for the history log."""
    async with session_maker() as s:
        alerts = (
            await s.execute(select(Alert).where(Alert.status == "active"))
        ).scalars().all()
        if not alerts:
            return None
        alert = random.choice(alerts)

        # Pick a sender phone in the alert's region (best effort).
        region_prefix = alert.region_geohash_prefix
        accounts: list[Account] = []
        if region_prefix:
            accounts = (
                await s.execute(
                    select(Account)
                    .where(Account.ngo_id == alert.ngo_id)
                    .where(Account.last_known_geohash.like(f"{region_prefix}%"))
                    .limit(20)
                )
            ).scalars().all()
        if not accounts:
            accounts = (
                await s.execute(
                    select(Account)
                    .where(Account.ngo_id == alert.ngo_id)
                    .limit(20)
                )
            ).scalars().all()
        if not accounts:
            return None

        sender = random.choice(accounts)
        body = _pick_body(alert.category)

        msg_id = generate_ulid()
        msg = InboundMessage(
            msg_id=msg_id,
            ngo_id=alert.ngo_id,
            channel=random.choice(("app", "sms")),
            sender_phone=sender.phone,
            in_reply_to_alert_id=alert.alert_id,
            body=body,
            media_urls=[],
            raw={"replay": True},
            received_at=datetime.now(UTC),
            status="new",
        )
        s.add(msg)
        await s.commit()

    await eventbus.publish("new_inbound", msg_id)

    return {
        "msgId": msg_id,
        "alertId": alert.alert_id,
        "personName": alert.person_name,
        "category": alert.category,
        "body": body,
        "ts": datetime.now(UTC).isoformat(),
    }


async def _replay_loop(
    session_maker: async_sessionmaker,
    eventbus: PostgresEventBus,
    interval_sec: float,
) -> None:
    """Background loop. Runs until cancelled."""
    state = _STATE
    state.started_at = datetime.now(UTC)
    state.interval_sec = interval_sec
    state.fired = 0
    try:
        while True:
            try:
                desc = await _fire_one(session_maker, eventbus)
                if desc is not None:
                    state.fired += 1
                    state.last_fired_at = datetime.now(UTC)
                    state.last_body = desc["body"]
                    state.last_alert_id = desc["alertId"]
                    state.history.append(desc)
                    state.history = state.history[-20:]
            except Exception as exc:  # noqa: BLE001
                logger.warning("replay: fire failed: %s", exc)
            await asyncio.sleep(interval_sec)
    except asyncio.CancelledError:
        raise


def start_replay(
    session_maker: async_sessionmaker,
    eventbus: PostgresEventBus,
    interval_sec: float = 6.0,
) -> dict:
    """Idempotent: returns current state if a task is already running."""
    state = _STATE
    if state.task is not None and not state.task.done():
        return status()
    state.task = asyncio.create_task(
        _replay_loop(session_maker, eventbus, interval_sec),
        name="sim-replay",
    )
    state.interval_sec = interval_sec
    state.started_at = datetime.now(UTC)
    state.fired = 0
    state.history.clear()
    return status()


async def stop_replay() -> dict:
    state = _STATE
    if state.task is None or state.task.done():
        return status()
    state.task.cancel()
    try:
        await asyncio.wait_for(state.task, timeout=2.0)
    except (asyncio.CancelledError, asyncio.TimeoutError):
        pass
    state.task = None
    return status()


def status() -> dict:
    state = _STATE
    running = state.task is not None and not state.task.done()
    return {
        "running": running,
        "intervalSec": state.interval_sec,
        "startedAt": state.started_at.isoformat() if state.started_at else None,
        "lastFiredAt": state.last_fired_at.isoformat() if state.last_fired_at else None,
        "fired": state.fired,
        "lastAlertId": state.last_alert_id,
        "lastBody": state.last_body,
        "recent": list(reversed(state.history[-10:])),
    }
