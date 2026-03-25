---
phase: "03-agent-analysis-engine"
plan: "02"
subsystem: "agent-pipeline"
tags: ["celery", "redis", "langgraph", "fan-out", "fan-in", "variance", "timescaledb", "alembic"]

dependency_graph:
  requires: ["03-01"]
  provides: ["analyse_opportunity tasks", "variance scoring", "AgentVerdictRecord", "CIODecisionRecord", "migration 0003"]
  affects: ["03-03", "03-04"]

tech_stack:
  added: ["nest_asyncio"]
  patterns: ["Redis HINCRBY atomic counter fan-in", "asyncio bridge for sync Celery tasks", "LangGraph invocation via asyncio.run()", "TimescaleDB hypertable ORM with composite PK"]

key_files:
  created:
    - backend/app/tasks/analyse_opportunity.py
    - backend/app/analysis/__init__.py
    - backend/app/analysis/variance.py
    - backend/alembic/versions/0003_agent_verdicts.py
  modified:
    - backend/app/db/models.py

decisions:
  - id: "03-02-D-1"
    summary: "TYPE_CHECKING guard for AgentVerdict in variance.py — imported at runtime by compute_variance_score, used only in type hints; guard prevents circular import if schemas imports from analysis in future"
  - id: "03-02-D-2"
    summary: "nest_asyncio fallback in _run_graph_sync — handles test environments with running event loops without failing silently"
  - id: "03-02-D-3"
    summary: "run_committee deferred-imported variance module — avoids circular import between tasks and analysis packages at module load time"

metrics:
  duration: "~4 min"
  completed: "2026-03-25"
---

# Phase 3 Plan 02: Five-Agent Fan-Out Pipeline Summary

**One-liner:** BLPOP consumer dispatches five parallel Celery agent tasks; Redis HINCRBY counter fans-in to committee; std-dev variance scoring rejects sycophantic consensus.

**Status:** Complete
**Started:** 2026-03-25
**Completed:** 2026-03-25

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | BLPOP consumer + fan-out + run_persona_agent + run_committee (stub) | 67d4480 | backend/app/tasks/analyse_opportunity.py |
| 2 | Variance scoring + AgentVerdictRecord/CIODecisionRecord ORM + migration 0003 | 0903da2 | backend/app/analysis/variance.py, backend/app/db/models.py, alembic/versions/0003_agent_verdicts.py |

## Deliverables

- **consume_queue** — Long-running Celery task; BLPOP-blocks on `opportunity_queue` (key from Phase 2 `OPP_QUEUE_KEY`); dispatches `fan_out` per dequeue.
- **fan_out** — Dispatches exactly 5 `run_persona_agent` tasks in parallel; one per persona (buffett, munger, ackman, cohen, dalio). Opportunity ID: `ticker:detected_at` compound key.
- **run_persona_agent** — Invokes `PERSONA_GRAPH.ainvoke()` via `asyncio.run()` bridge; persists `AgentVerdict` to Redis hash `verdicts:<opportunity_id>`; increments `HINCRBY` atomic counter; publishes `AGENT_STARTED` and `AGENT_COMPLETE` events; triggers `run_committee` when counter reaches 5. Max retries: 3, countdown: 30s.
- **run_committee** — Stub for Plan 03-03; loads all verdicts from Redis hash, calls variance scoring, logs validity. Full committee aggregation deferred.
- **compute_variance_score** — Returns `statistics.stdev()` of confidence scores across verdicts. Returns 0.0 if fewer than 2 verdicts.
- **is_committee_valid** — Returns `variance >= MINIMUM_VARIANCE_THRESHOLD` (default 8.0, configurable via `AGENT_VARIANCE_THRESHOLD` env var).
- **AgentVerdictRecord** — TimescaleDB hypertable ORM; composite PK `(analysed_at, opportunity_id, persona)`.
- **CIODecisionRecord** — TimescaleDB hypertable ORM; composite PK `(decided_at, opportunity_id)`.
- **Migration 0003** — Creates `agent_verdicts` and `cio_decisions` tables; down_revision=0002.

## Decisions Made

| ID | Decision |
|----|----------|
| 03-02-D-1 | `TYPE_CHECKING` guard for `AgentVerdict` in variance.py — used only in type hints at runtime; prevents future circular import if schemas imports analysis |
| 03-02-D-2 | `nest_asyncio` fallback in `_run_graph_sync` — handles test environments with running event loops |
| 03-02-D-3 | `run_committee` deferred-imports variance module — avoids circular import between tasks and analysis packages at module load |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] langgraph not installed in local Python 3.9 environment**

- **Found during:** Task 1 verification
- **Issue:** `from app.agents.graph import PERSONA_GRAPH` failed with `ModuleNotFoundError: No module named 'langgraph'` — local dev machine uses system Python 3.9; packages are normally installed in Docker container.
- **Fix:** Installed `langgraph` (latest compatible version for Python 3.9), `langchain-anthropic`, and `nest_asyncio` via pip3 into local user site-packages. requirements.txt unchanged (already correct for container).
- **Files modified:** None (system-level install)
- **Commit:** No separate commit (prerequisite fix, not code change)

## Next Phase Readiness

Plan 03-03 (Committee Aggregation + CIO Decision) can proceed immediately:
- `run_committee` stub is in place with correct Redis key reading and variance checks
- `AgentVerdictRecord` and `CIODecisionRecord` ORM models ready
- `CIODecisionRecord` and `CIODecision` Pydantic schema available from 03-01
- All five agent tasks produce `AgentVerdict`-keyed Redis hashes with 24h TTL
