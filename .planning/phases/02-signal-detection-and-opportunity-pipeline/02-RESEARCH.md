# Phase 02: Signal Detection and Opportunity Pipeline - Research

**Researched:** 2026-03-25
**Domain:** Statistical signal detection on TimescaleDB time-series, Celery Beat scheduler, Redis idempotency queuing, FastAPI read endpoints
**Confidence:** HIGH for Celery/Redis patterns; HIGH for TimescaleDB SQL patterns; MEDIUM for signal scoring thresholds (empirical by nature)

---

## Summary

Phase 02 builds on the Phase 01 stack without adding any new core dependencies. The entire phase runs inside the existing Celery/Redis/TimescaleDB/FastAPI stack. The primary work is: (1) new Celery Beat entries for a 15-minute market scanner, (2) SQL-based signal detectors that query the existing hypertables using PostgreSQL window functions and z-scores, (3) a composite scorer and quality gate that runs in Python before any Redis enqueue, and (4) Redis SET NX deduplication for the opportunity queue. FastAPI read endpoints for VIS-01 and VIS-04 are straightforward async queries against the new `detected_signals` table.

The most important architectural decision is where signal detection logic lives. The correct answer is: pure SQL window-function queries executed inside Celery tasks. No external statistical library is needed — TimescaleDB/PostgreSQL stddev, AVG, and LAG window functions are sufficient for all five detector types. The scoring aggregation is plain Python arithmetic on the detector outputs. This keeps the stack minimal and avoids a numpy/pandas dependency in the Celery image.

The pre-phase blocker "signal scoring thresholds are empirical" is real and must be addressed architecturally: every threshold must be an environment variable from day one, and a false-positive rate counter must be written to a Redis gauge on every scan so it is queryable without reading the database.

**Primary recommendation:** Add `detected_signals` hypertable (new Alembic migration), add 5 SQL-based detector functions, add composite scorer with configurable env-var thresholds, add Redis SET NX opportunity queue, add Celery Beat entry for 15-minute scan, add FastAPI `GET /api/v1/signals` endpoint. No new Python packages required.

---

## Standard Stack

### Core (no new packages — all already in requirements.txt)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| celery[redis] | 5.6.2 | Beat scheduler + scan worker | Already in stack; beat_schedule entry is the only addition |
| redis-py | latest | Opportunity queue deduplication via SET NX | Already in stack; atomic NX prevents race conditions |
| sqlalchemy[asyncio] | 2.0.x | Async session for FastAPI; sync session for Celery tasks | Already in stack; window functions via `text()` or `func` |
| asyncpg | latest | Async PostgreSQL driver for FastAPI endpoints | Already in stack |
| psycopg2-binary | latest | Sync PostgreSQL driver for Celery task detectors | Already in stack |
| fastapi | 0.115.2 | Read endpoints for signals (VIS-01, VIS-04) | Already in stack |
| pydantic | v2 | Response schemas for signal endpoints | Already in stack |

### Supporting (no new packages needed)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tenacity | latest | Retry DB queries in signal detectors | Already in stack; wrap any external-data reads |
| python-dotenv | latest | Load threshold env vars at runtime | Already in stack |

### New Python Packages Required

**None.** All Phase 02 functionality is achievable with the existing requirements.txt. The detection logic uses raw SQL window functions; scoring uses Python arithmetic; Redis deduplication uses the existing redis-py client.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw SQL window functions in Celery tasks | pandas/numpy in-memory | SQL runs where the data lives; no memory copy of full OHLCV history; simpler image; already have psycopg2 |
| Redis SET NX for dedup | Celery task signatures with `unique_on` (celery-singleton) | SET NX is explicit, controllable, zero extra dependency; celery-singleton adds complexity for a trivially simple use case |
| Plain `detected_signals` table | TimescaleDB hypertable | Signals have timestamps; hypertable gives time-based partitioning for free; consistent with Phase 01 patterns |
| Hardcoded scoring weights | ML model | Thresholds are empirical; ML adds Phase 3 complexity; configurable env vars achieve the same observability goal |

---

## Architecture Patterns

### Recommended Project Structure Addition

```
backend/app/
├── signals/
│   ├── __init__.py
│   ├── detectors/
│   │   ├── __init__.py
│   │   ├── volume_spike.py        # SGNL-01: z-score on volume vs 20-day avg
│   │   ├── price_breakout.py      # SGNL-02: close vs rolling high/low
│   │   ├── insider_cluster.py     # SGNL-03: count buys within 30-day window
│   │   ├── news_catalyst.py       # SGNL-04: news item age + sentiment filter
│   │   └── sector_momentum.py     # SGNL-05: relative strength vs sector average
│   ├── scorer.py                  # SGNL-06: composite score from detector outputs
│   ├── quality_gate.py            # SGNL-07: threshold filter before Redis enqueue
│   └── queue.py                   # Redis SET NX opportunity queue with dedup
├── tasks/
│   ├── celery_app.py              # Add scan_market beat entry
│   └── scan_market.py             # SGNL-08: orchestrating Celery task
db/
├── models.py                      # Add DetectedSignal model
alembic/versions/
└── 0002_detected_signals.py       # New hypertable migration
routers/
└── signals.py                     # VIS-01, VIS-04: GET /api/v1/signals
```

### Pattern 1: DetectedSignal ORM Model (TimescaleDB hypertable)

**What:** A new hypertable storing every signal that passes any individual detector, before the quality gate. Score, detection type, and timestamp are all first-class columns — this satisfies VIS-01 (raw signals viewable) and VIS-04 (timestamps on every event).

**When to use:** Write one row per detected signal per ticker per scan run.

```python
# Source: Consistent with Phase 01 hypertable pattern (01-RESEARCH.md Pattern 3)
# backend/app/db/models.py — add to existing file

class DetectedSignal(Base):
    """Detected market signal — TimescaleDB hypertable on detected_at."""

    __tablename__ = "detected_signals"
    __table_args__ = {
        "timescaledb_hypertable": {"time_column_name": "detected_at"},
    }

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    ticker: Mapped[str] = mapped_column(String(20), primary_key=True)
    signal_type: Mapped[str] = mapped_column(
        String(50), primary_key=True
    )  # "volume_spike" | "price_breakout" | "insider_cluster" | "news_catalyst" | "sector_momentum"
    score: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    composite_score: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    passed_gate: Mapped[bool] = mapped_column(nullable=False, default=False)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON blob
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="scanner")
```

**Migration:** Add `0002_detected_signals.py` Alembic migration with `create_hypertable('detected_signals', 'detected_at')` and a composite index on `(ticker, detected_at)`.

### Pattern 2: Volume Spike Detector (SQL Window Function Z-Score)

**What:** Query `price_ohlcv` using a rolling window to compute the z-score of today's volume vs the 20-day average. Fire signal if z-score exceeds the configurable threshold.

**When to use:** Called from the market scanner Celery task per ticker.

```python
# Source: SQL pattern verified via WebSearch (TimescaleDB window function z-score)
# backend/app/signals/detectors/volume_spike.py

from sqlalchemy import text
from decimal import Decimal
import os

VOLUME_ZSCORE_THRESHOLD = float(os.environ.get("VOLUME_ZSCORE_THRESHOLD", "2.0"))

VOLUME_SPIKE_SQL = text("""
    WITH recent AS (
        SELECT
            ticker,
            timestamp,
            volume,
            AVG(volume) OVER (
                PARTITION BY ticker
                ORDER BY timestamp
                ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
            ) AS avg_vol_20d,
            STDDEV_SAMP(volume) OVER (
                PARTITION BY ticker
                ORDER BY timestamp
                ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
            ) AS std_vol_20d
        FROM price_ohlcv
        WHERE ticker = :ticker
          AND timestamp >= NOW() - INTERVAL '30 days'
        ORDER BY timestamp DESC
    ),
    latest AS (
        SELECT *,
            (volume - avg_vol_20d) / NULLIF(std_vol_20d, 0) AS z_score
        FROM recent
        LIMIT 1
    )
    SELECT ticker, timestamp, volume, avg_vol_20d, std_vol_20d, z_score
    FROM latest
    WHERE z_score >= :threshold
""")

def detect_volume_spike(session, ticker: str) -> dict | None:
    """Return signal dict if volume z-score exceeds threshold, else None."""
    row = session.execute(
        VOLUME_SPIKE_SQL,
        {"ticker": ticker, "threshold": VOLUME_ZSCORE_THRESHOLD}
    ).fetchone()

    if row is None:
        return None

    return {
        "signal_type": "volume_spike",
        "ticker": ticker,
        "score": min(float(row.z_score) / 3.0, 1.0),  # normalize to 0-1
        "detail": {
            "z_score": float(row.z_score),
            "volume": row.volume,
            "avg_vol_20d": float(row.avg_vol_20d or 0),
        },
    }
```

### Pattern 3: Price Breakout Detector (Rolling High/Low)

**What:** Detects close price breaking out above the 20-day rolling high (bullish breakout) or below the 20-day rolling low (bearish breakout). Also handles gap-ups/downs via LAG comparison.

```python
# Source: SQL LAG and window function pattern verified via multiple sources
# backend/app/signals/detectors/price_breakout.py

PRICE_BREAKOUT_SQL = text("""
    WITH windowed AS (
        SELECT
            ticker,
            timestamp,
            close,
            MAX(close) OVER (
                PARTITION BY ticker
                ORDER BY timestamp
                ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
            ) AS high_20d,
            MIN(close) OVER (
                PARTITION BY ticker
                ORDER BY timestamp
                ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
            ) AS low_20d,
            LAG(close) OVER (PARTITION BY ticker ORDER BY timestamp) AS prev_close
        FROM price_ohlcv
        WHERE ticker = :ticker
          AND timestamp >= NOW() - INTERVAL '30 days'
        ORDER BY timestamp DESC
    )
    SELECT
        ticker, timestamp, close, high_20d, low_20d, prev_close,
        CASE
            WHEN close > high_20d THEN 'breakout_up'
            WHEN close < low_20d THEN 'breakout_down'
            WHEN prev_close IS NOT NULL
                 AND (close - prev_close) / NULLIF(prev_close, 0) > :gap_threshold
                 THEN 'gap_up'
            WHEN prev_close IS NOT NULL
                 AND (close - prev_close) / NULLIF(prev_close, 0) < (:gap_threshold * -1)
                 THEN 'gap_down'
            ELSE NULL
        END AS breakout_type
    FROM windowed
    LIMIT 1
""")
```

### Pattern 4: Insider Buying Cluster Detector

**What:** Counts `buy` trades in `insider_trades` for a ticker within a rolling window (default 30 days). A cluster is 2+ distinct insiders buying in that window.

```python
# Source: SQL COUNT DISTINCT pattern on insider_trades hypertable
# backend/app/signals/detectors/insider_cluster.py

INSIDER_CLUSTER_SQL = text("""
    SELECT
        ticker,
        COUNT(DISTINCT insider_name) AS unique_buyers,
        SUM(CASE WHEN trade_type = 'buy' THEN shares ELSE 0 END) AS total_shares_bought,
        MIN(timestamp) AS first_buy,
        MAX(timestamp) AS last_buy
    FROM insider_trades
    WHERE ticker = :ticker
      AND trade_type = 'buy'
      AND timestamp >= NOW() - INTERVAL '30 days'
    GROUP BY ticker
    HAVING COUNT(DISTINCT insider_name) >= :min_insiders
""")

MIN_INSIDER_CLUSTER_SIZE = int(os.environ.get("MIN_INSIDER_CLUSTER_SIZE", "2"))
```

### Pattern 5: News Catalyst Detector

**What:** Checks `news_items` for recent articles with `sentiment = 'positive'` and keywords indicating high-impact catalysts (earnings, partnership, FDA, acquisition). Recency decay: articles older than 2 days score lower.

```python
# Source: SQL pattern on news_items hypertable; keyword list is configurable
# backend/app/signals/detectors/news_catalyst.py

NEWS_CATALYST_SQL = text("""
    SELECT
        ticker,
        COUNT(*) AS recent_articles,
        SUM(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END) AS positive_count,
        MAX(timestamp) AS most_recent,
        EXTRACT(EPOCH FROM (NOW() - MAX(timestamp))) / 3600 AS hours_since_latest
    FROM news_items
    WHERE ticker = :ticker
      AND timestamp >= NOW() - INTERVAL '48 hours'
      AND (
          headline ILIKE '%earnings%' OR headline ILIKE '%surprise%'
          OR headline ILIKE '%partnership%' OR headline ILIKE '%acquisition%'
          OR headline ILIKE '%FDA%' OR headline ILIKE '%approval%'
          OR headline ILIKE '%revenue%' OR headline ILIKE '%upgrade%'
      )
    GROUP BY ticker
    HAVING COUNT(*) >= 1
""")
```

**Note:** The keyword list must be configurable. Store it as a comma-separated env var `NEWS_CATALYST_KEYWORDS` and build the ILIKE clause dynamically.

### Pattern 6: Sector Momentum Detector

**What:** Computes each ticker's relative strength vs its sector peers within the watchlist. If a ticker's 5-day return exceeds the sector median by a configurable margin, it signals sector momentum.

**Implementation approach:** Two SQL queries — (1) compute 5-day return for all tickers in the watchlist, (2) compare each ticker vs sector median. Sector membership is defined via a `SECTOR_MAP` env var (`AAPL:tech,MSFT:tech,JPM:financial`).

```sql
-- Step 1: 5-day return per ticker
SELECT ticker,
    (MAX(CASE WHEN rn = 1 THEN close END) -
     MAX(CASE WHEN rn = 6 THEN close END))
    / NULLIF(MAX(CASE WHEN rn = 6 THEN close END), 0) AS return_5d
FROM (
    SELECT ticker, close,
        ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY timestamp DESC) AS rn
    FROM price_ohlcv
    WHERE ticker = ANY(:tickers)
      AND timestamp >= NOW() - INTERVAL '10 days'
) ranked
WHERE rn IN (1, 6)
GROUP BY ticker
```

### Pattern 7: Composite Scorer

**What:** Takes outputs from all five detectors for a ticker and computes a weighted sum. Weights are configurable env vars. Returns composite score (0.0–1.0) and a list of contributing signals.

```python
# backend/app/signals/scorer.py
import os

WEIGHTS = {
    "volume_spike":    float(os.environ.get("WEIGHT_VOLUME_SPIKE", "0.25")),
    "price_breakout":  float(os.environ.get("WEIGHT_PRICE_BREAKOUT", "0.25")),
    "insider_cluster": float(os.environ.get("WEIGHT_INSIDER_CLUSTER", "0.20")),
    "news_catalyst":   float(os.environ.get("WEIGHT_NEWS_CATALYST", "0.20")),
    "sector_momentum": float(os.environ.get("WEIGHT_SECTOR_MOMENTUM", "0.10")),
}

def compute_composite_score(signals: list[dict]) -> float:
    """
    signals: list of {signal_type: str, score: float (0-1)}
    Returns weighted composite score 0.0-1.0.
    """
    total_weight = sum(WEIGHTS[s["signal_type"]] for s in signals if s["signal_type"] in WEIGHTS)
    if total_weight == 0:
        return 0.0
    weighted_sum = sum(
        s["score"] * WEIGHTS.get(s["signal_type"], 0.0) for s in signals
    )
    return weighted_sum / total_weight
```

### Pattern 8: Quality Gate

**What:** Rejects composite scores below the configurable threshold. This is the gate referenced in SGNL-07. No LLM calls happen for anything below this threshold.

```python
# backend/app/signals/quality_gate.py
import os

QUALITY_GATE_THRESHOLD = float(os.environ.get("SIGNAL_QUALITY_GATE", "0.35"))

def passes_gate(composite_score: float) -> bool:
    """Return True only if composite_score meets the quality threshold."""
    return composite_score >= QUALITY_GATE_THRESHOLD
```

### Pattern 9: Redis Opportunity Queue with SET NX Deduplication

**What:** Before enqueuing an opportunity for agent analysis, check Redis with SET NX using a `opp:{ticker}` key and a configurable TTL (default 60 minutes). If the key already exists, the opportunity is a duplicate and must not be re-queued.

```python
# Source: Redis SET NX pattern — verified via redis.io/blog/what-is-idempotency-in-redis
# backend/app/signals/queue.py
import json
import os
import redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
DEDUP_TTL_SECONDS = int(os.environ.get("OPPORTUNITY_DEDUP_TTL_SECONDS", "3600"))
OPP_QUEUE_KEY = "opportunity_queue"

def enqueue_opportunity(r: redis.Redis, ticker: str, payload: dict) -> bool:
    """
    Enqueue opportunity if not already seen within the dedup window.
    Returns True if enqueued, False if duplicate (SET NX returned nil).
    """
    dedup_key = f"opp:dedup:{ticker}"

    # Atomic SET NX with TTL — returns True if key was set (new), False if duplicate
    is_new = r.set(dedup_key, "1", nx=True, ex=DEDUP_TTL_SECONDS)

    if not is_new:
        return False  # Already in queue within dedup window

    # Push to list — workers will BLPOP from this queue (Phase 3)
    r.rpush(OPP_QUEUE_KEY, json.dumps(payload))
    return True
```

**Important:** The dedup key is `opp:dedup:{ticker}`. The opportunity data goes into `opportunity_queue` as a JSON-serialized list. Phase 3 workers will `BLPOP` from this list. Do not use a Celery queue for this — the Redis list is the canonical source for Phase 3.

### Pattern 10: Market Scanner Celery Task

**What:** Orchestrating Celery task triggered every 15 minutes by Beat. Iterates over all watchlist tickers, runs all detectors, scores, gates, and enqueues passing opportunities.

```python
# backend/app/tasks/scan_market.py
from app.tasks.celery_app import app
from app.signals.detectors import volume_spike, price_breakout, insider_cluster, news_catalyst, sector_momentum
from app.signals.scorer import compute_composite_score
from app.signals.quality_gate import passes_gate
from app.signals.queue import enqueue_opportunity
from app.db.engine import SyncSessionLocal
from app.db.models import DetectedSignal
import redis
import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

@app.task(name="app.tasks.scan_market.run", bind=True, max_retries=2)
def run(self) -> dict:
    watchlist = [t.strip() for t in os.environ.get("WATCHLIST", "AAPL,MSFT,GOOGL,AMZN,NVDA").split(",")]
    r = redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"))

    passed = 0
    rejected = 0
    errors = []

    with SyncSessionLocal() as session:
        for ticker in watchlist:
            try:
                raw_signals = []
                for detector_fn in [
                    volume_spike.detect_volume_spike,
                    price_breakout.detect_price_breakout,
                    insider_cluster.detect_insider_cluster,
                    news_catalyst.detect_news_catalyst,
                ]:
                    result = detector_fn(session, ticker)
                    if result:
                        raw_signals.append(result)

                sector_result = sector_momentum.detect_sector_momentum(session, ticker, watchlist)
                if sector_result:
                    raw_signals.append(sector_result)

                detected_at = datetime.now(tz=timezone.utc)

                # Persist each raw signal (VIS-01, VIS-04)
                composite = compute_composite_score(raw_signals) if raw_signals else 0.0
                gate_passed = passes_gate(composite) if raw_signals else False

                for sig in raw_signals:
                    row = DetectedSignal(
                        detected_at=detected_at,
                        ticker=ticker,
                        signal_type=sig["signal_type"],
                        score=sig["score"],
                        composite_score=composite,
                        passed_gate=gate_passed,
                        detail=str(sig.get("detail", {})),
                    )
                    session.merge(row)

                if gate_passed:
                    enqueued = enqueue_opportunity(r, ticker, {
                        "ticker": ticker,
                        "composite_score": composite,
                        "signals": raw_signals,
                        "detected_at": detected_at.isoformat(),
                    })
                    if enqueued:
                        passed += 1
                        logger.info("scan_market: %s queued (score=%.3f)", ticker, composite)
                    else:
                        logger.info("scan_market: %s duplicate — skipped", ticker)
                else:
                    rejected += 1

            except Exception as exc:
                logger.error("scan_market: %s error: %s", ticker, exc, exc_info=True)
                errors.append(f"{ticker}: {exc}")

        session.commit()

    # Instrument false-positive rate in Redis for observability
    total = passed + rejected
    if total > 0:
        r.set("scanner:last_pass_rate", f"{passed / total:.3f}", ex=3600)

    return {"tickers": len(watchlist), "passed": passed, "rejected": rejected, "errors": errors}
```

### Pattern 11: Celery Beat Entry for Market Scanner

**What:** Add `scan-market` entry to `beat_schedule` in `celery_app.py`. Default 15 minutes; configurable via `SCAN_INTERVAL_SECONDS` env var.

```python
# Source: https://docs.celeryq.dev/en/main/userguide/periodic-tasks.html
# Add to existing beat_schedule in backend/app/tasks/celery_app.py

import os
SCAN_INTERVAL = int(os.environ.get("SCAN_INTERVAL_SECONDS", "900"))  # default 15 min

app.conf.beat_schedule.update({
    "scan-market": {
        "task": "app.tasks.scan_market.run",
        "schedule": SCAN_INTERVAL,
    },
})
```

### Pattern 12: FastAPI Read Endpoints for VIS-01 and VIS-04

**What:** `GET /api/v1/signals` returns recent detected signals, filterable by ticker and signal_type. `GET /api/v1/signals/{ticker}` returns signals for a specific ticker. Both include score, signal_type, composite_score, passed_gate, and detected_at — satisfying VIS-01 (raw signals viewable) and VIS-04 (timestamps on every pipeline event).

```python
# backend/app/routers/signals.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db.deps import get_session
from app.db.models import DetectedSignal
from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/api/v1/signals", tags=["signals"])

class SignalResponse(BaseModel):
    detected_at: datetime
    ticker: str
    signal_type: str
    score: Decimal
    composite_score: Optional[Decimal]
    passed_gate: bool
    detail: Optional[str]

    class Config:
        from_attributes = True

@router.get("", response_model=list[SignalResponse])
async def list_signals(
    ticker: Optional[str] = Query(None),
    signal_type: Optional[str] = Query(None),
    limit: int = Query(50, le=500),
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(DetectedSignal)
        .order_by(desc(DetectedSignal.detected_at))
        .limit(limit)
    )
    if ticker:
        stmt = stmt.where(DetectedSignal.ticker == ticker)
    if signal_type:
        stmt = stmt.where(DetectedSignal.signal_type == signal_type)

    result = await session.execute(stmt)
    return result.scalars().all()

@router.get("/{ticker}", response_model=list[SignalResponse])
async def signals_for_ticker(
    ticker: str,
    limit: int = Query(20, le=200),
    session: AsyncSession = Depends(get_session),
):
    stmt = (
        select(DetectedSignal)
        .where(DetectedSignal.ticker == ticker)
        .order_by(desc(DetectedSignal.detected_at))
        .limit(limit)
    )
    result = await session.execute(stmt)
    return result.scalars().all()
```

### Anti-Patterns to Avoid

- **Running detectors outside the DB:** Loading all OHLCV rows into Python memory for pandas calculations is wrong. All rolling statistics must stay in SQL. The data is already in TimescaleDB; window functions are far cheaper than memory copies.
- **Hardcoding thresholds:** Every numeric threshold (z-score, gate cutoff, cluster size, dedup TTL) must be an env var. They will change.
- **Using a Celery queue for the opportunity queue:** The opportunity queue is a Redis list (`RPUSH`/`BLPOP`). Phase 3 agents consume from it directly. Do not use `apply_async` for this — it adds Celery routing overhead and complicates Phase 3 integration.
- **Calling LLMs in the scanner task:** The scanner must not make any LLM calls. LLM calls belong to Phase 3 agents. The quality gate is the boundary; anything below it never reaches an LLM.
- **One giant scanner function:** Each detector must be a separate function/module. This allows unit testing each signal type independently without mocking the entire scan loop.
- **Not persisting rejected signals:** Both passed and rejected signals should be written to `detected_signals` with `passed_gate=True/False`. This is required for false-positive rate analysis and VIS-01.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rolling mean/stddev | numpy + pandas in-memory | SQL `AVG OVER (ROWS BETWEEN N PRECEDING...)` | Data already in DB; no copy overhead; PostgreSQL window functions are production-grade |
| Duplicate opportunity prevention | Custom timestamp comparison | Redis `SET NX EX` | Atomic; sub-millisecond; auto-expires; race-condition-free |
| Celery task deduplication | Manual locking in task body | Redis SET NX on `opp:dedup:{ticker}` | celery-singleton adds a package; SET NX is two lines with existing redis-py |
| Signal persistence | In-memory accumulation | SQLAlchemy `session.merge()` on `DetectedSignal` | Follows Phase 01 upsert pattern; crash-safe |
| Configurable thresholds | Config file parsing | `os.environ.get("VAR", default)` | Env vars are already the pattern; Docker Compose `.env` is the config surface |
| Detector result aggregation | Complex class hierarchy | Plain Python list of dicts | Dictionaries are sufficient; Pydantic model validation added later if needed |

**Key insight:** The entire phase's complexity is in the SQL queries and scoring arithmetic. The infrastructure (Celery, Redis, SQLAlchemy, FastAPI) is unchanged from Phase 01. Resist the urge to add pandas, scipy, or statsmodels — they are unnecessary and would bloat the Docker image.

---

## Common Pitfalls

### Pitfall 1: STDDEV_SAMP Returns NULL When Window Has Fewer Than 2 Rows

**What goes wrong:** `STDDEV_SAMP` returns NULL if the window has 0 or 1 rows. Division by NULL propagates NULL through z-score calculation. All signals fire or none fire incorrectly.
**Why it happens:** Window function aggregate with insufficient rows.
**How to avoid:** Always wrap divisor in `NULLIF(std_vol_20d, 0)` and handle `NULL` z-score in Python with `if row.z_score is None: return None`. Also add `WHERE timestamp >= NOW() - INTERVAL '30 days'` guard to ensure the ticker has recent data.
**Warning signs:** All volume spike detections fire simultaneously after a cold start with limited historical data.

### Pitfall 2: Celery Beat Fires Scanner Before Price Data Is Fresh

**What goes wrong:** Scanner runs at 09:00 UTC before the daily price ingest (06:00 UTC) has completed, causing detectors to query stale data and emit false signals.
**Why it happens:** Beat schedules are independent; no dependency between ingest tasks and scan tasks.
**How to avoid:** Schedule `scan-market` at 900-second intervals starting from 10:00 UTC (after ingest window), or add a DB freshness check at the start of the scanner task: verify the latest `price_ohlcv` row for any ticker is from today before proceeding.
**Warning signs:** All signals fire at the same timestamp (the scanner detected the same stale data repeatedly).

### Pitfall 3: Redis Dedup Key Granularity Too Coarse

**What goes wrong:** Using `opp:dedup:{ticker}` with a 1-hour TTL means if AAPL triggers a strong signal at 09:00 and another strong signal at 09:45 (different signal type), the second is silently dropped.
**Why it happens:** Key is per-ticker, not per-ticker-per-signal-type.
**How to avoid:** The Phase 2 dedup key is correct at `opp:dedup:{ticker}` because the Phase 3 agents analyze the full opportunity for a ticker, not individual signal types. One opportunity per ticker per dedup window is correct behavior. Document this intent explicitly.
**Warning signs:** Legitimate distinct signal types for the same ticker are dropped; confusion when debugging. The intent is intentional dedup, not a bug.

### Pitfall 4: Composite Score Denominator Is Zero

**What goes wrong:** If no detector fires for a ticker, `compute_composite_score([])` divides by zero.
**Why it happens:** Edge case when all detectors return None.
**How to avoid:** Guard with `if not raw_signals: return 0.0` before computing composite score.
**Warning signs:** `ZeroDivisionError` in scanner task logs.

### Pitfall 5: DetectedSignal Primary Key Collision on Rapid Reruns

**What goes wrong:** `DetectedSignal` has a composite PK of `(detected_at, ticker, signal_type)`. If the scanner fires twice within the same second (test reruns, manual trigger + scheduled trigger), `session.merge()` will overwrite the first row silently.
**Why it happens:** TimescaleDB timestamp precision is microsecond, but if `datetime.now()` is called once for all signals in a scan, all rows in one scan share the same `detected_at`.
**How to avoid:** This is acceptable behavior (same scan, same time, same ticker, same signal type = idempotent upsert). The concern is only if two separate scanner runs land within microseconds. In production with 15-minute intervals, this is not a real risk.
**Warning signs:** Only appears in fast test loops; acceptable in production.

### Pitfall 6: Insider Cluster Window Misses Cross-Month Buys

**What goes wrong:** `insider_trades` freshness TTL in the ingest task is 7 days. If the cluster window is 30 days but ingest only refreshes 7-day-old tickers, the cluster query may miss buys from 10–30 days ago if data was never ingested.
**Why it happens:** Ingest freshness TTL is shorter than the detector lookback window.
**How to avoid:** The ingest freshness TTL (7 days) only skips tickers with *recent* data. Historical data from past ingests remains in the DB. The cluster query reads all rows in the DB for that ticker up to 30 days — so the data is there as long as the system has been running for 30+ days. On fresh start, the cluster detector will under-fire (expected behavior). Document this cold-start limitation.
**Warning signs:** No insider cluster signals firing in the first 30 days of operation; this is correct behavior, not a bug.

### Pitfall 7: Sector Momentum Requires All Watchlist Tickers to Have Data

**What goes wrong:** If even one ticker in the sector is missing recent price data, the sector median calculation is skewed. The signal fires or suppresses incorrectly based on missing data.
**Why it happens:** SQL query filters `WHERE ticker = ANY(:tickers)` — if a ticker has no rows in the window, it simply has no row in the result set, changing the median.
**How to avoid:** After fetching 5-day returns, check that at least 60% of tickers in the sector have data before computing sector median. If fewer than this threshold have data, skip the sector momentum signal for all tickers in that sector.
**Warning signs:** Sector momentum signals fire uniformly across all tickers in a sector simultaneously — indicates the median is being computed from one ticker's data only.

---

## Code Examples

### Alembic Migration for detected_signals Hypertable

```python
# Source: Consistent with Phase 01 migration pattern (0001_initial_schema.py)
# alembic/versions/0002_detected_signals.py

revision = "0002"
down_revision = "0001"

def upgrade():
    op.create_table(
        "detected_signals",
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("signal_type", sa.String(50), nullable=False),
        sa.Column("score", sa.Numeric(), nullable=False),
        sa.Column("composite_score", sa.Numeric(), nullable=True),
        sa.Column("passed_gate", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("source", sa.String(50), nullable=False, server_default="scanner"),
        sa.PrimaryKeyConstraint("detected_at", "ticker", "signal_type"),
    )
    op.execute(
        "SELECT create_hypertable('detected_signals', 'detected_at', "
        "chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE)"
    )
    op.create_index(
        "ix_detected_signals_ticker_detected_at",
        "detected_signals",
        ["ticker", "detected_at"],
    )
    op.create_index(
        "ix_detected_signals_passed_gate",
        "detected_signals",
        ["passed_gate", "detected_at"],
    )

def downgrade():
    op.drop_table("detected_signals")
```

### Redis False-Positive Rate Instrumentation

```python
# Source: Redis SET pattern; aligns with Phase 01 spend tracker pattern
# At the end of every scan_market.run():

total = passed + rejected
if total > 0:
    r.set("scanner:last_pass_rate", f"{passed / total:.3f}", ex=3600)
    r.set("scanner:last_scan_at", datetime.now(tz=timezone.utc).isoformat(), ex=3600)
    r.set("scanner:last_total", str(total), ex=3600)
```

### Beat Schedule Addition (configurable interval)

```python
# Source: https://docs.celeryq.dev/en/main/userguide/periodic-tasks.html
# Pattern: integer seconds schedule for frequent tasks (not crontab)

SCAN_INTERVAL = int(os.environ.get("SCAN_INTERVAL_SECONDS", "900"))

app.conf.beat_schedule.update({
    "scan-market": {
        "task": "app.tasks.scan_market.run",
        "schedule": SCAN_INTERVAL,
        # No args — watchlist read from env at task runtime (matches Phase 01 pattern)
    },
})
```

### Register Router in main.py

```python
# backend/app/main.py — add after existing imports
from app.routers.signals import router as signals_router

app.include_router(signals_router)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pandas rolling z-score in-memory | SQL `AVG OVER / STDDEV_SAMP OVER` window functions | Always best practice for DB-resident data | No memory copy; query optimizer can use hypertable indexes |
| External task scheduling (APScheduler, cron) | Celery Beat `beat_schedule` | Phase 01 decision | Already in stack; no new service |
| Ad-hoc Redis key naming | `opp:dedup:{ticker}` namespaced key pattern | Redis best practice (namespacing) | Avoids key collisions; easy `SCAN opp:dedup:*` for debugging |
| Bloom filter for dedup | Redis SET NX with TTL | Recommended for bounded dedup windows | Zero false positives for per-ticker dedup; bloom filter only needed at very high scale (>>10K tickers) |

**Deprecated/outdated:**
- Using `celery-singleton` or `celery-once` packages for scan dedup: unnecessary when the dedup unit is "per ticker per time window" (Redis SET NX is simpler and already in the stack).
- `django-celery-beat`: not relevant; this project does not use Django.

---

## Open Questions

1. **Sentiment column in news_items is currently unpopulated**
   - What we know: `NewsItem.sentiment` exists in the schema but neither MassiveConnector nor FMPConnector populate it (they don't do sentiment analysis; the field is always `None`).
   - What's unclear: The news catalyst detector uses `sentiment = 'positive'` in its SQL. With no sentiment data, positive_count will always be 0.
   - Recommendation: The news catalyst detector should NOT filter on sentiment in Phase 02. Instead, filter on keyword presence in headline only. Sentiment analysis is a Phase 3 concern (LLM can assess it during agent analysis). Remove `SUM(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END)` from the detector SQL.

2. **FMP endpoint paths are LOW confidence (inherited from Phase 01 decision D-01-02-3)**
   - What we know: insider_cluster and news_catalyst detectors query data already in TimescaleDB — they do not call FMP directly. The detector SQL is independent of FMP path accuracy.
   - What's unclear: If FMP data has not been successfully ingested (because endpoints are wrong), the insider_cluster detector will never fire. This is a data quality issue, not a detector code issue.
   - Recommendation: Validate FMP endpoints before Phase 02 scan runs, as blocked in STATE.md. If FMP endpoints are wrong, insider_cluster and news_catalyst detectors will return no results (silent failure). Add a "data freshness check" at scanner start.

3. **Primary key structure for detected_signals with multiple signals per scan**
   - What we know: Composite PK is `(detected_at, ticker, signal_type)`. Within one scanner run, all signals share the same `detected_at` timestamp (called once at task start). This is correct — each scan run produces at most one row per `(ticker, signal_type)` pair.
   - What's unclear: If the scanner is triggered manually AND by Beat within microseconds, both will attempt to write with the same timestamp. `session.merge()` will silently upsert (last write wins). This is acceptable for Phase 02.
   - Recommendation: Acceptable. Document the PK intent in a comment on the model.

4. **Sector membership configuration**
   - What we know: Sector momentum requires grouping watchlist tickers by sector. There is no automated sector lookup in the Phase 01 stack.
   - What's unclear: The best configuration surface for sector mapping — env var, JSON file, or a `sectors` DB table.
   - Recommendation: Use a JSON env var `SECTOR_MAP` (e.g., `'{"AAPL":"tech","MSFT":"tech","JPM":"financial"}'`). Parse it at task startup. This avoids adding a DB table for what is fundamentally static configuration. Can be promoted to a DB table in a future phase if the watchlist grows.

---

## Sources

### Primary (HIGH confidence)
- Celery Beat official docs — https://docs.celeryq.dev/en/main/userguide/periodic-tasks.html — `beat_schedule` syntax, integer schedule type, single Beat instance requirement
- Redis idempotency official blog — https://redis.io/blog/what-is-idempotency-in-redis/ — SET NX with EX pattern, Python code examples, TTL strategy
- Redis deduplication tutorial — https://redis.io/tutorials/data-deduplication-with-redis/ — SET NX layer, exact fingerprint layer, TTL best practices
- PostgreSQL window function docs — `AVG OVER`, `STDDEV_SAMP OVER`, `LAG OVER`, `ROWS BETWEEN N PRECEDING AND CURRENT ROW` — all standard SQL:2003; PostgreSQL 16 (in use via TimescaleDB)
- Phase 01 research and codebase — all stack decisions locked and verified

### Secondary (MEDIUM confidence)
- TimescaleDB z-score anomaly pattern — verified via WebSearch with corroborating sources: `(value - avg) / NULLIF(stddev, 0)` with threshold 2.0–3.0 is the documented community pattern for time-series anomaly detection
- Celery-singleton GitHub — https://github.com/steinitzu/celery-singleton — reviewed for comparison; NOT recommended for this use case (Redis SET NX is simpler)
- oneuptime.com Redis request deduplication post (2026-01-21) — confirms SET NX pattern for dedup windows; TTL selection guidance

### Tertiary (LOW confidence)
- Signal scoring weight defaults (0.25/0.25/0.20/0.20/0.10) — entirely empirical; no authoritative source. Treat as placeholder values requiring tuning.
- Quality gate default threshold (0.35) — empirical; no authoritative source. Instrument from day one.
- 20-day rolling window for volume/price baseline — common in technical analysis literature but specific to use case; should be configurable.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — No new packages; all Phase 01 patterns apply directly
- Architecture: HIGH — SQL window functions, Redis SET NX, Celery Beat are well-documented patterns
- SQL detector queries: HIGH — Window function syntax is standard PostgreSQL; verified via multiple sources
- Signal scoring weights: LOW — Empirical values; must be configurable from day one
- Pitfalls: HIGH — Derived from understanding of the actual codebase and known SQL edge cases

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (30 days — stack is stable; signal thresholds require empirical tuning post-deploy)
