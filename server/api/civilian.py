"""Civilian-facing API tier — the endpoints the SafeThread iOS app calls.

Mirrors the contract documented in
`bitchat-amber/bitchat/Services/HubClient.swift`. The iOS app is the only
consumer; the operator dashboard is served by `/api/*` routers elsewhere.

Endpoints: `/v1/register` (creates Account), `/v1/message` (inserts
InboundMessage with channel='app'), `/v1/alerts/active` (returns
operator-issued Alerts), `WS /v1/stream` (pushes ALERT_ISSUED on
incident_upserted). Sighting / location_report / profile remain stubs
until the DTN layer re-merges.

Auth: `Authorization: Bearer <userId>` — `userId` is the phone number,
returned to iOS at register time. Friend can swap for a JWT later.

Civilian messages are *never* cases. A "case" is an operator-issued
Alert created via `POST /api/incidents`. Civilian messages ride
`InboundMessage(channel='app', in_reply_to_alert_id=NULL)` — they appear
on the Messages tab's live wire (`MessagesView.tsx`) but do NOT show up
on the Cases page. If a caseworker decides a message warrants a case,
that's a separate explicit action.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Optional

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Response, WebSocket
from fastapi.websockets import WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.db.alerts import Alert
from server.db.base import generate_ulid
from server.db.engine import get_engine, get_session_maker
from server.db.identity import NGO, Account, get_or_create_default_ngo
from server.db.messages import InboundMessage
from server.db.session import get_db
from server.eventbus.postgres import PostgresEventBus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["civilian"])


# ---------------------------------------------------------------------------
# Schemas (request/response shapes the iOS HubClient expects verbatim)
# ---------------------------------------------------------------------------


class RegisterBody(BaseModel):
    name: str
    phone_number: str
    profession: Optional[str] = None
    language: str
    bitchat_pubkey: str
    apns_token: Optional[str] = None


class RegisterResponse(BaseModel):
    user_id: str
    hub_pubkey: str
    ngo_name: str


class MessageBody(BaseModel):
    body: str
    client_msg_id: str
    sent_at: float  # unix seconds; iOS sends Date().timeIntervalSince1970


class OkResponse(BaseModel):
    ok: bool = True


class SightingBody(BaseModel):
    """JSON request body when the user submits a sighting *without*
    photo/voice attachments. iOS sends multipart/form-data when media
    is attached — that path stays a stub for now."""

    case_id: str
    free_text: str
    client_msg_id: str
    observed_at: float
    location: Optional[list[float]] = None  # [lat, lng]


class SightingResponse(BaseModel):
    sighting_id: str
    ack: bool = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _resolve_single_ngo(db: AsyncSession) -> NGO:
    """Return the single configured NGO. If none exist yet (fresh volume),
    create the default one on the fly so /v1/register doesn't fail
    cold-start. Multi-NGO deployments (>1) are still rejected — there's no
    routing key to choose between them on a civilian app registration."""
    try:
        return await get_or_create_default_ngo(db)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def _bearer_phone(authorization: str = Header(...)) -> str:
    """Extract phone from `Authorization: Bearer <phone>`. The phone
    serves as the opaque user_id the iOS app received from /v1/register.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty bearer token")
    return token


# ---------------------------------------------------------------------------
# POST /v1/register
# ---------------------------------------------------------------------------


@router.post("/register", response_model=RegisterResponse)
async def register(
    body: RegisterBody,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    ngo = await _resolve_single_ngo(db)

    acc = await db.get(Account, body.phone_number)
    if acc is None:
        acc = Account(
            phone=body.phone_number,
            ngo_id=ngo.ngo_id,
            language=body.language,
            push_token=body.apns_token,
            # Stash the iOS-supplied bitchat pubkey in `account_id` until the
            # `bitchat_pubkey` column lands on main (it was in the orphaned
            # DTN PR #5). The iOS app sends a hex string; either column
            # accepts the same shape.
            account_id=body.bitchat_pubkey,
            source="app",
        )
        db.add(acc)
        await db.flush()
    else:
        # Re-register: refresh language + push token + key.
        acc.language = body.language
        acc.push_token = body.apns_token
        acc.account_id = body.bitchat_pubkey

    await db.commit()

    return RegisterResponse(
        user_id=body.phone_number,
        # Stub: real X25519 hub pubkey gets wired when the DTN library
        # re-merges and the friend exposes a key from env.
        hub_pubkey="00" * 32,
        ngo_name=ngo.name,
    )


# ---------------------------------------------------------------------------
# POST /v1/message
# ---------------------------------------------------------------------------


@router.post("/message", response_model=OkResponse)
async def message(
    body: MessageBody,
    user_id: str = Depends(_bearer_phone),
    db: AsyncSession = Depends(get_db),
) -> OkResponse:
    acc = await db.get(Account, user_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="Unknown account; register first")

    # Civilian messages are NOT cases — they ride orphan (no alert reference)
    # and surface on the dashboard's Messages tab as live wire. A caseworker
    # can promote a message to a case via the explicit Create Case flow.
    msg_id = generate_ulid()
    msg = InboundMessage(
        msg_id=msg_id,
        ngo_id=acc.ngo_id,
        channel="app",
        sender_phone=user_id,
        in_reply_to_alert_id=None,
        body=body.body,
        media_urls=[],
        raw={
            "kind": "general_message",
            "client_msg_id": body.client_msg_id,
            "sent_at": body.sent_at,
        },
        received_at=datetime.now(UTC),
        status="new",
    )
    db.add(msg)
    await db.commit()

    # Wakes the triage worker + flips the WS stream to push the new message
    # to the operator dashboard. Mirrors the pattern in sim_inbound.
    bus = PostgresEventBus(get_engine())
    await bus.publish("new_inbound", msg_id)

    return OkResponse(ok=True)


# ---------------------------------------------------------------------------
# Stubs — the other five endpoints the iOS app calls.
# ---------------------------------------------------------------------------
#
# These return 501 (rather than the FastAPI default 405 / 404) so the
# iOS app's HubError surfaces a clean "not supported yet" rather than a
# misleading "method not allowed". Real implementations land when the
# DTN library re-merges (sighting, location_report, profile) and when
# the WS stream gets wired to the existing eventbus channels.


@router.post("/sighting", response_model=SightingResponse)
async def sighting(
    body: SightingBody,
    user_id: str = Depends(_bearer_phone),
    db: AsyncSession = Depends(get_db),
) -> SightingResponse:
    """A user-submitted sighting *on* a specific operator-issued case.

    Unlike civilian free-form messages (`/v1/message`), sightings reference
    a `case_id` — they thread under that case on the dashboard. The
    triage worker will classify the body and the agent worker will see
    the bucket (because there's an alert_id) and may suggest follow-up
    actions.

    Photo/voice multipart uploads aren't supported here yet; iOS only
    sends multipart when media is attached, so text-only sightings work
    over HTTP and media still falls back to the DTN mesh queue (the
    "Offline — sighting queued for mesh relay" path).
    """
    acc = await db.get(Account, user_id)
    if acc is None:
        raise HTTPException(status_code=404, detail="Unknown account; register first")

    alert = await db.get(Alert, body.case_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="case not found")

    msg_id = generate_ulid()
    msg = InboundMessage(
        msg_id=msg_id,
        ngo_id=acc.ngo_id,
        channel="app",
        sender_phone=user_id,
        in_reply_to_alert_id=body.case_id,
        body=body.free_text,
        media_urls=[],
        raw={
            "kind": "sighting",
            "client_msg_id": body.client_msg_id,
            "observed_at": body.observed_at,
            "location": body.location,
        },
        received_at=datetime.now(UTC),
        status="new",
    )
    db.add(msg)
    await db.commit()

    bus = PostgresEventBus(get_engine())
    await bus.publish("new_inbound", msg_id)

    return SightingResponse(sighting_id=msg_id, ack=True)


@router.post("/location_report")
async def location_report_stub(
    user_id: str = Depends(_bearer_phone),
) -> Response:
    del user_id
    return Response(status_code=501, content="endpoint not yet implemented")


@router.post("/profile")
async def profile_stub(
    user_id: str = Depends(_bearer_phone),
) -> Response:
    del user_id
    return Response(status_code=501, content="endpoint not yet implemented")


@router.get("/alerts/active")
async def alerts_active(
    user_id: str = Depends(_bearer_phone),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return all active operator-issued amber alerts for the iOS app.

    Excludes `category='general_inbound'` (those are per-user app-message
    threads — not real alerts a civilian should see).
    """
    del user_id  # auth-only check; alerts are not user-scoped today
    rows = (
        await db.execute(
            select(Alert)
            .where(Alert.status == "active")
            .where(Alert.category != "general_inbound")
        )
    ).scalars().all()
    return {"alerts": [_alert_to_ios_payload(a) for a in rows]}


def _alert_to_ios_payload(alert: Alert) -> dict[str, Any]:
    """Map an Alert row to the iOS HubClient's expected envelope.

    iOS expects keys: case_id, title, summary, issued_at (unix seconds),
    version (int), photo_url (optional), category (optional).
    """
    # Use updated_at so edits push a newer timestamp to the iOS upsertAlert;
    # falls back to created_at when the row hasn't been edited yet.
    ts = alert.updated_at or alert.created_at
    issued_at = ts.timestamp() if ts else 0
    return {
        "case_id": alert.alert_id,
        "title": alert.person_name or (alert.description or "")[:80],
        "summary": alert.description or "",
        "issued_at": issued_at,
        "version": 1,
        "photo_url": None,
        "category": alert.category,
    }


# ---------------------------------------------------------------------------
# WS /v1/stream — push ALERT_ISSUED to connected iOS clients.
# ---------------------------------------------------------------------------
#
# Subscribes to the existing `incident_upserted` Postgres NOTIFY channel.
# When an operator creates a case via POST /api/incidents, the dashboard
# WS already receives the event; this handler forwards a typed envelope
# the iOS HubEvent decoder expects (type=ALERT_ISSUED).
#
# Auth: iOS sends `Authorization: Bearer <userId>` as a connection header.
# WebSockets in browsers can't set custom headers, but iOS URLSessionTask
# WebSocket can. We accept the header if present; otherwise still accept
# the connection (the demo doesn't have auth-revocation yet).


@router.websocket("/stream")
async def stream(websocket: WebSocket) -> None:
    await websocket.accept()
    bus = PostgresEventBus(get_engine())
    sm = get_session_maker()

    async def forwarder() -> None:
        async for alert_id in bus.subscribe("incident_upserted"):
            try:
                async with sm() as s:
                    alert = await s.get(Alert, alert_id)
                if alert is None or alert.category == "general_inbound":
                    continue
                envelope = {
                    "type": "ALERT_ISSUED",
                    **_alert_to_ios_payload(alert),
                }
                await websocket.send_text(json.dumps(envelope))
            except WebSocketDisconnect:
                return
            except Exception:  # noqa: BLE001 — keep the loop alive
                logger.exception("civilian /v1/stream forward failed")

    forward_task = asyncio.create_task(forwarder(), name="civilian-stream-forwarder")

    try:
        # Drain inbound frames so the connection stays half-open. The iOS
        # app doesn't send anything on this socket today, but if it ever
        # does we just discard.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        forward_task.cancel()
        try:
            await asyncio.wait_for(forward_task, timeout=2.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
