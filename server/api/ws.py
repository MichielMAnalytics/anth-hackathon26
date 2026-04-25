import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from server.db.alerts import Alert
from server.db.engine import get_engine, get_session_maker
from server.db.messages import InboundMessage
from server.eventbus.postgres import PostgresEventBus

router = APIRouter()
logger = logging.getLogger(__name__)


def _incident_shape(alert: Optional[Alert]) -> dict:
    if alert is None:
        return {"alert_id": None, "person_name": "Unknown", "status": "unknown",
                "description": None, "photo_url": None}
    return {
        "alert_id": alert.alert_id,
        "person_name": alert.person_name,
        "status": alert.status,
        "description": alert.description,
        "photo_url": alert.photo_url,
    }


def _message_shape(msg: InboundMessage) -> dict:
    return {
        "msg_id": msg.msg_id,
        "channel": msg.channel,
        "sender_phone": msg.sender_phone,
        "body": msg.body,
        "media_urls": msg.media_urls,
        "status": msg.status,
        "received_at": msg.received_at.isoformat() if msg.received_at else None,
        "in_reply_to_alert_id": msg.in_reply_to_alert_id,
    }


async def _compose_inbound_event(msg_id: str) -> Optional[dict]:
    sm = get_session_maker()
    async with sm() as s:
        msg = await s.get(InboundMessage, msg_id)
        if msg is None:
            return None
        alert: Optional[Alert] = None
        if msg.in_reply_to_alert_id:
            alert = await s.get(Alert, msg.in_reply_to_alert_id)
        return {"type": "message", "incident": _incident_shape(alert), "message": _message_shape(msg)}


async def _compose_incident_event(alert_id: str) -> Optional[dict]:
    sm = get_session_maker()
    async with sm() as s:
        alert = await s.get(Alert, alert_id)
    if alert is None:
        return None
    return {"type": "incident_upserted", "incident": _incident_shape(alert), "message": None}


@router.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket):
    await websocket.accept()
    bus = PostgresEventBus(get_engine())

    async def listen(channel: str):
        async for payload in bus.subscribe(channel):
            try:
                if channel == "new_inbound":
                    evt = await _compose_inbound_event(payload)
                    if evt:
                        await websocket.send_json(evt)
                elif channel == "incident_upserted":
                    evt = await _compose_incident_event(payload)
                    if evt:
                        await websocket.send_json(evt)
                elif channel == "bucket_open":
                    pass
            except Exception as exc:
                logger.warning("ws_stream(%s): error: %s", channel, exc)

    tasks = [
        asyncio.create_task(listen("new_inbound")),
        asyncio.create_task(listen("incident_upserted")),
        asyncio.create_task(listen("bucket_open")),
    ]
    try:
        await asyncio.gather(*tasks)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("ws_stream: %s", exc)
    finally:
        for t in tasks:
            t.cancel()
        try:
            await websocket.close()
        except Exception:
            pass
