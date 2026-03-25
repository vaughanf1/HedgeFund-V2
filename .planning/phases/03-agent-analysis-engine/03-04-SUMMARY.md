---
phase: 03-agent-analysis-engine
plan: "04"
subsystem: api
tags: [fastapi, sse, redis, pubsub, sqlalchemy, pydantic, asyncio]

requires:
  - phase: 03-02
    provides: AgentVerdictRecord and CIODecisionRecord ORM models written by the pipeline worker

provides:
  - GET /api/v1/events/stream — SSE endpoint streaming pipeline:events Redis Pub/Sub channel
  - GET /api/v1/opportunities — ranked list of CIO decisions ordered by conviction_score desc
  - GET /api/v1/opportunities/{id} — full breakdown with all five agent verdicts and CIO decision
  - OpportunitySummary and OpportunityDetail Pydantic response models

affects:
  - phase-04-frontend
  - any downstream consumer needing real-time pipeline visibility

tech-stack:
  added: [sse-starlette, redis.asyncio (already in redis package)]
  patterns:
    - SSE via EventSourceResponse from sse_starlette wrapping an async generator
    - Redis Pub/Sub subscribe/listen pattern using redis.asyncio with finally cleanup
    - Pydantic response models with from_attributes for ORM mapping
    - Manual JSON parsing for nested JSONB-stored fields (decision_json, verdict_json)

key-files:
  created:
    - backend/app/routers/events.py
    - backend/app/routers/opportunities.py
  modified:
    - backend/app/main.py

key-decisions:
  - "sse_starlette.sse.EventSourceResponse wraps an async generator — client reconnect handled by EventSource API (browser scope)"
  - "DATABASE_URL env var required at import time via engine.py — local verification uses stub value; no code change needed"

patterns-established:
  - "SSE generator pattern: subscribe in try, yield in loop, unsubscribe+aclose in finally"
  - "Opportunities endpoints follow signals.py conventions: APIRouter prefix, Depends(get_session), desc() ordering"

duration: 5min
completed: 2026-03-25
---

# Phase 3 Plan 04: SSE Event Stream and Opportunities API Summary

**FastAPI SSE endpoint streaming Redis pipeline:events Pub/Sub to clients, plus ranked opportunities REST API with full per-opportunity agent/committee/CIO breakdown.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-25T00:00:00Z
- **Completed:** 2026-03-25T00:05:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- SSE endpoint (`GET /api/v1/events/stream`) subscribes to `pipeline:events` Redis channel via `redis.asyncio` and streams `event: pipeline` messages; proper cleanup on disconnect via `finally` block
- Opportunities list endpoint (`GET /api/v1/opportunities`) returns CIO decisions ranked by conviction_score descending with optional `final_verdict` filter and `limit` pagination (max 100)
- Opportunity detail endpoint (`GET /api/v1/opportunities/{id}`) returns full breakdown — all five agent verdicts ordered by persona, plus CIO decision JSON; 404 on unknown ID
- All three routers (signals, events, opportunities) registered in `main.py`

## Task Commits

Each task was committed atomically:

1. **Task 1: SSE event stream endpoint + opportunities API endpoints** - `3a135d5` (feat)
2. **Task 2: Register new routers in main.py** - `a0dff65` (feat)

**Plan metadata:** (see docs commit below)

## Files Created/Modified

- `backend/app/routers/events.py` — SSE endpoint subscribing to pipeline:events via redis.asyncio
- `backend/app/routers/opportunities.py` — List and detail endpoints for CIO decisions + agent verdicts
- `backend/app/main.py` — Added events_router and opportunities_router registrations

## Decisions Made

- **D-03-04-1:** `EventSourceResponse` from `sse_starlette` wraps the async generator — reconnect on disconnect is handled by the client's `EventSource` API (browser built-in, Phase 4 scope). Server simply streams without reconnect state.
- **D-03-04-2:** `risk_rating` extracted via `json.loads(row.decision_json).get("risk_rating", "UNKNOWN")` in `OpportunitySummary` — avoids adding a separate DB column for a field already in the JSON blob; graceful fallback on parse failure.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed sse-starlette locally for verification**
- **Found during:** Task 1 verification
- **Issue:** `sse_starlette` was in `requirements.txt` but not installed in the local Python 3.9 environment; `from sse_starlette.sse import EventSourceResponse` raised `ModuleNotFoundError`
- **Fix:** `pip3 install sse-starlette` — package already declared in requirements, environment was simply not set up for local testing
- **Files modified:** None (environment only)
- **Verification:** `from app.routers.events import router; print(len(router.routes))` printed 1
- **Committed in:** N/A (environment install, not committed)

---

**Total deviations:** 1 auto-fixed (1 blocking — local env missing package)
**Impact on plan:** Zero scope creep. Package was already in requirements.txt; local install was needed only for verification.

## Issues Encountered

- `DATABASE_URL` KeyError on local import of `app.db.deps` — engine.py raises at import time if env var absent. Resolved by prefixing verification command with `DATABASE_URL=postgresql+asyncpg://u:p@localhost/db`. No code change required; this is expected container-only behaviour.

## User Setup Required

None — no external service configuration required. Redis URL defaults to `redis://redis:6379/0` via `REDIS_URL` env var (already set in docker-compose).

## Next Phase Readiness

- Phase 4 frontend has all required API endpoints: `/api/v1/signals`, `/api/v1/events/stream`, `/api/v1/opportunities`, `/api/v1/opportunities/{id}`
- SSE stream is live once the container stack runs with Redis; no additional wiring needed
- Wave 3 (03-03 + 03-04) now complete — Phase 3 fully executed pending 03-03 parallel completion

---
*Phase: 03-agent-analysis-engine*
*Completed: 2026-03-25*
