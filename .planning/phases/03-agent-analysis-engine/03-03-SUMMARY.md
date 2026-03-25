---
phase: 03-agent-analysis-engine
plan: 03
subsystem: analysis
tags: [asymmetric-betting, committee-aggregation, regime-detection, cio-decision, celery, redis, sqlalchemy]

# Dependency graph
requires:
  - phase: 03-02
    provides: BLPOP consumer, five-agent fan-out, Redis HINCRBY fan-in, variance scoring, AgentVerdictRecord/CIODecisionRecord ORM, run_committee stub

provides:
  - asymmetric.py — evaluate_asymmetric() detecting 5x-10x opportunities (buy_count>=3, avg_confidence>=70)
  - committee.py — detect_regime() + aggregate_committee() with REGIME_WEIGHTS (4 regimes, per-persona influence multipliers)
  - cio.py — make_cio_decision() deterministic conviction→allocation→risk→verdict engine
  - run_committee fully wired — full 11-step pipeline replacing stub

affects:
  - 03-04 (SSE consumer needs COMMITTEE_COMPLETE and DECISION_MADE events — now published)
  - Phase 4 portfolio manager (consumes CIODecisionRecord rows and conviction_score/suggested_allocation_pct)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Regime-weighted committee voting — REGIME_WEIGHTS[regime][persona] multiplier applied to confidence score before averaging
    - Deterministic CIO — no LLM in final decision layer; pure rule-based tiers derived from weighted_conviction
    - Deferred imports in Celery task — analysis modules imported inside run_committee body to avoid circular import at module load

key-files:
  created:
    - backend/app/analysis/asymmetric.py
    - backend/app/analysis/committee.py
    - backend/app/analysis/cio.py
  modified:
    - backend/app/tasks/analyse_opportunity.py

key-decisions:
  - "fan_out stores opportunity dict in Redis (opportunity:{id}, TTL=24h) — run_committee reads it rather than relying on task arguments or re-queuing"
  - "Graceful degradation in run_committee when Redis opportunity key missing — reconstructs minimal dict from opportunity_id rather than crashing"
  - "Low variance warning does not block pipeline — committee proceeds even if agents converged sycophantically; variance is informational"
  - "Asymmetric 1.5x allocation multiplier capped at 10% — prevents runaway allocation on highly asymmetric plays"
  - "SPLIT consensus with conviction>=60 maps to MONITOR not PASS — acknowledges partial conviction without committing capital"

patterns-established:
  - "Regime detection from signal_type keywords — macro/fundamental/momentum keyword sets map signals to regime; default on no match"
  - "CIO allocation tiers: >=80→8%, >=65→5%, >=50→3%, >=35→1.5%, else 0%; asymmetric x1.5 capped at 10%"
  - "Kill conditions sourced from lowest-confidence agents first — pessimistic risk surfacing"

# Metrics
duration: 3min
completed: 2026-03-25
---

# Phase 3 Plan 03: Committee Aggregation + CIO Decision Engine Summary

**Regime-weighted committee aggregation (Dalio 1.5x macro, Buffett 1.5x fundamental, Cohen 1.5x momentum) feeding a deterministic CIO tier engine, with 10X asymmetric bet detection and full DB + event pipeline replacing the run_committee stub**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-25T19:32:58Z
- **Completed:** 2026-03-25T19:35:51Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Built `evaluate_asymmetric()` — detects 5x-10x opportunities when >=3 agents vote BUY with avg confidence >=70; extracts catalyst justification, probability score, payoff multiple, required conditions, and deduplicated risk flags
- Built `aggregate_committee()` with `detect_regime()` — infers market regime (macro/fundamental/momentum/default) from signal_type keywords, applies REGIME_WEIGHTS influence multipliers, computes weighted conviction, determines consensus (BUY/HOLD/PASS/SPLIT), identifies dissent agents
- Built `make_cio_decision()` — deterministic conviction-tier allocation (0-10%), variance-derived risk rating (LOW/MEDIUM/HIGH/VERY_HIGH), mode time horizon, key catalysts from BUY agents, kill conditions from lowest-confidence agents, final verdict (INVEST/MONITOR/PASS)
- Replaced run_committee stub with full 11-step pipeline: verdicts → variance check → opportunity load → asymmetric scoring → committee aggregation → COMMITTEE_COMPLETE event → CIO decision → DECISION_MADE event → DB persist (AgentVerdictRecord + CIODecisionRecord) → Redis cleanup
- Updated `fan_out` to store opportunity dict in Redis so run_committee can retrieve it without additional task arguments

## Task Commits

1. **Task 1: Asymmetric scoring + committee aggregation + CIO decision modules** - `a0dff65` (feat)
2. **Task 2: Wire run_committee with full pipeline — replace stub** - `cd34a82` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `backend/app/analysis/asymmetric.py` — evaluate_asymmetric() — 10X asymmetric bet detection
- `backend/app/analysis/committee.py` — detect_regime(), aggregate_committee(), REGIME_WEIGHTS constant
- `backend/app/analysis/cio.py` — make_cio_decision() — deterministic CIO engine
- `backend/app/tasks/analyse_opportunity.py` — fan_out updated + run_committee stub replaced with full pipeline

## Decisions Made

- **D-03-03-1:** `fan_out` stores opportunity dict in Redis under `opportunity:{id}` (TTL 24h). `run_committee` reads it via `r.get()`. Avoids passing large dicts through Celery task arguments, which can hit message broker size limits.
- **D-03-03-2:** Graceful degradation in `run_committee` when opportunity key missing — reconstructs minimal `{"ticker": ..., "detected_at": ...}` dict from the compound opportunity_id rather than raising.
- **D-03-03-3:** Low variance does not block pipeline. Committee proceeds even if agents converged. Variance is logged as warning and is informational; blocking would prevent any analysis when divergence is genuinely low.
- **D-03-03-4:** Asymmetric allocation multiplier (1.5x) capped at 10% — portfolio-level guard against runaway allocation on highly asymmetric plays.
- **D-03-03-5:** SPLIT consensus + conviction>=60 maps to MONITOR (not PASS) — partial conviction signals should not be silently discarded.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- COMMITTEE_COMPLETE and DECISION_MADE events are now published — Plan 03-04 (SSE consumer) can subscribe immediately
- CIODecisionRecord rows are persisted — Phase 4 portfolio manager can query `cio_decisions` table for `final_verdict`, `conviction_score`, `suggested_allocation_pct`
- All five persona agents (03-01) + fan-out pipeline (03-02) + committee engine (03-03) form a complete analysis chain
- No blockers for 03-04 or Phase 4

---
*Phase: 03-agent-analysis-engine*
*Completed: 2026-03-25*
