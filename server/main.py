from fastapi import FastAPI

from server.api.audiences import router as audiences_router
from server.api.health import router as health_router
from server.api.incidents import router as incidents_router
from server.api.operators import router as operators_router
from server.api.regions import router as regions_router

app = FastAPI(title="anth-hackathon26 matching engine")
app.include_router(health_router)
app.include_router(operators_router)
app.include_router(audiences_router)
app.include_router(regions_router)
app.include_router(incidents_router)
