# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-25)

**Core value:** The system discovers investment opportunities before the user has to think about them — a living alpha engine, not a reactive analyzer.
**Current focus:** Phase 3 in progress — Agent Analysis Engine

## Current Position

Phase: 3 of 4 (Agent Analysis Engine — IN PROGRESS)
Plan: 1 of 4 in current phase (03-01 complete)
Status: Executing Wave 2 next (plan 03-02)
Last activity: 2026-03-25 — Completed 03-01-PLAN (Pydantic schemas, LangGraph graph, structured output wrapper, event publisher)

Progress: [███████░░░] ~58% (7/12 estimated plans)

## Performance Metrics

**Velocity:**
- Total plans completed: 7
- Average duration: ~4 min
- Total execution time: ~28 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| Phase 1 | 3 | ~21 min | ~7 min |
| Phase 2 | 3 | ~6 min | ~2 min |

**Recent Trend:**
- Last 5 plans: 01-03 (~5 min), 02-01 (~2 min), 02-02 (~2 min), 02-03 (~2 min)
- Trend: Stable, accelerating on well-defined tasks

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Phase 1]: React moved to Vite SPA (not Next.js) — no SSR needed; React Flow + shadcn/ui + Tailwind v4
- [Phase 1]: TimescaleDB (not plain PostgreSQL) — handles both relational and time-series in one engine
- [Phase 1]: SSE (not WebSocket) — server-push only; bidirectionality adds complexity for no benefit
- [Phase 1]: Agent divergence via information asymmetry — must be designed into Phase 1 data partitioning, not patched later
- [Phase 1]: Signal quality gate before any LLM call — primary cost control; must exist before Phase 3
- [01-02 D-01-02-1]: httpx used instead of polygon-api-client in MassiveConnector — library not in requirements, httpx achieves identical result
- [01-02 D-01-02-2]: session.merge() for upsert in Celery tasks — correct upsert semantics on TimescaleDB composite PK
- [01-02 D-01-02-3]: FMP endpoint paths LOW CONFIDENCE — must verify /ratios-ttm, /income-statement, /balance-sheet-statement, /insider-trading, /stock_news against live FMP v3 docs before production use
- [01-03 D-01-03-1]: TYPE_CHECKING guard for FinancialSnapshot import — parallel execution with 01-02 avoids hard import failure at merge time
- [01-03 D-01-03-2]: `from __future__ import annotations` in all modules — local Python 3.9 vs container Python 3.12; PEP 563 makes union syntax portable
- [01-03 D-01-03-3]: Sync + async SpendTracker interface — Celery tasks (sync) and FastAPI routes (async) both need spend tracking
- [01-03 D-01-03-4]: Conservative pre-flight estimate ($0.003) for budget gate — exact cost unknown pre-call; estimate prevents overrun without over-blocking
- [02-01]: composite_score=None and passed_gate=False on all raw signals — scorer and gate deferred to Plan 02
- [02-01]: SECTOR_MAP sourced from env as JSON — empty default means sector_momentum silently skips until configured; avoids hardcoded sector assignments
- [02-01]: SECTOR_MIN_COVERAGE guard at 60% default — prevents momentum signals when peer data is sparse
- [02-02 D-02-02-1]: INTERVAL uses f-string injection at module load — PostgreSQL INTERVAL does not accept bind parameters
- [02-02 D-02-02-2]: ILIKE patterns injected as string literals — cannot parameterize ILIKE arrays in PostgreSQL
- [02-02 D-02-02-3]: Composite denominator = fired-signal weights only — prevents penalizing tickers where fewer detectors fire
- [02-02 D-02-02-4]: Redis instrumentation failures logged as warnings, not errors
- [02-03]: Dedup is per-ticker (not per-signal-type) — Phase 3 agents analyze full ticker opportunity via BLPOP
- [02-03]: json.dumps with default=str in enqueue_opportunity — safety net for Decimal/datetime edge cases in signal detail dicts — observability must not block scan correctness
- [03-01 D-03-01-1]: AgentVerdict schema imports used at top of wrapper.py (not TYPE_CHECKING guard) — schemas are used at runtime by messages.parse()
- [03-01 D-03-01-2]: publisher.py uses sync redis (not async) — called from synchronous Celery tasks; SSE consumer (Plan 03-04) uses redis.asyncio

### Pending Todos

- Verify FMP endpoint paths against live FMP v3 API documentation (D-01-02-3)
- Load-test session.merge() upsert on large OHLCV batches with TimescaleDB hypertable
- Update COST_PER_MTOK pricing table in spend_tracker.py when Anthropic changes pricing

### Blockers/Concerns

- [Pre-Phase 3]: LangGraph + Celery fan-out integration is not well-documented — plan a spike in Plan 03-01 before full implementation
- [Pre-Phase 3]: Celery Chord reliability — PITFALLS.md recommends avoiding Chord for agent fan-out; use individual tasks + Redis counter pattern instead
- [Pre-Phase 2]: Signal scoring thresholds are empirical — treat as configurable parameters from day one, instrument false-positive rate immediately
- [01-02]: FMP endpoint paths are low-confidence — validate before first real API run
- [01-03]: COST_PER_MTOK is hardcoded — consider a staleness-alert test in Phase 3

## Session Continuity

Last session: 2026-03-25
Stopped at: Completed 03-01-PLAN.md — Pydantic schemas, LangGraph graph, structured output wrapper, event publisher. Wave 1 complete.
Resume file: None
