from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers.pipeline import router as pipeline_router
from app.routers.events import router as events_router
from app.routers.opportunities import router as opportunities_router
from app.routers.signals import router as signals_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="HedgeFund V2 API",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "hedgefund-api"}


app.include_router(signals_router)
app.include_router(events_router)
app.include_router(opportunities_router)
app.include_router(pipeline_router)
