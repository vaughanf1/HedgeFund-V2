---
phase: 02
plan: 02
subsystem: signal-detection
tags: [signals, scoring, quality-gate, redis, celery, postgresql, sqlalchemy]

dependency-graph:
  requires:
    - "02-01: DetectedSignal model, volume_spike, price_breakout, sector_momentum, scan_market skeleton"
  provides:
    - "insider_cluster detector (SGNL-03)"
    - "news_catalyst detector (SGNL-04)"
    - "composite scorer (SGNL-06)"
    - "quality gate (SGNL-07)"
    - "fully wired scan_market task (SGNL-08 complete)"
  affects:
    - "02-03: downstream consumers can filter detected_signals WHERE passed_gate = true"
    - "Phase 3: LLM agent invocation gated on passed_gate — primary cost control"

tech-stack:
  added: []
  patterns:
    - "Dynamic SQL INTERVAL injection via f-string (not bind param) for PostgreSQL compatibility"
    - "Keyword ILIKE clause built at module load from env var — avoids per-query string construction"
    - "Weighted composite score with normalized denominator — handles partial signal fires correctly"
    - "Redis instrumentation with TTL — scan metrics visible without DB query"

key-files:
  created:
    - backend/app/signals/detectors/insider_cluster.py
    - backend/app/signals/detectors/news_catalyst.py
    - backend/app/signals/scorer.py
    - backend/app/signals/quality_gate.py
  modified:
    - backend/app/tasks/scan_market.py

decisions:
  - id: D-02-02-1
    summary: "INTERVAL uses f-string injection, min_insiders uses bind param"
    rationale: "PostgreSQL INTERVAL does not accept bind parameters. Window days injected at module load (constant for process lifetime). min_insiders stays parameterized for query plan safety."
  - id: D-02-02-2
    summary: "ILIKE patterns injected as string literals, not bind params"
    rationale: "PostgreSQL cannot parameterize arrays of ILIKE patterns. Keywords are env-var configured and stable for process lifetime; injection is safe."
  - id: D-02-02-3
    summary: "Composite denominator = sum of weights of FIRED signals only (not all five)"
    rationale: "Normalizing against total possible weight would penalize tickers where fewer detectors fire. Using fired-signal weight preserves score integrity when only 1-2 signals trigger."
  - id: D-02-02-4
    summary: "Redis instrumentation failures logged as warnings, not errors"
    rationale: "Instrumentation is observability, not correctness. A Redis outage must not fail the scan task — scan results are committed to DB regardless."

metrics:
  duration: "~2 min"
  completed: "2026-03-25"
---

# Phase 2 Plan 02: Insider Cluster, News Catalyst, Composite Scorer, Quality Gate Summary

**One-liner:** Weighted composite scorer with 0.35 quality gate gates all five signal types before LLM invocation, using ILIKE keyword news detection and COUNT DISTINCT insider cluster analysis.

## What Was Built

This plan completes the signal detection and filtering pipeline:

1. **insider_cluster.py (SGNL-03)** — Detects buying clusters of 2+ distinct insiders within a configurable rolling window (default 30 days). Uses `COUNT(DISTINCT insider_name)` with a dynamically injected INTERVAL. Score normalized: 4+ insiders = 1.0.

2. **news_catalyst.py (SGNL-04)** — Detects keyword-matching news in the last 48 hours using a dynamically built ILIKE OR clause. Score applies recency decay: `base_score * max(0.2, 1.0 - hours_since_latest / 48.0)`. Does NOT filter on sentiment (column is unpopulated).

3. **scorer.py (SGNL-06)** — `compute_composite_score(signals)` produces a weighted 0.0-1.0 from all fired signals. Denominator is sum of weights of fired signals only — partial fire does not distort score. Empty list or all-unknown types returns 0.0.

4. **quality_gate.py (SGNL-07)** — `passes_gate(composite_score)` returns True when score >= SIGNAL_QUALITY_GATE (default 0.35). Primary cost control before Phase 3 LLM calls.

5. **scan_market.py (SGNL-08 complete)** — Now runs all five detectors, computes composite score, applies gate, and persists `composite_score` and `passed_gate` on every signal record. Writes three Redis instrumentation keys (`scanner:last_pass_rate`, `scanner:last_scan_at`, `scanner:last_total`) with 1h TTL after each scan.

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| D-02-02-1 | INTERVAL uses f-string injection at module load | PostgreSQL INTERVAL does not accept bind parameters |
| D-02-02-2 | ILIKE patterns injected as string literals | Cannot parameterize ILIKE arrays in PostgreSQL |
| D-02-02-3 | Composite denominator = fired-signal weights only | Prevents penalizing tickers where fewer detectors fire |
| D-02-02-4 | Redis failures are warnings, not errors | Observability must not block scan correctness |

## Deviations from Plan

None — plan executed exactly as written.

## Environment Variables (all configurable)

| Variable | Default | Module |
|----------|---------|--------|
| MIN_INSIDER_CLUSTER_SIZE | 2 | insider_cluster.py |
| INSIDER_CLUSTER_WINDOW_DAYS | 30 | insider_cluster.py |
| NEWS_CATALYST_KEYWORDS | earnings,surprise,partnership,... | news_catalyst.py |
| WEIGHT_VOLUME_SPIKE | 0.25 | scorer.py |
| WEIGHT_PRICE_BREAKOUT | 0.25 | scorer.py |
| WEIGHT_INSIDER_CLUSTER | 0.20 | scorer.py |
| WEIGHT_NEWS_CATALYST | 0.20 | scorer.py |
| WEIGHT_SECTOR_MOMENTUM | 0.10 | scorer.py |
| SIGNAL_QUALITY_GATE | 0.35 | quality_gate.py |
| REDIS_URL | redis://redis:6379/0 | scan_market.py |

## Next Phase Readiness

- All five detectors are operational; scan_market is fully wired
- `detected_signals` rows now carry `composite_score` and `passed_gate=True/False`
- Phase 3 can filter `WHERE passed_gate = true` to select candidates for LLM analysis
- Signal scoring thresholds remain empirical — instrument false-positive rate once real data flows (see Blockers/Concerns)
