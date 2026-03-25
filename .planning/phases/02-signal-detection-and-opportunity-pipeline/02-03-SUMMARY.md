---
phase: 02-signal-detection-and-opportunity-pipeline
plan: "03"
subsystem: api
tags: [redis, fastapi, sqlalchemy, pydantic, opportunity-queue, signals-api]

# Dependency graph
requires:
  - phase: 02-signal-detection-and-opportunity-pipeline/02-01
    provides: DetectedSignal model, scan_market task skeleton, signal detectors foundation
  - phase: 02-signal-detection-and-opportunity-pipeline/02-02
    provides: composite scorer, quality gate, insider cluster, news catalyst, full scan_market wiring

provides:
  - Redis opportunity queue (enqueue_opportunity) with SET NX per-ticker dedup and configurable TTL
  - opportunity_queue Redis list for Phase 3 BLPOP consumption
  - FastAPI GET /api/v1/signals with ticker, signal_type, passed_gate filters (VIS-01)
  - FastAPI GET /api/v1/signals/{ticker} per-ticker endpoint (VIS-01)
  - detected_at timestamps on every signal response (VIS-04)
  - scan_market now enqueues gate-passed opportunities with enqueued_count in return dict

affects:
  - 03-agent-analysis-and-recommendation
  - 04-frontend-and-real-time-delivery

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Redis SET NX dedup pattern: opp:dedup:{ticker} key prevents duplicate Phase 3 analysis within configurable TTL window"
    - "Redis RPUSH list as work queue: Phase 3 agents BLPOP from opportunity_queue"
    - "FastAPI router prefix pattern: APIRouter with /api/v1 prefix registered via app.include_router"
    - "Pydantic v2 model_config from_attributes for SQLAlchemy ORM response serialization"

key-files:
  created:
    - backend/app/signals/queue.py
    - backend/app/routers/__init__.py
    - backend/app/routers/signals.py
  modified:
    - backend/app/tasks/scan_market.py
    - backend/app/main.py

key-decisions:
  - "json.dumps with default=str as safety net for Decimal/datetime in queue payloads — avoids silent serialization failures on edge-case signal detail values"
  - "Dedup is per-ticker (not per-signal-type) — Phase 3 agents analyze the full opportunity for a ticker, so one dedup key per ticker is correct"

patterns-established:
  - "Router registration: app.include_router(signals_router) at bottom of main.py after health endpoint"
  - "from __future__ import annotations in all new modules (project-wide decision from 01-03)"
  - "enqueue_opportunity returns bool — True=enqueued, False=duplicate. Callers log but do not error on False"

# Metrics
duration: 2min
completed: 2026-03-25
---

# Phase 2 Plan 03: Redis Opportunity Queue and Signals API Summary

**Redis SET NX per-ticker dedup queue feeding Phase 3 via BLPOP, plus FastAPI /api/v1/signals endpoints exposing raw detected signals with timestamps (VIS-01, VIS-04, SGNL-08 complete)**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-25T15:53:25Z
- **Completed:** 2026-03-25T15:55:14Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Redis dedup queue with `enqueue_opportunity(r, ticker, payload)` — SET NX on `opp:dedup:{ticker}` with configurable TTL (default 1h), RPUSH to `opportunity_queue`
- scan_market wired: gate-passed tickers enqueued, `enqueued_count` tracked in return dict and log
- FastAPI `GET /api/v1/signals` with optional filters: `ticker`, `signal_type`, `passed_gate`, `limit` (max 500)
- FastAPI `GET /api/v1/signals/{ticker}` per-ticker convenience endpoint (limit 200)
- Both endpoints return `SignalResponse` with `detected_at`, `score`, `composite_score`, `passed_gate` (all VIS-01/VIS-04 fields)
- Router registered in `main.py` via `app.include_router(signals_router)`

## Task Commits

Each task was committed atomically:

1. **Task 1: Redis opportunity queue with SET NX dedup + wire into scan_market** - `64c8c4e` (feat)
2. **Task 2: FastAPI signals read endpoints + router registration** - `2f1d1a3` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `backend/app/signals/queue.py` - enqueue_opportunity with Redis SET NX dedup and RPUSH to opportunity_queue
- `backend/app/routers/__init__.py` - routers package init (empty)
- `backend/app/routers/signals.py` - FastAPI router with list and per-ticker signal endpoints, SignalResponse Pydantic model
- `backend/app/tasks/scan_market.py` - Added enqueue_opportunity call after gate check, enqueued_count counter
- `backend/app/main.py` - Added from __future__ import annotations, signals_router import and include_router

## Decisions Made

- **json.dumps with `default=str`:** Used as a safety net when serializing opportunity payloads to Redis. Signal `detail` dicts contain floats and strings in normal operation, but `Decimal` values could appear if scorer returns them. `default=str` prevents silent serialization failures without requiring an explicit cast loop.
- **Dedup is per-ticker (not per-signal-type):** `opp:dedup:{ticker}` rather than `opp:dedup:{ticker}:{signal_type}`. Phase 3 agents receive the full ticker opportunity (all signals) via BLPOP — they don't need to be invoked once per signal type.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- Import verification with `python3 -c "from app.routers.signals import router"` failed locally because `app.db.engine` reads `DATABASE_URL` at module load time (pre-existing project behavior). Resolved by passing `DATABASE_URL` env var to the verification command. This is a known pattern in this codebase — works correctly in Docker context. Not a deviation.

## User Setup Required

None — no external service configuration required. Redis and PostgreSQL are existing infrastructure.

## Next Phase Readiness

- Phase 2 is fully complete: all five signal detectors, composite scorer, quality gate, Redis dedup queue, and signals API are implemented and committed.
- Phase 3 can immediately start consuming from `opportunity_queue` via `BLPOP opportunity_queue 0`.
- Dedup TTL is configurable via `OPPORTUNITY_DEDUP_TTL_SECONDS` env var — tune per production scan frequency.
- Signals API is queryable for all pipeline monitoring and frontend data needs.
- Blocker carried forward: LangGraph + Celery fan-out integration spike should be first task in Phase 3 (Plan 03-01).

---
*Phase: 02-signal-detection-and-opportunity-pipeline*
*Completed: 2026-03-25*
