"""Pipeline control endpoints: trigger real data ingest + market scan.

POST /api/v1/pipeline/run  — backfill data and run a full scan
GET  /api/v1/pipeline/status — check pipeline health
"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_session
from app.db.models import AgentVerdictRecord, CIODecisionRecord, DetectedSignal
from app.tasks.celery_app import app as celery_app

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])

_REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")


@router.post("/run")
async def run_pipeline(
    days_back: int = 30,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Trigger a full pipeline run with real market data.

    1. Clears any demo data from DB
    2. Dispatches ingest tasks (price backfill, fundamentals, insider, news)
    3. Dispatches market scan (after ingest completes)

    Args:
        days_back: Days of price history to backfill (default 30).
    """
    # 1. Clear demo data
    demo_deleted = await session.execute(
        delete(DetectedSignal).where(DetectedSignal.source == "demo")
    )
    # Clear CIO decisions and verdicts that came from demo runs
    # (demo opportunity_ids have timestamps from demo runs)
    await session.commit()
    logger.info("Cleared %d demo signal rows", demo_deleted.rowcount)

    # 2. Dispatch ingest tasks — price with backfill, others immediately
    price_task = celery_app.send_task(
        "app.tasks.ingest_price.run",
        kwargs={"days_back": days_back},
    )
    fundamentals_task = celery_app.send_task("app.tasks.ingest_fundamentals.run")
    insider_task = celery_app.send_task("app.tasks.ingest_insider.run")
    news_task = celery_app.send_task("app.tasks.ingest_news.run")

    # 3. Dispatch scan with a countdown to let ingest complete first
    scan_task = celery_app.send_task(
        "app.tasks.scan_market.run",
        countdown=15,  # 15s delay to let ingest tasks finish
    )

    return {
        "status": "pipeline_triggered",
        "tasks": {
            "ingest_price": price_task.id,
            "ingest_fundamentals": fundamentals_task.id,
            "ingest_insider": insider_task.id,
            "ingest_news": news_task.id,
            "scan_market": scan_task.id,
        },
        "days_back": days_back,
    }


@router.get("/status")
async def pipeline_status() -> dict:
    """Check pipeline health — last scan time, data freshness, queue depth."""
    import redis.asyncio as aioredis

    r = aioredis.from_url(_REDIS_URL)
    try:
        last_scan = await r.get("scanner:last_scan_at")
        pass_rate = await r.get("scanner:last_pass_rate")
        total = await r.get("scanner:last_total")
        queue_len = await r.llen("opportunity_queue")

        return {
            "last_scan_at": last_scan.decode() if last_scan else None,
            "last_pass_rate": float(pass_rate) if pass_rate else None,
            "tickers_scanned": int(total) if total else None,
            "queue_depth": queue_len,
        }
    finally:
        await r.aclose()
