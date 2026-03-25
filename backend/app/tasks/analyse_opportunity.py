"""Agent fan-out pipeline: BLPOP consumer, fan-out, per-persona tasks, committee trigger.

Architecture:
  consume_queue  -- Long-running Celery task; BLPOP-blocks on opportunity_queue.
  fan_out        -- Dispatches 5 run_persona_agent tasks in parallel (one per persona).
  run_persona_agent -- Invokes PERSONA_GRAPH, persists verdict to Redis hash,
                       increments atomic counter, publishes events.
  run_committee  -- Triggered by last completing agent (counter == 5); aggregates
                    verdicts and validates inter-agent variance.

No Celery Chord is used. Fan-in is implemented via Redis HINCRBY counter.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import redis

from app.agents.graph import PERSONA_GRAPH
from app.agents.schemas import AgentVerdict
from app.events.publisher import publish_event
from app.signals.queue import OPP_QUEUE_KEY
from app.tasks.celery_app import app

logger = logging.getLogger(__name__)

_REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

AGENTS = ["buffett", "munger", "ackman", "cohen", "dalio"]
AGENT_COUNT = len(AGENTS)
VERDICT_TTL = 86400  # 24 hours


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _run_graph_sync(
    persona_name: str,
    data_context: dict[str, Any],
    redis_url: str,
) -> dict[str, Any]:
    """Invoke PERSONA_GRAPH synchronously from a Celery worker thread.

    Celery workers run in a sync context. This helper bridges into async by
    calling asyncio.run(). If an event loop is already running (e.g. during
    tests with nest_asyncio), it patches and retries.

    Args:
        persona_name: One of the five persona names.
        data_context: Full opportunity dict; the graph's DataPartitioner filters
            per-persona before the LLM call.
        redis_url: Redis connection URL passed into the graph state.

    Returns:
        A dict representation of the AgentVerdict (via model_dump()).
    """

    async def _invoke() -> dict[str, Any]:
        result = await PERSONA_GRAPH.ainvoke(
            {
                "persona_name": persona_name,
                "data_context": data_context,
                "redis_url": redis_url,
                "verdict": None,
            }
        )
        return result["verdict"].model_dump()

    try:
        return asyncio.run(_invoke())
    except RuntimeError:
        # Event loop already running (e.g. Jupyter / nest_asyncio test env).
        import nest_asyncio  # type: ignore[import]

        nest_asyncio.apply()
        return asyncio.run(_invoke())


# ---------------------------------------------------------------------------
# Celery tasks
# ---------------------------------------------------------------------------


@app.task(
    name="app.tasks.analyse_opportunity.run_persona_agent",
    bind=True,
    max_retries=3,
)
def run_persona_agent(
    self,
    opportunity_id: str,
    persona_name: str,
    data_context: dict,
) -> None:
    """Invoke the LangGraph persona, persist verdict to Redis, increment counter.

    Publishes AGENT_STARTED before invoking the graph and AGENT_COMPLETE after
    persisting the result. When the atomic HINCRBY counter reaches AGENT_COUNT
    (5), this task dispatches run_committee.

    Args:
        opportunity_id: Compound key ``ticker:detected_at``.
        persona_name: One of "buffett", "munger", "ackman", "cohen", "dalio".
        data_context: Full opportunity payload from Phase 2 queue.
    """
    r = redis.from_url(_REDIS_URL)
    try:
        publish_event(
            r,
            "AGENT_STARTED",
            {"opportunity_id": opportunity_id, "persona": persona_name},
        )

        try:
            verdict_dict = _run_graph_sync(persona_name, data_context, _REDIS_URL)
        except Exception as exc:
            logger.exception(
                "run_persona_agent failed for %s/%s — retrying",
                opportunity_id,
                persona_name,
            )
            raise self.retry(exc=exc, countdown=30)

        # Persist verdict to Redis hash (key: verdicts:<opportunity_id>)
        r.hset(
            f"verdicts:{opportunity_id}",
            persona_name,
            json.dumps(verdict_dict, default=str),
        )
        r.expire(f"verdicts:{opportunity_id}", VERDICT_TTL)

        # Atomic fan-in counter
        completed = int(r.hincrby(f"verdicts_counter:{opportunity_id}", "count", 1))
        r.expire(f"verdicts_counter:{opportunity_id}", VERDICT_TTL)

        publish_event(
            r,
            "AGENT_COMPLETE",
            {
                "opportunity_id": opportunity_id,
                "persona": persona_name,
                "verdict": verdict_dict.get("verdict"),
                "confidence": verdict_dict.get("confidence"),
            },
        )

        logger.info(
            "Agent %s complete for %s — %d/%d agents done",
            persona_name,
            opportunity_id,
            completed,
            AGENT_COUNT,
        )

        if completed >= AGENT_COUNT:
            logger.info("All agents complete for %s — triggering committee", opportunity_id)
            run_committee.delay(opportunity_id)

    finally:
        r.close()


@app.task(
    name="app.tasks.analyse_opportunity.fan_out",
    bind=True,
)
def fan_out(self, opportunity: dict) -> None:
    """Dispatch one run_persona_agent task per persona in parallel.

    Builds the compound opportunity_id from ticker and detected_at, then
    dispatches AGENT_COUNT (5) tasks — one for each persona in AGENTS.

    Args:
        opportunity: Opportunity dict enqueued by Phase 2 scanner.
    """
    opportunity_id = f"{opportunity['ticker']}:{opportunity['detected_at']}"
    data_context = opportunity  # Full dict; partitioner inside graph filters per-persona

    logger.info("Fanning out to %d agents for %s", AGENT_COUNT, opportunity_id)

    for persona in AGENTS:
        run_persona_agent.delay(opportunity_id, persona, data_context)


@app.task(
    name="app.tasks.analyse_opportunity.consume_queue",
    bind=True,
)
def consume_queue(self) -> None:
    """Long-running BLPOP consumer for the opportunity queue.

    Blocks on OPP_QUEUE_KEY with a 30-second timeout, looping forever.
    On each dequeue, dispatches fan_out. Designed to run as a dedicated
    Celery worker (celery -A app.tasks.celery_app worker --queues default).
    """
    r = redis.from_url(_REDIS_URL)
    logger.info("consume_queue started — listening on %s", OPP_QUEUE_KEY)

    while True:
        result = r.blpop(OPP_QUEUE_KEY, timeout=30)
        if result is None:
            # Timeout — loop back and keep listening
            continue

        _, raw = result
        opportunity = json.loads(raw)
        logger.info(
            "Dequeued opportunity: %s (detected_at=%s)",
            opportunity.get("ticker"),
            opportunity.get("detected_at"),
        )
        fan_out.delay(opportunity)


@app.task(
    name="app.tasks.analyse_opportunity.run_committee",
    bind=True,
)
def run_committee(self, opportunity_id: str) -> None:
    """Aggregate all five agent verdicts and validate inter-agent variance.

    Loads the five verdicts from the Redis hash, parses them into AgentVerdict
    objects, computes variance, and validates the committee. Full committee
    aggregation and CIO decision are implemented in Plan 03-03.

    Args:
        opportunity_id: Compound key ``ticker:detected_at``.
    """
    from app.analysis.variance import compute_variance_score, is_committee_valid

    r = redis.from_url(_REDIS_URL)
    try:
        raw_verdicts = r.hgetall(f"verdicts:{opportunity_id}")
        verdicts = [
            AgentVerdict(**json.loads(v)) for v in raw_verdicts.values()
        ]

        variance = compute_variance_score(verdicts)
        valid = is_committee_valid(verdicts)

        logger.info(
            "Committee for %s — variance=%.2f valid=%s agents=%d",
            opportunity_id,
            variance,
            valid,
            len(verdicts),
        )

        if not valid:
            logger.warning(
                "Low variance detected for %s (%.2f) — agents converged sycophantically",
                opportunity_id,
                variance,
            )

        # TODO(03-03): Committee aggregation, asymmetric scoring, CIO decision
        logger.info("Committee task complete (stub) for %s", opportunity_id)

    finally:
        r.close()
