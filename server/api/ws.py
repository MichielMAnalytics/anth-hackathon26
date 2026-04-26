import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from server.api.incidents import alert_to_incident_shape
from server.db.alerts import Alert
from server.db.decisions import AgentDecision, ToolCall
from server.db.engine import get_engine, get_session_maker
from server.db.messages import Bucket, InboundMessage
from server.eventbus.postgres import PostgresEventBus

router = APIRouter()
logger = logging.getLogger(__name__)


def _incident_shape(alert: Optional[Alert]) -> dict:
    """Camel-case Incident shape, matching GET /api/incidents.

    A None alert returns an empty dict so the frontend can ignore it
    rather than upsert a placeholder with id=undefined.
    """
    if alert is None:
        return {}
    return alert_to_incident_shape(alert)


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


async def _compose_thinking_event(bucket_key: str) -> Optional[dict]:
    """Agent claimed a bucket; UI should glow the matching region card."""
    sm = get_session_maker()
    async with sm() as s:
        bucket = await s.get(Bucket, bucket_key)
        if bucket is None:
            return None
        alert = await s.get(Alert, bucket.alert_id) if bucket.alert_id else None
    return {
        "type": "agent_thinking",
        "bucketKey": bucket_key,
        "alertId": bucket.alert_id,
        "regionPrefix": bucket.geohash_prefix_4,
        "incident": _incident_shape(alert),
    }


async def _compose_decision_event(decision_id: str) -> Optional[dict]:
    sm = get_session_maker()
    async with sm() as s:
        d = await s.get(AgentDecision, decision_id)
        if d is None:
            return None
        bucket = await s.get(Bucket, d.bucket_key)
        alert = await s.get(Alert, bucket.alert_id) if bucket else None
        calls = (
            await s.execute(
                select(ToolCall).where(ToolCall.decision_id == d.decision_id)
            )
        ).scalars().all()
    return {
        "type": "decision_made",
        "decision": {
            "id": d.decision_id,
            "model": d.model,
            "summary": d.reasoning_summary,
            "totalTurns": d.total_turns,
            "latencyMs": d.latency_ms,
            "costUsd": d.cost_usd,
            "createdAt": d.created_at.isoformat() if d.created_at else None,
            "isHeartbeat": d.bucket_key.startswith("heartbeat:"),
            "toolCalls": [
                {"id": c.call_id, "name": c.tool_name, "mode": c.mode,
                 "approvalStatus": c.approval_status}
                for c in calls
            ],
        },
        "alertId": bucket.alert_id if bucket else None,
        "regionPrefix": bucket.geohash_prefix_4 if bucket else None,
        "incident": _incident_shape(alert),
    }


async def _compose_suggestion_pending_event(call_id: str) -> Optional[dict]:
    sm = get_session_maker()
    async with sm() as s:
        tc = await s.get(ToolCall, call_id)
        if tc is None or tc.approval_status != "pending":
            return None
        decision = await s.get(AgentDecision, tc.decision_id) if tc.decision_id else None
        alert = None
        if decision is not None:
            bucket = await s.get(Bucket, decision.bucket_key)
            if bucket is not None:
                alert = await s.get(Alert, bucket.alert_id)
        elif isinstance(tc.args, dict) and tc.args.get("incident_id"):
            alert = await s.get(Alert, tc.args["incident_id"])
    return {
        "type": "suggestion_pending",
        "suggestion": {
            "id": tc.call_id,
            "tool": tc.tool_name,
            "mode": tc.mode,
            "args": tc.args,
            "createdAt": tc.created_at.isoformat() if tc.created_at else None,
            "decisionSummary": decision.reasoning_summary if decision else None,
        },
        "incident": _incident_shape(alert) if alert else None,
    }


async def _compose_suggestion_resolved_event(payload: str) -> Optional[dict]:
    """Payload format: '<call_id>|<status>'."""
    if "|" not in payload:
        return None
    call_id, status = payload.split("|", 1)
    return {
        "type": "suggestion_resolved",
        "id": call_id,
        "approvalStatus": status,
    }


@router.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket):
    await websocket.accept()
    bus = PostgresEventBus(get_engine())
    closed = asyncio.Event()

    async def listen(channel: str):
        async for payload in bus.subscribe(channel):
            if closed.is_set():
                return
            try:
                evt: Optional[dict] = None
                if channel == "new_inbound":
                    evt = await _compose_inbound_event(payload)
                elif channel == "incident_upserted":
                    evt = await _compose_incident_event(payload)
                elif channel == "agent_thinking":
                    evt = await _compose_thinking_event(payload)
                elif channel == "decision_made":
                    evt = await _compose_decision_event(payload)
                elif channel == "suggestion_pending":
                    evt = await _compose_suggestion_pending_event(payload)
                elif channel == "suggestion_resolved":
                    evt = await _compose_suggestion_resolved_event(payload)
                if evt:
                    await websocket.send_json(evt)
            except (WebSocketDisconnect, RuntimeError):
                # Client gone — flag every listener to bail.
                closed.set()
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("ws_stream(%s): %s", channel, exc)

    async def heartbeat():
        """Detect a silently-dead client by reading from it; raises on disconnect."""
        try:
            while not closed.is_set():
                await websocket.receive_text()
        except WebSocketDisconnect:
            closed.set()
        except Exception:  # noqa: BLE001
            closed.set()

    tasks = [
        asyncio.create_task(listen(c)) for c in (
            "new_inbound", "incident_upserted",
            "agent_thinking", "decision_made",
            "suggestion_pending", "suggestion_resolved",
        )
    ]
    tasks.append(asyncio.create_task(heartbeat()))
    try:
        # Wait until the close flag is set (any listener saw the disconnect).
        await closed.wait()
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("ws_stream: %s", exc)
    finally:
        closed.set()
        for t in tasks:
            t.cancel()
        try:
            await websocket.close()
        except Exception:
            pass
