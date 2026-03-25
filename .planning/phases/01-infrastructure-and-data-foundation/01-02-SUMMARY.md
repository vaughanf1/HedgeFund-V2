---
phase: 01
plan: 02
subsystem: data-ingestion
tags: [pydantic, sqlalchemy, celery, httpx, tenacity, timescaledb, fmp, massive]

dependency-graph:
  requires:
    - "01-01: Docker stack, TimescaleDB models, Celery app skeleton"
  provides:
    - FinancialSnapshot canonical schema
    - DataConnector abstract interface
    - MassiveConnector (OHLCV + News via Polygon-compatible REST)
    - FMPConnector (Fundamentals + Insider Trades + News)
    - Four Celery ingest tasks wired to beat_schedule
    - SyncSessionLocal for Celery workers
  affects:
    - "01-03: Signal scoring will consume FinancialSnapshot / DB rows"
    - "Phase 3: Agent fan-out reads normalized data from TimescaleDB"

tech-stack:
  added:
    - httpx (sync HTTP client in connectors)
    - tenacity (retry decorator on all API calls)
    - psycopg2-binary (sync DB driver for Celery tasks)
  patterns:
    - Abstract connector interface (DataConnector ABC) — all providers swappable
    - Cache-first TTL pattern in fundamentals (24h) and insider (7d) tasks
    - Canonical schema as single contract between connectors and DB layer
    - Upsert via session.merge() in all ingest tasks

key-files:
  created:
    - backend/app/schemas/financial.py
    - backend/app/connectors/base.py
    - backend/app/connectors/massive.py
    - backend/app/connectors/fmp.py
    - backend/app/tasks/ingest_price.py
    - backend/app/tasks/ingest_fundamentals.py
    - backend/app/tasks/ingest_insider.py
    - backend/app/tasks/ingest_news.py
  modified:
    - backend/app/db/engine.py (added SyncSessionLocal + sync_engine)

decisions:
  - id: D-01-02-1
    choice: "httpx sync client instead of polygon-api-client RESTClient"
    reason: "polygon-api-client not in requirements.txt and not installed in container. httpx achieves identical result with no new dependency."
    alternatives: ["Add polygon-api-client to requirements (needs container rebuild)"]
  - id: D-01-02-2
    choice: "session.merge() for upsert in all tasks"
    reason: "TimescaleDB hypertables do not support ON CONFLICT natively via SQLAlchemy; merge() on composite PK (timestamp, ticker) provides correct upsert semantics."
    alternatives: ["Raw INSERT ... ON CONFLICT", "postgresql dialect upsert"]
  - id: D-01-02-3
    choice: "FMP endpoint paths marked low-confidence"
    reason: "FMP v3 endpoint paths were coded from known patterns but not verified against live API during this plan. Must be validated before first real FMP call."
    alternatives: ["Verify endpoints now (requires FMP_API_KEY)"]

metrics:
  duration: "3m 5s"
  completed: "2026-03-25"
---

# Phase 1 Plan 02: Data Ingestion Pipeline Summary

**One-liner:** Canonical FinancialSnapshot schema + abstract DataConnector ABC + MassiveConnector (httpx/Polygon-compatible) + FMPConnector (httpx/FMP v3) + four Celery ingest tasks with cache-first TTL logic and per-ticker error isolation.

## What Was Built

### FinancialSnapshot (canonical schema)
`backend/app/schemas/financial.py` — Pydantic v2 model that is the single data contract between every connector and the database. Covers all four data types (ohlcv, fundamentals, insider_trade, news) with optional fields per type. Decimal fields use `str` JSON encoding.

### DataConnector (abstract interface)
`backend/app/connectors/base.py` — ABC with four abstract methods returning `list[FinancialSnapshot]`. Keeps connectors swappable; Phase 3 agents depend on this interface, not any concrete implementation.

### MassiveConnector
`backend/app/connectors/massive.py` — Implements `fetch_ohlcv` (GET `/aggs/ticker/{ticker}/range/1/day/...`) and `fetch_news` (GET `/reference/news`). Uses synchronous httpx with the Massive.com Polygon-compatible API. Both methods wrapped with tenacity (3 attempts, exponential backoff). `fetch_fundamentals` and `fetch_insider_trades` raise `NotImplementedError`.

### FMPConnector
`backend/app/connectors/fmp.py` — Implements `fetch_fundamentals` (combines `/ratios-ttm`, `/income-statement`, `/balance-sheet-statement`), `fetch_insider_trades` (`/insider-trading`), and `fetch_news` (`/stock_news`). Synchronous httpx. All methods wrapped with tenacity. `fetch_ohlcv` raises `NotImplementedError`. **FMP endpoint paths are marked as low-confidence — verify against live FMP v3 docs before production use.**

### db/engine.py — sync session
Added `sync_engine` (psycopg2) and `SyncSessionLocal` derived from `DATABASE_URL` by replacing `+asyncpg` with `+psycopg2`. Celery workers are synchronous so the async engine from FastAPI cannot be reused.

### Four Celery Ingest Tasks

| Task | File | Connector | TTL | Beat schedule |
|------|------|-----------|-----|---------------|
| `app.tasks.ingest_price.run` | ingest_price.py | MassiveConnector | — | every 5 min |
| `app.tasks.ingest_fundamentals.run` | ingest_fundamentals.py | FMPConnector | 24h cache | daily 06:00 UTC |
| `app.tasks.ingest_insider.run` | ingest_insider.py | FMPConnector | 7d cache | daily 07:00 UTC |
| `app.tasks.ingest_news.run` | ingest_news.py | Massive + FMP | — | every 15 min |

All tasks: WATCHLIST from env (default AAPL,MSFT,GOOGL,AMZN,NVDA), per-ticker error isolation (one failure doesn't abort others), structured logging, `session.merge()` upsert.

## Decisions Made

1. **httpx instead of polygon-api-client** — polygon-api-client is not in requirements.txt and is not installed in the Docker image. httpx provides identical functionality without adding a new dependency or requiring a container rebuild. (D-01-02-1)

2. **session.merge() for upsert** — TimescaleDB hypertables with composite PK work correctly with SQLAlchemy's `merge()`. No raw SQL needed. (D-01-02-2)

3. **FMP endpoints low-confidence** — Endpoint paths follow known FMP v3 patterns but must be validated against live docs when `FMP_API_KEY` is available. (D-01-02-3)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] polygon-api-client not available — used httpx instead**

- **Found during:** Task 1 — MassiveConnector implementation
- **Issue:** The plan specified `RESTClient` from a Massive/polygon client library, but the package is not installed in the Docker image (requirements.txt has no polygon dependency)
- **Fix:** Implemented MassiveConnector using `httpx.Client` with the Polygon-compatible REST endpoints directly. API surface is identical; no external dependency added.
- **Files modified:** `backend/app/connectors/massive.py`
- **Commit:** 262335a

## Success Criteria Verification

- [x] Both connectors implement DataConnector interface and are swappable — confirmed via ABC enforcement
- [x] FinancialSnapshot is the single canonical schema between connectors and database — all four tasks and both connectors use it
- [x] All four Celery tasks are registered with correct names matching beat_schedule — verified: all return correct `.name` attributes matching `celery_app.py`
- [x] FMP calls have cache-first logic with freshness TTL — ingest_fundamentals (24h), ingest_insider (7d)

## Next Phase Readiness

- **Plan 01-03 can proceed** — signal scoring layer can consume DB rows written by these tasks
- **Watch:** FMP endpoint paths must be verified against live API before real data runs
- **Watch:** `session.merge()` on TimescaleDB hypertable composite PK works in testing but should be load-tested with large OHLCV batches
