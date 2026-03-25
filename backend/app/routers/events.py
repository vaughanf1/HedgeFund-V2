"""FastAPI SSE endpoint for real-time pipeline event streaming (Plan 03-04).

Subscribes to the ``pipeline:events`` Redis Pub/Sub channel via
``redis.asyncio`` and streams every published event to connected clients
as Server-Sent Events.  Phase 4 frontend consumes this stream to update
the opportunity dashboard in real time.

Events published by Celery workers (publisher.py):
  AGENT_STARTED, AGENT_COMPLETE, COMMITTEE_COMPLETE, DECISION_MADE.
"""
from __future__ import annotations

import asyncio  # noqa: F401 — available for future generator sleep patterns
import logging
import os

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/events", tags=["events"])

_REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")


@router.get("/stream")
async def stream_pipeline_events() -> EventSourceResponse:
    """Stream pipeline events from Redis Pub/Sub as Server-Sent Events.

    Each SSE message has ``event: pipeline`` and ``data`` containing the
    JSON-serialised event payload published by a Celery worker.

    The client is responsible for reconnect logic (EventSource API handles
    this automatically in browsers).
    """

    async def event_generator():
        r = aioredis.from_url(_REDIS_URL)
        pubsub = r.pubsub()
        await pubsub.subscribe("pipeline:events")
        logger.info("SSE client subscribed to pipeline:events")
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    yield {"event": "pipeline", "data": data}
        finally:
            await pubsub.unsubscribe("pipeline:events")
            await r.aclose()
            logger.info("SSE client disconnected from pipeline:events")

    return EventSourceResponse(event_generator())
