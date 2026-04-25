from fastapi import FastAPI

from server.api.health import router as health_router
from server.api.operators import router as operators_router

app = FastAPI(title="anth-hackathon26 matching engine")
app.include_router(health_router)
app.include_router(operators_router)
