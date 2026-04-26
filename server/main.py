import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from server.api.agent_feed import router as agent_feed_router
from server.api.audiences import router as audiences_router
from server.api.dashboard import router as dashboard_router
from server.api.health import router as health_router
from server.api.incidents import router as incidents_router
from server.api.operator_actions import router as operator_actions_router
from server.api.operators import router as operators_router
from server.api.regions import router as regions_router
from server.api.sim import router as sim_router
from server.api.suggestions import router as suggestions_router
from server.api.ws import router as ws_router
from server.db.engine import get_engine, get_session_maker
from server.eventbus.postgres import PostgresEventBus
from server.workers.agent import agent_worker_loop
from server.workers.heartbeat import heartbeat_loop
from server.workers.triage import triage_worker_loop

logger = logging.getLogger(__name__)

_triage_task: Optional[asyncio.Task] = None
_agent_task: Optional[asyncio.Task] = None
_heartbeat_task: Optional[asyncio.Task] = None
_event_bus: Optional[PostgresEventBus] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _triage_task, _agent_task, _heartbeat_task, _event_bus
    engine = get_engine()
    session_maker = get_session_maker()
    _event_bus = PostgresEventBus(engine)
    _triage_task = asyncio.create_task(
        triage_worker_loop(_event_bus, session_maker),
        name="triage-worker",
    )
    _agent_task = asyncio.create_task(
        agent_worker_loop(_event_bus, session_maker),
        name="agent-worker",
    )
    _heartbeat_task = asyncio.create_task(
        heartbeat_loop(_event_bus, session_maker),
        name="heartbeat",
    )
    try:
        yield
    finally:
        for t in (_triage_task, _agent_task, _heartbeat_task):
            if t and not t.done():
                t.cancel()
                try:
                    await asyncio.wait_for(t, timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
        if _event_bus:
            await _event_bus.close()


app = FastAPI(title="anth-hackathon26 matching engine", lifespan=lifespan)
app.include_router(health_router)
app.include_router(operators_router)
app.include_router(audiences_router)
app.include_router(regions_router)
app.include_router(incidents_router)
app.include_router(operator_actions_router)
app.include_router(suggestions_router)
app.include_router(agent_feed_router)
app.include_router(dashboard_router)
app.include_router(sim_router)
app.include_router(ws_router)


# ---------------------------------------------------------------------------
# Static frontend (production deploy).
# The Dockerfile builds web/dist and copies it into the image. In dev there
# is no web/dist and Vite serves the SPA on :5173 with /api proxied here, so
# we mount only when the build is present.
#
# StaticFiles serves files under web/dist (index.html, /assets/*, root-level
# pngs, etc.). For any non-API path that doesn't resolve to a file (e.g.
# /cases on hard refresh) we fall back to index.html so React Router can
# pick up history routes. Mounted last so API routers take precedence.
# ---------------------------------------------------------------------------

_WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
_INDEX_HTML = _WEB_DIST / "index.html"

if _WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=_WEB_DIST, html=True), name="spa")

    _NON_SPA_PREFIXES = ("/api", "/ws", "/health", "/assets")

    @app.exception_handler(StarletteHTTPException)
    async def _spa_history_fallback(request: Request, exc: StarletteHTTPException):
        path = request.url.path
        if (
            exc.status_code == 404
            and request.method == "GET"
            and not path.startswith(_NON_SPA_PREFIXES)
            and _INDEX_HTML.is_file()
        ):
            return FileResponse(_INDEX_HTML)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
