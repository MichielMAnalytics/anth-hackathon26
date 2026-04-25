import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .schemas import AlertPayload, IngestEvent, StreamEvent
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
    await hub.broadcast(
        StreamEvent(type="message", incident=incident, message=message)
    )
    return {"ok": True, "incidentId": incident.id, "messageId": message.messageId}


@app.post("/api/alerts")
def send_alert(payload: AlertPayload):
    return {"ok": True, "queued": True, "incidentId": payload.incidentId}


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
