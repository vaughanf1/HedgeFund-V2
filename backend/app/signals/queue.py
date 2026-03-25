"""Redis opportunity queue with SET NX deduplication.

Phase 3 agents consume from OPP_QUEUE_KEY via BLPOP. Dedup key is per-ticker
(not per-signal-type) because agents analyze the full opportunity for a ticker.
"""
from __future__ import annotations

import json
import os

import redis

_REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
_DEDUP_TTL_SECONDS = int(
    os.environ.get("OPPORTUNITY_DEDUP_TTL_SECONDS", "3600")
)

OPP_QUEUE_KEY = "opportunity_queue"


def enqueue_opportunity(r: redis.Redis, ticker: str, payload: dict) -> bool:
    """Enqueue an opportunity for a ticker, deduplicating within TTL window.

    Args:
        r: Redis client.
        ticker: Ticker symbol — used as the dedup key scope.
        payload: Opportunity dict to push onto the queue.

    Returns:
        True if the opportunity was enqueued (new within dedup window).
        False if the ticker was already seen (duplicate — silently rejected).
    """
    dedup_key = f"opp:dedup:{ticker}"
    is_new = r.set(dedup_key, "1", nx=True, ex=_DEDUP_TTL_SECONDS)
    if not is_new:
        return False
    r.rpush(OPP_QUEUE_KEY, json.dumps(payload, default=str))
    return True
