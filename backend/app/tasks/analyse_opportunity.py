"""Agent fan-out pipeline: BLPOP consumer, fan-out, per-persona tasks, committee trigger.

Architecture:
  consume_queue  -- Long-running Celery task; BLPOP-blocks on opportunity_queue.
  fan_out        -- Dispatches 5 run_persona_agent tasks in parallel (one per persona).
                   Also stores the full opportunity dict in Redis for run_committee.
  run_persona_agent -- Invokes PERSONA_GRAPH, persists verdict to Redis hash,
                       increments atomic counter, publishes events.
  run_committee  -- Triggered by last completing agent (counter == 5); runs the full
                    pipeline: asymmetric scoring → committee aggregation → CIO decision
                    → DB persist → events → Redis cleanup.

No Celery Chord is used. Fan-in is implemented via Redis HINCRBY counter.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
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

    # Store full opportunity in Redis so run_committee can load it without
    # re-deserialising from the queue or relying on task arguments.
    r = redis.from_url(_REDIS_URL)
    try:
        r.set(
            f"opportunity:{opportunity_id}",
            json.dumps(opportunity, default=str),
            ex=VERDICT_TTL,
        )
    finally:
        r.close()

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
    """Aggregate all five agent verdicts and produce a CIO decision.

    Full pipeline (Plan 03-03):
    1. Load verdicts from Redis hash.
    2. Parse into AgentVerdict objects.
    3. Variance check — log warning if agents converged (low variance), but
       continue: convergence does not block analysis.
    4. Load opportunity dict from Redis (stored by fan_out).
    5. evaluate_asymmetric() — 10X asymmetric bet scoring.
    6. aggregate_committee() — context-weighted conviction + regime detection.
    7. Publish COMMITTEE_COMPLETE event.
    8. make_cio_decision() — deterministic CIO decision.
    9. Publish DECISION_MADE event.
    10. Persist AgentVerdictRecord rows and CIODecisionRecord to DB via sync
        SQLAlchemy session.
    11. Clean up Redis keys.

    Args:
        opportunity_id: Compound key ``ticker:detected_at``.
    """
    from app.analysis.asymmetric import evaluate_asymmetric
    from app.analysis.cio import make_cio_decision
    from app.analysis.committee import aggregate_committee
    from app.analysis.variance import compute_variance_score, is_committee_valid
    from app.db.engine import SyncSessionLocal
    from app.db.models import AgentVerdictRecord, CIODecisionRecord

    r = redis.from_url(_REDIS_URL)
    try:
        # ------------------------------------------------------------------
        # 1 & 2. Load and parse verdicts
        # ------------------------------------------------------------------
        raw_verdicts = r.hgetall(f"verdicts:{opportunity_id}")
        verdicts = [
            AgentVerdict(**json.loads(v)) for v in raw_verdicts.values()
        ]

        # ------------------------------------------------------------------
        # 3. Variance check (warn only — do not block)
        # ------------------------------------------------------------------
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
                "Low variance detected for %s (%.2f) — agents may have converged "
                "sycophantically; proceeding with analysis",
                opportunity_id,
                variance,
            )

        # ------------------------------------------------------------------
        # 4. Load opportunity from Redis
        # ------------------------------------------------------------------
        raw_opportunity = r.get(f"opportunity:{opportunity_id}")
        if raw_opportunity:
            opportunity = json.loads(raw_opportunity)
        else:
            # Graceful degradation — reconstruct minimal dict from opportunity_id
            logger.warning(
                "Opportunity dict not found in Redis for %s — using minimal stub",
                opportunity_id,
            )
            ticker, detected_at = opportunity_id.split(":", 1) if ":" in opportunity_id else (opportunity_id, "")
            opportunity = {"ticker": ticker, "detected_at": detected_at}

        # ------------------------------------------------------------------
        # 5. Asymmetric scoring
        # ------------------------------------------------------------------
        asymmetric_result = evaluate_asymmetric(verdicts, opportunity)

        # ------------------------------------------------------------------
        # 6. Committee aggregation
        # ------------------------------------------------------------------
        report = aggregate_committee(opportunity_id, verdicts, opportunity, asymmetric_result)

        # ------------------------------------------------------------------
        # 7. Publish COMMITTEE_COMPLETE
        # ------------------------------------------------------------------
        publish_event(
            r,
            "COMMITTEE_COMPLETE",
            {
                "opportunity_id": opportunity_id,
                "consensus": report.consensus,
                "weighted_conviction": report.weighted_conviction,
                "asymmetric_flag": report.asymmetric_flag,
                "dissent_agents": report.dissent_agents,
            },
        )

        # ------------------------------------------------------------------
        # 8. CIO decision
        # ------------------------------------------------------------------
        decision = make_cio_decision(report)

        # ------------------------------------------------------------------
        # 9. Publish DECISION_MADE
        # ------------------------------------------------------------------
        publish_event(
            r,
            "DECISION_MADE",
            {
                "opportunity_id": opportunity_id,
                "final_verdict": decision.final_verdict,
                "conviction_score": decision.conviction_score,
                "suggested_allocation_pct": decision.suggested_allocation_pct,
                "risk_rating": decision.risk_rating,
                "time_horizon": decision.time_horizon,
            },
        )

        # ------------------------------------------------------------------
        # 10. Persist to DB via sync session
        # ------------------------------------------------------------------
        now = datetime.now(timezone.utc)

        with SyncSessionLocal() as session:
            # One AgentVerdictRecord row per persona
            for v in verdicts:
                record = AgentVerdictRecord(
                    analysed_at=now,
                    opportunity_id=opportunity_id,
                    persona=v.persona,
                    verdict=v.verdict,
                    confidence=v.confidence,
                    verdict_json=json.dumps(v.model_dump(), default=str),
                )
                session.merge(record)

            # One CIODecisionRecord row per opportunity
            cio_record = CIODecisionRecord(
                decided_at=now,
                opportunity_id=opportunity_id,
                conviction_score=decision.conviction_score,
                suggested_allocation_pct=decision.suggested_allocation_pct,
                final_verdict=decision.final_verdict,
                decision_json=json.dumps(decision.model_dump(), default=str),
            )
            session.merge(cio_record)
            session.commit()

        logger.info(
            "Committee pipeline complete for %s — verdict=%s conviction=%d",
            opportunity_id,
            decision.final_verdict,
            decision.conviction_score,
        )

        # ------------------------------------------------------------------
        # 11. Clean up Redis keys
        # ------------------------------------------------------------------
        r.delete(
            f"verdicts:{opportunity_id}",
            f"verdicts_counter:{opportunity_id}",
            f"opportunity:{opportunity_id}",
        )

    finally:
        r.close()
