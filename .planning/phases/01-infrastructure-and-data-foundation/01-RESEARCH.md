# Phase 01: Infrastructure and Data Foundation - Research

**Researched:** 2026-03-25
**Domain:** Docker Compose orchestration, TimescaleDB/SQLAlchemy, financial data connectors (Massive.com/FMP), Celery task queue, LLM cost controls, agent prompt architecture
**Confidence:** HIGH (stack is locked; all core findings verified via official docs or Context7)

---

## Summary

Phase 01 establishes the entire platform stack from scratch: Docker Compose service orchestration, time-series data ingestion from two financial APIs, a unified normalization schema, and agent prompt infrastructure with built-in divergence enforcement. The tech stack is fully locked (FastAPI, TimescaleDB, Celery/Redis, SQLAlchemy 2.0, Anthropic SDK) so research focused on authoritative implementation patterns rather than option evaluation.

The biggest implementation risk in this phase is the Alembic/TimescaleDB interaction: TimescaleDB auto-creates indexes on hypertable time columns that Alembic does not track, causing autogenerate to emit spurious DROP INDEX statements in every subsequent migration. This must be handled with a custom `include_object` filter from the first migration or it becomes a persistent maintenance burden. Additionally, Polygon.io rebranded as Massive.com in October 2025 — the Python package is now `massive`, not `polygon-api-client`.

The LLM cost control wrapper must be built before any agent makes a real API call. Current Claude Haiku 4.5 pricing is $1/MTok input and $5/MTok output — 5x cheaper than Sonnet 4 for triage tasks. Token counts are available in every API response's `usage` object, making Redis-backed daily spend accumulation straightforward without a third-party library.

**Primary recommendation:** Build in this exact sequence: Docker Compose + healthchecks → Alembic bootstrap with TimescaleDB filter configured → data connectors behind abstract interface → FinancialSnapshot normalization → LLM wrapper with spend gate → agent persona files. Each step has a clear testable output before proceeding.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | 0.135.2 | HTTP API + SSE endpoint | Locked decision; async-native, auto-docs |
| sqlalchemy | 2.0.x | ORM + async DB access | Locked; 2.0 style is mandatory (not legacy 1.x) |
| alembic | 1.18.4 | DB schema migrations | Pairs with SQLAlchemy; current release |
| sqlalchemy-timescaledb | latest | TimescaleDB dialect for SQLAlchemy | Handles hypertable DDL natively; supports asyncpg |
| asyncpg | latest | Async PostgreSQL driver | Required for SQLAlchemy 2.0 async mode |
| celery | 5.6.2 | Distributed task queue | Locked; handles periodic market data ingestion |
| redis-py | latest | Redis client (broker + result backend) | Locked; Celery broker; also session cache |
| pydantic | v2 | Data validation and normalization schema | Used in FastAPI; powers FinancialSnapshot |
| anthropic | 0.86.0 | Claude API SDK | Locked; provides usage.input_tokens/output_tokens |
| massive | latest (formerly polygon-api-client) | Polygon/Massive.com market data | Official Python client post Oct 2025 rebrand |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| celery[redis] | 5.6.2 | Redis broker transport for Celery | Required when using Redis as broker |
| flower | latest | Celery task monitoring web UI | Dev/ops visibility into task queues |
| python-dotenv | latest | Load .env into environment | API key management in Docker |
| httpx | latest | Async HTTP for FMP API calls | No official async FMP client exists |
| tenacity | latest | Retry with exponential backoff | Wrap all external API calls |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| massive (official) | requests + polygon REST | Official client handles pagination, auth, retries automatically |
| sqlalchemy-timescaledb dialect | Raw SQL execute() | Dialect handles hypertable DDL in create_all(); cleaner ORM integration |
| Redis daily spend counter | SQLite / file-based | Redis already in stack; atomic INCRBYFLOAT avoids race conditions |

### Installation
```bash
pip install fastapi==0.135.2 sqlalchemy[asyncio] alembic asyncpg \
    sqlalchemy-timescaledb celery[redis] redis flower \
    anthropic==0.86.0 massive pydantic httpx tenacity python-dotenv
```

---

## Architecture Patterns

### Recommended Project Structure
```
backend/
├── alembic/
│   ├── versions/          # Migration files
│   ├── env.py             # CRITICAL: TimescaleDB index filter goes here
│   └── alembic.ini
├── app/
│   ├── main.py            # FastAPI app, lifespan events
│   ├── db/
│   │   ├── engine.py      # create_async_engine, async_sessionmaker
│   │   ├── models.py      # SQLAlchemy ORM models (hypertable-annotated)
│   │   └── deps.py        # FastAPI get_session() dependency
│   ├── connectors/
│   │   ├── base.py        # Abstract DataConnector interface
│   │   ├── massive.py     # Polygon/Massive.com implementation
│   │   └── fmp.py         # Financial Modeling Prep implementation
│   ├── schemas/
│   │   └── financial.py   # FinancialSnapshot Pydantic model
│   ├── tasks/
│   │   ├── celery_app.py  # Celery app + beat_schedule
│   │   ├── ingest_price.py
│   │   ├── ingest_fundamentals.py
│   │   ├── ingest_insider.py
│   │   └── ingest_news.py
│   ├── llm/
│   │   ├── wrapper.py     # LLM call wrapper with cost gate
│   │   └── spend_tracker.py  # Redis-backed daily spend accumulator
│   └── agents/
│       └── personas/
│           ├── buffett.md    # Fundamentals-only; value lens
│           ├── cohen.md      # Price action only; momentum lens
│           ├── dalio.md      # Macro + diversification lens
│           ├── lynch.md      # Growth + GARP lens
│           └── simons.md     # Quantitative signals lens
docker-compose.yml
.env.example
```

### Pattern 1: Docker Compose Healthcheck with Dependency Chain

**What:** Services declare healthchecks; downstream services use `condition: service_healthy` so Docker enforces startup order and will not start a service until its dependencies are genuinely ready.
**When to use:** Always — without this, FastAPI starts before TimescaleDB accepts connections.

```yaml
# Source: https://docs.docker.com/compose/how-tos/startup-order/
services:
  timescaledb:
    image: timescale/timescaledb:latest-pg16
    environment:
      POSTGRES_USER: hedge
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: hedgefund
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U hedge -d hedgefund"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  api:
    build: ./backend
    depends_on:
      timescaledb:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 20s

  celery_worker:
    build: ./backend
    command: celery -A app.tasks.celery_app worker --loglevel=info
    depends_on:
      api:
        condition: service_healthy

  celery_beat:
    build: ./backend
    command: celery -A app.tasks.celery_app beat --loglevel=info
    depends_on:
      api:
        condition: service_healthy
```

### Pattern 2: SQLAlchemy 2.0 Async Engine Setup

**What:** Single engine and sessionmaker per process; short-lived AsyncSession per request via FastAPI dependency injection.
**When to use:** Always with FastAPI + asyncpg.

```python
# Source: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
# backend/app/db/engine.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

DATABASE_URL = "timescaledb+asyncpg://hedge:password@timescaledb:5432/hedgefund"

engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=0,
    pool_pre_ping=True,
    pool_recycle=3600,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,  # REQUIRED: prevents implicit IO after commit
    class_=AsyncSession,
)

# backend/app/db/deps.py
async def get_session():
    async with AsyncSessionLocal() as session:
        yield session
```

### Pattern 3: TimescaleDB ORM Model with Hypertable Annotation

**What:** SQLAlchemy model with `timescaledb_hypertable` table arg; `create_all()` calls `create_hypertable()` automatically via the dialect.
**When to use:** All time-series tables (price OHLCV, fundamentals snapshots, news).

```python
# Source: https://github.com/dorosch/sqlalchemy-timescaledb
# backend/app/db/models.py
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped
from sqlalchemy import String, Float, DateTime, BigInteger
from datetime import datetime

class Base(DeclarativeBase):
    pass

class PriceOHLCV(Base):
    __tablename__ = "price_ohlcv"
    __table_args__ = (
        {"timescaledb_hypertable": {"time_column_name": "timestamp"}},
    )

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20), primary_key=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(String(50))  # "massive" | "fmp"
```

### Pattern 4: Alembic env.py with TimescaleDB Index Filter

**What:** Alembic autogenerate filter that excludes hypertable-generated indexes from diff output.
**When to use:** MANDATORY — configure on first migration setup or every autogenerate will emit spurious DROP INDEX.

```python
# Source: https://github.com/sqlalchemy/alembic/discussions/1465
# alembic/env.py  — add this to the run_migrations_online() function

def include_object(object, name, type_, reflected, compare_to):
    """Exclude TimescaleDB auto-created indexes from migration diffs."""
    if type_ == "index" and reflected and compare_to is None:
        # TimescaleDB creates indexes automatically on hypertable time columns
        # These are not in our migrations; exclude them to prevent spurious DROP INDEX
        return False
    return True

# In context.configure():
context.configure(
    connection=connection,
    target_metadata=target_metadata,
    include_object=include_object,
    compare_type=True,
)
```

### Pattern 5: Abstract Data Connector Interface

**What:** ABC defining the contract all data source connectors must satisfy; enables swapping Massive.com for another provider without changing downstream normalization.
**When to use:** All data ingestion paths.

```python
# backend/app/connectors/base.py
from abc import ABC, abstractmethod
from typing import AsyncIterator
from app.schemas.financial import FinancialSnapshot
import datetime

class DataConnector(ABC):
    """All market data providers implement this interface."""

    @abstractmethod
    async def fetch_ohlcv(
        self,
        ticker: str,
        from_date: datetime.date,
        to_date: datetime.date,
    ) -> AsyncIterator[FinancialSnapshot]:
        """Yield normalized OHLCV snapshots."""
        ...

    @abstractmethod
    async def fetch_fundamentals(self, ticker: str) -> FinancialSnapshot:
        """Return latest fundamentals snapshot."""
        ...

    @abstractmethod
    async def fetch_insider_trades(self, ticker: str, limit: int = 50) -> list[FinancialSnapshot]:
        """Return recent insider trade snapshots."""
        ...

    @abstractmethod
    async def fetch_news(self, ticker: str, limit: int = 20) -> list[FinancialSnapshot]:
        """Return recent news snapshots."""
        ...
```

### Pattern 6: Massive.com (Polygon) Connector

**What:** Concrete connector using the `massive` Python client (rebranded from `polygon-api-client`).
**When to use:** Real-time/recent price data and news headlines.

```python
# Source: https://github.com/polygon-io/client-python (now massive)
# backend/app/connectors/massive.py
from massive import RESTClient
from tenacity import retry, stop_after_attempt, wait_exponential
import os

class MassiveConnector(DataConnector):
    def __init__(self):
        self.client = RESTClient(api_key=os.environ["MASSIVE_API_KEY"])

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def fetch_ohlcv(self, ticker, from_date, to_date):
        for agg in self.client.list_aggs(
            ticker=ticker,
            multiplier=1,
            timespan="day",
            from_=str(from_date),
            to=str(to_date),
            limit=50000,
        ):
            yield FinancialSnapshot(
                ticker=ticker,
                timestamp=agg.timestamp,
                data_type="ohlcv",
                source="massive",
                price=agg.close,
                open=agg.open,
                high=agg.high,
                low=agg.low,
                volume=agg.volume,
            )
```

### Pattern 7: LLM Wrapper with Cost Gate

**What:** Wrapper around `anthropic.Anthropic().messages.create()` that reads `usage` from the response, accumulates spend in Redis with `INCRBYFLOAT`, and raises before any call that would breach the daily limit.
**When to use:** Every LLM call — no agent calls the SDK directly.

```python
# backend/app/llm/wrapper.py
import anthropic
import redis.asyncio as aioredis
from datetime import date

COST_PER_MTK = {
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
}
DAILY_SPEND_LIMIT_USD = float(os.environ.get("DAILY_SPEND_LIMIT_USD", "10.0"))

async def llm_call(model: str, messages: list, system: str, redis_client) -> dict:
    """
    Gated LLM call. Raises BudgetExceededError if daily spend would breach limit.
    Returns message content + usage metadata.
    """
    today_key = f"llm:spend:{date.today().isoformat()}"
    current_spend = float(await redis_client.get(today_key) or 0)

    if current_spend >= DAILY_SPEND_LIMIT_USD:
        raise BudgetExceededError(
            f"Daily LLM spend limit ${DAILY_SPEND_LIMIT_USD} reached. "
            f"Current: ${current_spend:.4f}"
        )

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=system,
        messages=messages,
    )

    # Accumulate actual cost from usage object in response
    prices = COST_PER_MTK[model]
    cost = (
        response.usage.input_tokens / 1_000_000 * prices["input"]
        + response.usage.output_tokens / 1_000_000 * prices["output"]
    )
    await redis_client.incrbyfloat(today_key, cost)
    await redis_client.expire(today_key, 86400)  # TTL: 24h rolling

    return {
        "content": response.content[0].text,
        "model": model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cost_usd": cost,
    }
```

### Pattern 8: Agent Persona File Structure

**What:** Versioned Markdown system prompt files with explicit data partition rules baked in. Loaded at runtime, not hardcoded.
**When to use:** All five investor persona agents.

```
# agents/personas/buffett.md
# Persona: Warren Buffett — Value Investor
# Version: 1.0.0
# Data partition: FUNDAMENTALS ONLY

## Role
You are Warren Buffett analyzing a stock from first principles.
You have access ONLY to fundamental financial data (P/E ratio, revenue growth,
profit margins, balance sheet strength, owner earnings).

## STRICT CONSTRAINT
You must NOT reference price movements, technical indicators, or momentum signals.
If the DATA CONTEXT below does not contain fundamental data for a metric you need,
state clearly: "Insufficient fundamental data to assess [metric]."

## DATA CONTEXT
{{fundamentals_json}}

## Analysis Framework
1. Business quality: moat, competitive position, management integrity
2. Financial health: debt/equity, free cash flow, ROE
3. Valuation: intrinsic value vs current price (only if price provided in DATA CONTEXT)
4. Verdict: BUY / HOLD / PASS with one-paragraph rationale

## Output Format (JSON)
{"persona": "buffett", "verdict": "BUY|HOLD|PASS", "confidence": 0-100,
 "rationale": "...", "key_metrics_used": [...], "data_gaps": [...]}
```

### Anti-Patterns to Avoid

- **Sharing sessions across concurrent requests:** Each request must get its own `AsyncSession` from the factory — sharing causes race conditions and transaction bleed.
- **Calling `metadata.create_all()` without Alembic:** In production, all schema changes go through Alembic migrations. `create_all()` is for local dev only.
- **LLM calls outside the wrapper:** Any direct `anthropic.Anthropic().messages.create()` call bypasses the cost gate. Make the wrapper the only import used by agents.
- **Fat agent prompts with no data context block:** Without a structured `DATA CONTEXT` block in the prompt, the model recalls training data (hallucinated financials). Always inject figures explicitly.
- **Running `celery beat` on multiple instances:** Beat must be a single process. Multiple beat instances = duplicate ingestion tasks.
- **Using `polygon-api-client` package:** It is now `massive`. The old package name may still install but routes to the deprecated API base.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP retries for external APIs | Custom retry loop | `tenacity` with `@retry` decorator | Handles jitter, exponential backoff, exception typing |
| Periodic task scheduling | `asyncio.sleep` loop | Celery beat `beat_schedule` | Persistence, restartability, crontab syntax, monitoring |
| TimescaleDB hypertable DDL | Raw `execute("SELECT create_hypertable(...)")` | `sqlalchemy-timescaledb` dialect | Integrated with `create_all()` and Alembic; correct chunking defaults |
| LLM token cost calculation | Manual token counting | Read `response.usage` from Anthropic SDK | SDK provides exact counts; pre-counting with `count_tokens()` available for gate checks |
| Service startup ordering | `sleep` scripts in entrypoint | Docker Compose `condition: service_healthy` | Native; restarts correctly on container failure |
| API key management | Hardcode or config files | `.env` + `python-dotenv` + Docker env injection | Secrets stay out of image layers |

**Key insight:** Every "simple" problem in this list has at least one non-obvious edge case (retry storms, duplicate beat tasks, drift in token cost estimates) that the recommended library already handles correctly.

---

## Common Pitfalls

### Pitfall 1: Alembic Drops TimescaleDB Auto-Created Indexes
**What goes wrong:** After `create_hypertable()` runs, TimescaleDB creates a btree index on the time column automatically. Alembic's autogenerate reflects this index but cannot find it in the migration history, so it emits `DROP INDEX` in every subsequent autogenerate migration.
**Why it happens:** TimescaleDB creates the index outside Alembic's control.
**How to avoid:** Add the `include_object` filter to `alembic/env.py` before running any migrations. Filter out reflected indexes with `compare_to is None`.
**Warning signs:** Autogenerated migrations contain `op.drop_index(...)` for an index you never created explicitly.

### Pitfall 2: Massive.com / Polygon Rebrand
**What goes wrong:** Installing `polygon-api-client` or importing `polygon` still works but the default API base is the old `api.polygon.io`, which will eventually be deprecated.
**Why it happens:** The rebrand to Massive.com happened October 30, 2025.
**How to avoid:** Use `pip install massive` and `from massive import RESTClient`. The new package defaults to `api.massive.com`.
**Warning signs:** Import `from polygon import RESTClient` — this is the old client.

### Pitfall 3: Async Session Reuse Across Concurrent Tasks
**What goes wrong:** Sharing a single `AsyncSession` instance across multiple concurrent `asyncio` tasks causes transaction isolation errors and data corruption.
**Why it happens:** `AsyncSession` is not thread/task-safe for concurrent use.
**How to avoid:** Always call `AsyncSessionLocal()` as a context manager to get a new session per operation. Never store session on a class instance shared across requests.
**Warning signs:** Intermittent `MissingGreenlet` or transaction isolation errors under load.

### Pitfall 4: Two Celery Beat Processes Running
**What goes wrong:** Running two `celery beat` processes causes every periodic task to be enqueued twice, resulting in duplicate data ingestion and doubled API calls.
**Why it happens:** Beat is a scheduler; multiple schedulers emit duplicate schedules.
**How to avoid:** Docker Compose must define exactly one `celery_beat` service. Add `restart: unless-stopped` but not `replicas: 2`.
**Warning signs:** Database contains duplicate rows for the same ticker/timestamp.

### Pitfall 5: LLM Sycophantic Convergence Without Data Partitioning
**What goes wrong:** All five agents receive the same complete data context and produce similar verdicts, defeating the purpose of multi-agent divergence.
**Why it happens:** Without enforced data partitions in system prompts, models naturally reason from the same evidence to consensus conclusions.
**How to avoid:** Each persona file must explicitly limit its `DATA CONTEXT` to its assigned data subset. Buffett gets fundamentals JSON only. Cohen gets OHLCV price JSON only. Build a `DataPartitioner` that constructs persona-specific context from the unified `FinancialSnapshot`.
**Warning signs:** Inter-agent verdict variance is consistently low; agents cite the same metrics.

### Pitfall 6: FMP Rate Limit Exhaustion
**What goes wrong:** Free tier FMP plan has a 500MB/30-day bandwidth cap. Fetching 13F filings or full balance sheets for many tickers exhausts the quota quickly.
**Why it happens:** 13F filings responses are large; balance sheets compound across multiple tickers.
**How to avoid:** Celery tasks must cache responses in TimescaleDB with a freshness TTL. Fundamentals: max one fetch per ticker per day. 13F: max one fetch per ticker per quarter. Check DB first; only call FMP on cache miss.
**Warning signs:** HTTP 429 or bandwidth quota errors from FMP mid-day.

### Pitfall 7: `expire_on_commit=True` (Default) Causes Implicit IO
**What goes wrong:** After committing, accessing any ORM attribute triggers a synchronous load, which raises `MissingGreenlet` in async context.
**Why it happens:** SQLAlchemy's default `expire_on_commit=True` marks all attributes as expired after commit.
**How to avoid:** Set `expire_on_commit=False` in `async_sessionmaker`. Load all data you need before committing or refresh explicitly with `await session.refresh(obj)`.
**Warning signs:** `MissingGreenlet` errors immediately after `await session.commit()`.

---

## Code Examples

### Celery App with Beat Schedule for Market Data
```python
# Source: https://docs.celeryq.dev/en/main/userguide/periodic-tasks.html
# backend/app/tasks/celery_app.py
from celery import Celery
from celery.schedules import crontab
import os

app = Celery(
    "hedgefund",
    broker=os.environ["REDIS_URL"],
    backend=os.environ["REDIS_URL"],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # one task at a time per worker
)

app.conf.beat_schedule = {
    "ingest-price-every-5min": {
        "task": "app.tasks.ingest_price.run",
        "schedule": 300.0,  # 5 minutes
    },
    "ingest-fundamentals-daily": {
        "task": "app.tasks.ingest_fundamentals.run",
        "schedule": crontab(hour=6, minute=0),  # 06:00 UTC daily
    },
    "ingest-insider-trades-daily": {
        "task": "app.tasks.ingest_insider.run",
        "schedule": crontab(hour=7, minute=0),
    },
    "ingest-news-every-15min": {
        "task": "app.tasks.ingest_news.run",
        "schedule": crontab(minute="*/15"),
    },
}
```

### FinancialSnapshot Unified Schema (Pydantic v2)
```python
# backend/app/schemas/financial.py
from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime
from decimal import Decimal

DataType = Literal["ohlcv", "fundamentals", "insider_trade", "news"]

class FinancialSnapshot(BaseModel):
    """
    Single canonical schema for all ingested financial data.
    Agents consume this; connectors produce it.
    Fields are Optional because not all data types populate all fields.
    """
    ticker: str
    timestamp: datetime
    data_type: DataType
    source: str  # "massive" | "fmp"

    # OHLCV fields (data_type="ohlcv")
    price: Optional[Decimal] = None
    open: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    volume: Optional[int] = None

    # Fundamentals fields (data_type="fundamentals")
    pe_ratio: Optional[Decimal] = None
    revenue: Optional[Decimal] = None
    net_income: Optional[Decimal] = None
    eps: Optional[Decimal] = None
    debt_to_equity: Optional[Decimal] = None
    free_cash_flow: Optional[Decimal] = None

    # Insider trade fields (data_type="insider_trade")
    insider_name: Optional[str] = None
    trade_type: Optional[Literal["buy", "sell"]] = None
    shares: Optional[int] = None
    trade_value: Optional[Decimal] = None

    # News fields (data_type="news")
    headline: Optional[str] = None
    summary: Optional[str] = None
    sentiment: Optional[Literal["positive", "negative", "neutral"]] = None
    article_url: Optional[str] = None

    class Config:
        # Allow Decimal serialization for JSON
        json_encoders = {Decimal: str}
```

### Alembic Initial Migration with Hypertable
```python
# alembic/versions/0001_initial_schema.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        "price_ohlcv",
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("open", sa.Numeric, nullable=True),
        sa.Column("high", sa.Numeric, nullable=True),
        sa.Column("low", sa.Numeric, nullable=True),
        sa.Column("close", sa.Numeric, nullable=True),
        sa.Column("volume", sa.BigInteger, nullable=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.PrimaryKeyConstraint("timestamp", "ticker"),
    )
    # Convert to TimescaleDB hypertable after table creation
    op.execute(
        "SELECT create_hypertable('price_ohlcv', 'timestamp', "
        "chunk_time_interval => INTERVAL '7 days')"
    )
    # Add composite index for ticker-first queries
    op.create_index("ix_price_ohlcv_ticker_time", "price_ohlcv", ["ticker", "timestamp"])

def downgrade():
    op.drop_table("price_ohlcv")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `polygon-api-client` package | `massive` package | Oct 2025 | Old package will eventually stop working |
| `tiangolo/uvicorn-gunicorn-fastapi` Docker image | Build from `python:3.x` directly | 2024 | Base image deprecated; use `fastapi run --workers N` |
| SQLAlchemy 1.x `Session` patterns | SQLAlchemy 2.0 `AsyncSession` + `async_sessionmaker` | 2023 | 1.x style still works but produces deprecation warnings |
| `polygon` Python import | `from massive import RESTClient` | Oct 2025 | Old import targets deprecated API base |
| `claude-haiku-3` ($0.25/$1.25 per MTok) | `claude-haiku-4-5` ($1/$5 per MTok) | 2025 | 4x price increase but significantly better reasoning |

**Deprecated/outdated:**
- `polygon-api-client` PyPI package: replaced by `massive`; do not use in new code
- `tiangolo/uvicorn-gunicorn-fastapi` Docker image: officially deprecated; FastAPI docs now recommend building from base Python image

---

## Open Questions

1. **Massive.com API key backward compatibility**
   - What we know: Existing Polygon.io API keys continue working post-rebrand
   - What's unclear: When exactly `api.polygon.io` will be fully deprecated (timeline not published)
   - Recommendation: Use `api_key` env var named `MASSIVE_API_KEY`; `POLYGON_API_KEY` as alias for backward compat

2. **FMP free tier bandwidth cap enforcement**
   - What we know: Free tier = 500MB / 30 days. Fundamentals + 13F filings are large responses
   - What's unclear: Whether FMP returns 429 vs 200 with error body when bandwidth is exceeded
   - Recommendation: Wrap all FMP calls with error handling for both; add cache-first logic from day one

3. **TimescaleDB chunk interval for this workload**
   - What we know: Financial data is low-frequency; TimescaleDB docs recommend 1 week to 1 month intervals for low-frequency data
   - What's unclear: Actual row volume at target scale (number of tickers being tracked)
   - Recommendation: Default to `7 days` chunk interval; can be adjusted later with `set_chunk_time_interval()`

4. **SQLAlchemy-timescaledb Alembic autogenerate support**
   - What we know: The dialect handles `create_all()` correctly; Alembic integration has the index drift problem documented above
   - What's unclear: Whether the dialect provides built-in Alembic ops for hypertable operations
   - Recommendation: Use raw `op.execute("SELECT create_hypertable(...)")` in initial migration; this is the documented community pattern

---

## Sources

### Primary (HIGH confidence)
- Official FastAPI Docker docs: https://fastapi.tiangolo.com/deployment/docker/ — Dockerfile patterns, CMD exec form requirement, deprecation of tiangolo base image
- Official Docker Compose docs: https://docs.docker.com/compose/how-tos/startup-order/ — `condition: service_healthy` syntax verified
- SQLAlchemy 2.0 asyncio docs: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html — `async_sessionmaker`, `expire_on_commit=False` requirement
- Anthropic pricing page: https://platform.claude.com/docs/en/about-claude/pricing — Verified Haiku 4.5 ($1/$5 MTok), Sonnet 4.6 ($3/$15 MTok), usage object structure
- `sqlalchemy-timescaledb` GitHub: https://github.com/dorosch/sqlalchemy-timescaledb — ORM integration, `__table_args__` pattern, asyncpg support
- `massive` GitHub (formerly polygon-io/client-python): https://github.com/polygon-io/client-python — Rebrand confirmed, `pip install massive`, `RESTClient` usage

### Secondary (MEDIUM confidence)
- Alembic/TimescaleDB index drift issue: https://github.com/sqlalchemy/alembic/discussions/1465 — `include_object` filter pattern verified across multiple community responses
- Celery periodic tasks docs: https://docs.celeryq.dev/en/main/userguide/periodic-tasks.html — `beat_schedule` syntax, `crontab` examples verified
- TimescaleDB financial data guide: https://www.tigerdata.com/learn/best-practices-for-time-series-metadata-tables — chunk interval recommendations for financial data
- GuruAgents research paper: https://arxiv.org/html/2510.01664v1 — Validates persona-driven investor agent approach; five distinct investor archetypes confirmed viable

### Tertiary (LOW confidence)
- FMP API endpoint structure — docs returned 403; derived from search results and GitHub examples. Verify endpoint paths against live FMP docs with actual API key before implementation.
- `fmp-data` Python client (https://github.com/MehdiZare/fmp-data) — community wrapper, not official; assess before adopting vs raw httpx calls

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — All versions locked in project spec; Massive.com rebrand confirmed from official GitHub
- Docker Compose patterns: HIGH — Verified from official Docker docs
- SQLAlchemy async patterns: HIGH — Verified from official SQLAlchemy 2.0 docs
- TimescaleDB/Alembic integration: MEDIUM — `include_object` fix verified via community + official Alembic issue tracker; dialect Alembic support not explicitly documented
- FMP API endpoints: LOW — docs returned 403; structure inferred from search results. Needs verification with live API key
- Claude pricing: HIGH — Fetched directly from official Anthropic pricing page
- Agent persona divergence: MEDIUM — Pattern validated by GuruAgents research paper; specific prompt structures are implementation choices

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (30 days — stack is stable, but Massive.com transition timeline may update)
