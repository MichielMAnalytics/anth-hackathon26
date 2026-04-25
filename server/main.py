import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from server.api.audiences import router as audiences_router
from server.api.dashboard import router as dashboard_router
from server.api.health import router as health_router
from server.api.incidents import router as incidents_router
from server.api.operators import router as operators_router
from server.api.regions import router as regions_router
from server.api.sim import router as sim_router
from server.api.ws import router as ws_router
from server.db.engine import get_engine, get_session_maker
from server.eventbus.postgres import PostgresEventBus
from server.workers.triage import triage_worker_loop

logger = logging.getLogger(__name__)

_worker_task: Optional[asyncio.Task] = None
_event_bus: Optional[PostgresEventBus] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker_task, _event_bus
    engine = get_engine()
    session_maker = get_session_maker()
    _event_bus = PostgresEventBus(engine)
    _worker_task = asyncio.create_task(
        triage_worker_loop(_event_bus, session_maker),
        name="triage-worker",
    )
    try:
        yield
    finally:
        if _worker_task and not _worker_task.done():
            _worker_task.cancel()
            try:
                await asyncio.wait_for(_worker_task, timeout=5.0)
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
app.include_router(dashboard_router)
app.include_router(sim_router)
app.include_router(ws_router)
