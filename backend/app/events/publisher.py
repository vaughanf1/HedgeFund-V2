"""Redis Pub/Sub event publisher for pipeline state transitions.

Events: AGENT_STARTED, AGENT_COMPLETE, COMMITTEE_COMPLETE, DECISION_MADE.

Celery workers call ``publish_event`` (sync redis) on every state transition.
The FastAPI SSE endpoint (Plan 03-04) subscribes via ``redis.asyncio``.
"""

from __future__ import annotations

import json
import logging

import redis as redis_sync

logger = logging.getLogger(__name__)

EVENTS_CHANNEL = "pipeline:events"


def publish_event(r: redis_sync.Redis, event_type: str, payload: dict) -> int:
    """Publish a pipeline event to the Redis Pub/Sub channel.

    Args:
        r: A synchronous Redis client.
        event_type: Event name (e.g. ``AGENT_STARTED``).
        payload: Arbitrary JSON-serialisable dict.

    Returns:
        Number of subscribers that received the message.
    """
    message = json.dumps({"event": event_type, "data": payload}, default=str)
    num_subscribers = r.publish(EVENTS_CHANNEL, message)
    logger.info("Published %s event to %d subscribers", event_type, num_subscribers)
    return num_subscribers
