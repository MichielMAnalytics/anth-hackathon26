import asyncio
import json
import math
import os
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from fastapi import Header

from . import audiences as audiences_module
from . import dashboard as dashboard_module
from . import operators as operators_module
from datetime import datetime, timezone
from uuid import uuid4

from .schemas import (
    BroadcastAck,
    BroadcastPayload,
    IngestEvent,
    Message,
    OperatorMessage,
    RegionStats,
    StreamEvent,
)
from .seed import load_seed
from .store import store

app = FastAPI(title="NGO Hub")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class WSHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def add(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.add(ws)

    async def remove(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, event: StreamEvent) -> None:
        payload = event.model_dump_json(by_alias=True)
        async with self._lock:
            dead: list[WebSocket] = []
            for ws in self._clients:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._clients.discard(ws)


hub = WSHub()


@app.get("/api/incidents")
def list_incidents() -> list[dict]:
    incidents = store.list_incidents()
    incidents.sort(
        key=lambda i: (
            {"critical": 0, "high": 1, "medium": 2, "low": 3}[i.severity],
            -(i.lastActivity.timestamp() if i.lastActivity else 0),
        )
    )
    return [json.loads(i.model_dump_json(by_alias=True)) for i in incidents]


@app.get("/api/incidents/{incident_id}")
def get_incident(incident_id: str):
    inc = store.get_incident(incident_id)
    if not inc:
        return JSONResponse({"error": "not found"}, status_code=404)
    return json.loads(inc.model_dump_json(by_alias=True))


@app.get("/api/incidents/{incident_id}/messages")
def list_messages(incident_id: str) -> list[dict]:
    msgs = store.list_messages(incident_id)
    return [json.loads(m.model_dump_json(by_alias=True)) for m in msgs]


@app.post("/api/ingest")
async def ingest(event: IngestEvent):
    incident, message = store.upsert(event)
    await hub.broadcast(StreamEvent(type="message", incident=incident, message=message))
    return {"ok": True, "incidentId": incident.id, "messageId": message.messageId}


def _operator(header_id: str | None) -> operators_module.Operator:
    return operators_module.get(header_id)


@app.get("/api/operators")
def list_operators():
    return [json.loads(o.model_dump_json(by_alias=True)) for o in operators_module.OPERATORS]


@app.get("/api/me")
def whoami(x_operator_id: str | None = Header(default=None)):
    return json.loads(_operator(x_operator_id).model_dump_json(by_alias=True))


@app.get("/api/audiences")
def list_audiences() -> list[dict]:
    return [json.loads(a.model_dump_json(by_alias=True)) for a in audiences_module.AUDIENCES]


@app.get("/api/dashboard")
def get_dashboard(window: int = 60):
    return dashboard_module.build_dashboard(window_minutes=window)


@app.get("/api/regions/{region}/timeline")
def region_timeline(region: str, minutes: int = 60, bucket: int = 60):
    if region not in audiences_module.REGION_META:
        return JSONResponse({"error": "unknown region"}, status_code=404)
    series = store.timeline(region, minutes=minutes, bucket_seconds=bucket)
    total = sum(c for _, c in series)
    return {
        "region": region,
        "minutes": minutes,
        "bucketSeconds": bucket,
        "buckets": [
            {"ts": t.isoformat(), "count": c} for t, c in series
        ],
        "total": total,
    }


@app.get("/api/regions/stats")
def region_stats() -> list[dict]:
    out: list[RegionStats] = []
    incidents = store.list_incidents()
    audiences = audiences_module.AUDIENCES
    for region, meta in audiences_module.REGION_META.items():
        in_region = [i for i in incidents if i.region == region]
        msg_count = sum(i.messageCount for i in in_region)
        reachable = sum(a.count for a in audiences if region in a.regions and "civilian" in a.roles)
        msgs_per_min = store.msgs_per_minute(region)
        baseline = store.baseline_msgs_per_minute(region)
        anomaly = msgs_per_min > 3 * baseline + 2
        out.append(
            RegionStats(
                region=region,
                label=meta["label"],
                lat=meta["lat"],
                lon=meta["lon"],
                reachable=reachable,
                incidentCount=len(in_region),
                messageCount=msg_count,
                msgsPerMin=round(msgs_per_min, 2),
                baselineMsgsPerMin=round(baseline, 2),
                anomaly=anomaly,
            )
        )
    return [json.loads(s.model_dump_json(by_alias=True)) for s in out]


def _build_ack(payload: BroadcastPayload, kind: str) -> BroadcastAck:
    aud = audiences_module.get(payload.audienceId)
    if aud is None:
        return BroadcastAck(
            ok=False,
            queued=0,
            batches=0,
            etaSeconds=0,
            channels=[payload.channels],
            audienceLabel="(unknown audience)",
            note=f"audience {payload.audienceId!r} not found",
        )
    # batch size differs by channel
    if payload.channels == "sms":
        batch_size = 400
        channels = ["sms"]
    elif payload.channels == "app":
        batch_size = 5000
        channels = ["app"]
    else:  # fallback: try app first, SMS for rest
        batch_size = 1500
        channels = ["app", "sms"]
    queued = aud.count
    batches = max(1, math.ceil(queued / batch_size))
    eta = batches * 30
    audience_in_region = (
        aud.label if not payload.region else f"{aud.label} (filtered to {payload.region})"
    )
    note = (
        f"{kind.capitalize()} queued. Batching to {batches} group"
        f"{'s' if batches != 1 else ''} of ~{batch_size}; ETA ~{eta}s."
    )
    return BroadcastAck(
        ok=True,
        queued=queued,
        batches=batches,
        etaSeconds=eta,
        channels=channels,
        audienceLabel=audience_in_region,
        note=note,
    )


def _check_broadcast_permissions(
    op: operators_module.Operator, payload: BroadcastPayload
) -> tuple[bool, str]:
    if not operators_module.can_act_in_region(op, payload.region):
        return False, f"{op.name} ({op.role}) cannot broadcast in {payload.region}."
    aud = audiences_module.get(payload.audienceId)
    if aud and "civilian" in aud.roles and not operators_module.can_broadcast_to_civilians(op):
        return (
            False,
            f"Junior operators cannot broadcast to civilian audiences. "
            f"Escalate to a senior operator or pick an NGO/medical audience.",
        )
    return True, ""


@app.post("/api/alerts")
def send_alert(
    payload: BroadcastPayload, x_operator_id: str | None = Header(default=None)
):
    op = _operator(x_operator_id)
    ok, reason = _check_broadcast_permissions(op, payload)
    if not ok:
        return JSONResponse({"ok": False, "error": "permission", "reason": reason}, status_code=403)
    return json.loads(_build_ack(payload, "alert").model_dump_json(by_alias=True))


@app.post("/api/requests")
def send_request(
    payload: BroadcastPayload, x_operator_id: str | None = Header(default=None)
):
    op = _operator(x_operator_id)
    ok, reason = _check_broadcast_permissions(op, payload)
    if not ok:
        return JSONResponse({"ok": False, "error": "permission", "reason": reason}, status_code=403)
    return json.loads(_build_ack(payload, "request").model_dump_json(by_alias=True))


@app.post("/api/cases/{incident_id}/messages")
async def send_operator_message(
    incident_id: str,
    payload: OperatorMessage,
    x_operator_id: str | None = Header(default=None),
):
    incident = store.get_incident(incident_id)
    if not incident:
        return JSONResponse({"error": "case not found"}, status_code=404)
    op = _operator(x_operator_id)
    if not operators_module.can_act_in_region(op, incident.region):
        return JSONResponse(
            {
                "ok": False,
                "error": "permission",
                "reason": f"{op.name} ({op.role}) is not assigned to {incident.region}.",
            },
            status_code=403,
        )
    msg = Message(
        messageId=str(uuid4()),
        incidentId=incident_id,
        **{"from": f"operator:{op.id}"},
        body=payload.body,
        ts=datetime.now(timezone.utc),
        outbound=True,
        via=payload.via,
    )
    store.append_outbound(msg)
    refreshed = store.get_incident(incident_id) or incident
    await hub.broadcast(StreamEvent(type="message", incident=refreshed, message=msg))

    ack: BroadcastAck | None = None
    if payload.audienceId:
        ack = _build_ack(
            BroadcastPayload(
                audienceId=payload.audienceId,
                channels=payload.via,
                region=incident.region,
                body=payload.body,
                incidentId=incident_id,
            ),
            "case-message",
        )
    return {
        "ok": True,
        "messageId": msg.messageId,
        "broadcast": json.loads(ack.model_dump_json(by_alias=True)) if ack else None,
    }


@app.post("/api/sim/seed")
async def sim_seed():
    n = load_seed()
    for inc in store.list_incidents():
        await hub.broadcast(StreamEvent(type="incident_upserted", incident=inc))
    return {"ok": True, "incidents": len(store.list_incidents()), "events": n}


@app.websocket("/ws/stream")
async def stream(ws: WebSocket):
    await ws.accept()
    await hub.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await hub.remove(ws)


# --- Static assets (built React app) ---
WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        target = WEB_DIST / full_path
        if full_path and target.is_file():
            return FileResponse(target)
        return FileResponse(WEB_DIST / "index.html")


if os.environ.get("SEED_ON_STARTUP", "").lower() in {"1", "true", "yes"}:
    load_seed()
