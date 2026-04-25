from fastapi import FastAPI

from server.api.health import router as health_router

app = FastAPI(title="anth-hackathon26 matching engine")
app.include_router(health_router)
