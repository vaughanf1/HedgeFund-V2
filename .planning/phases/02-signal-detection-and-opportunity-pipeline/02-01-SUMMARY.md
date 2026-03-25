---
phase: 02-signal-detection-and-opportunity-pipeline
plan: 01
subsystem: database, signals, tasks
tags: [timescaledb, sqlalchemy, celery, celery-beat, alembic, window-functions, z-score]

# Dependency graph
requires:
  - phase: 01-infrastructure-and-data-foundation
    provides: PriceOHLCV hypertable, SyncSessionLocal, celery_app beat_schedule, alembic migration pattern

provides:
  - DetectedSignal ORM model with composite PK (detected_at, ticker, signal_type)
  - Alembic migration 0002 creating detected_signals hypertable with two composite indexes
  - detect_volume_spike: SQL window z-score over 20-day rolling average/stddev
  - detect_price_breakout: 20-day high/low breakout + gap detection with env-var threshold
  - detect_sector_momentum: sector peer comparison with minimum coverage guard
  - scan_market Celery task orchestrating all detectors across watchlist
  - Celery Beat scan-market entry (default 900s, configurable via SCAN_INTERVAL_SECONDS)

affects:
  - 02-02 (scorer, gate, remaining detectors build on DetectedSignal + scan_market scaffold)
  - 02-03 (opportunity queue + API reads from detected_signals hypertable)
  - 03 (agent fan-out triggered after signals pass gate)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - SQL window functions (ROWS BETWEEN N PRECEDING) for rolling statistics in TimescaleDB
    - Env-var threshold pattern for all signal parameters (configurable without code changes)
    - session.merge() for upsert semantics on composite-PK hypertable rows
    - try/except per-ticker in scan loop so one failure does not abort entire scan
    - from __future__ import annotations in all new modules (Python 3.9 compat, D-01-03-2)

key-files:
  created:
    - backend/app/db/models.py (DetectedSignal class appended)
    - backend/alembic/versions/0002_detected_signals.py
    - backend/app/signals/__init__.py
    - backend/app/signals/detectors/__init__.py
    - backend/app/signals/detectors/volume_spike.py
    - backend/app/signals/detectors/price_breakout.py
    - backend/app/signals/detectors/sector_momentum.py
    - backend/app/tasks/scan_market.py
  modified:
    - backend/app/tasks/celery_app.py

key-decisions:
  - "composite_score=None and passed_gate=False set on all signals — scorer and gate deferred to Plan 02"
  - "SECTOR_MAP loaded from env as JSON — no hardcoded sector assignments, allows runtime reconfiguration"
  - "SECTOR_MIN_COVERAGE guard (default 60%) prevents spurious signals when peer data is sparse"
  - "NULLIF(std_vol_20d, 0) + Python None check guards against zero-volume division"

patterns-established:
  - "Detector signature: detect_X(session, ticker) -> dict | None — uniform interface for scan_market to call"
  - "Signal dict shape: {signal_type, ticker, score, detail} — score always 0.0-1.0 range"
  - "All SQL as module-level text() constants — separates SQL from Python, enables easy inspection"
  - "Beat schedule entries use integer seconds + env var override — consistent pattern for all periodic tasks"

# Metrics
duration: 2min
completed: 2026-03-25
---

# Phase 2 Plan 01: Signal Detection Foundation Summary

**DetectedSignal hypertable, three SQL window-function detectors (volume z-score, price breakout, sector momentum), and a Celery Beat-driven scan_market task that persists raw signals to TimescaleDB.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-25T15:43:16Z
- **Completed:** 2026-03-25T15:45:30Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- DetectedSignal ORM model with composite primary key (detected_at, ticker, signal_type) and Alembic migration creating the hypertable with two performance indexes
- Three signal detectors using SQL window functions: volume spike (20-day z-score), price breakout (20-day range + gap), sector momentum (sector peer comparison with coverage guard)
- scan_market Celery task iterating the WATCHLIST env var, running all detectors, persisting signals via session.merge(), with per-ticker error isolation
- Celery Beat scan-market entry with configurable SCAN_INTERVAL_SECONDS (default 900s)

## Task Commits

1. **Task 1: DetectedSignal model + Alembic migration** - `fa456f5` (feat)
2. **Task 2: Signal detectors + scan_market + Beat entry** - `263222b` (feat)

## Files Created/Modified

- `backend/app/db/models.py` - DetectedSignal class appended; Boolean import added
- `backend/alembic/versions/0002_detected_signals.py` - Migration with create_hypertable, two indexes
- `backend/app/signals/__init__.py` - Package scaffold (empty)
- `backend/app/signals/detectors/__init__.py` - Package scaffold (empty)
- `backend/app/signals/detectors/volume_spike.py` - detect_volume_spike with 20-day rolling z-score SQL
- `backend/app/signals/detectors/price_breakout.py` - detect_price_breakout with breakout/gap SQL
- `backend/app/signals/detectors/sector_momentum.py` - detect_sector_momentum with peer comparison SQL
- `backend/app/tasks/scan_market.py` - Celery task orchestrating scan loop
- `backend/app/tasks/celery_app.py` - SCAN_INTERVAL var + scan-market beat entry added

## Decisions Made

- composite_score and passed_gate left as None/False for all signals — scorer and gate are Plan 02 scope; keeping them null-safe in the model avoids backfill complexity later
- SECTOR_MAP sourced from env JSON — allows runtime reconfiguration without redeploy; empty default means sector_momentum returns None for all tickers until configured
- SECTOR_MIN_COVERAGE guard at 60% — prevents momentum signals when fewer than 3/5 peers have data; configurable via env
- NULLIF(std_vol_20d, 0) guard in SQL plus Python None check for z_score — double-layered defence against zero-variance edge case

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

To activate sector momentum detection, set SECTOR_MAP env var as JSON, for example:

```
SECTOR_MAP='{"AAPL":"Technology","MSFT":"Technology","GOOGL":"Technology","AMZN":"Consumer Cyclical","NVDA":"Technology"}'
```

Without it, detect_sector_momentum returns None for all tickers (no error).

## Next Phase Readiness

- DetectedSignal hypertable migration is ready for `alembic upgrade head`
- scan_market task is wired into Celery Beat; will fire on schedule once worker is running
- Plan 02 can add scorer, gate, and remaining detectors (insider_cluster, news_catalyst) by extending scan_market's detector list and setting composite_score/passed_gate
- Plan 03 can read from detected_signals directly using the (ticker, detected_at) composite index

---
*Phase: 02-signal-detection-and-opportunity-pipeline*
*Completed: 2026-03-25*
