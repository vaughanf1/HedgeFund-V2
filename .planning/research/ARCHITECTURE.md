# Architecture Patterns: Proactive Multi-Agent AI Investment Discovery Platform

**Domain:** Multi-agent AI financial analysis / investment discovery
**Researched:** 2026-03-25
**Confidence:** MEDIUM-HIGH (patterns verified via Azure Architecture Center, AWS financial AI blog, TradingAgents paper, FastAPI/Celery/Redis official community sources)

---

## Recommended Architecture

The system is a **concurrent fan-out/fan-in orchestration** sitting downstream of an **event-driven market scanner pipeline**. Two main processing planes exist:

- **Ingestion plane** — scheduled, background, async (market scanner workers, signal detection, opportunity scoring)
- **Analysis plane** — on-demand, triggered per opportunity, parallel LLM calls + aggregation

A **real-time pub/sub channel** (Redis) bridges the backend planes to the frontend, which subscribes via Server-Sent Events (SSE).

---

## Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| **Market Scanner Workers** | Poll Polygon.io / FMP APIs on schedule; emit raw market events | Celery beat (schedule), PostgreSQL (raw storage), Redis (signal events) |
| **Signal Detector** | Consume raw events; apply detection logic (volume anomaly, breakout, insider, news catalyst); classify and score | PostgreSQL (write signals), Redis (pub/sub topic: `signals.detected`) |
| **Opportunity Queue** | Receive scored signals above threshold; deduplicate; enqueue for analysis | Redis (list/stream: `opportunities.pending`), PostgreSQL (opportunity table) |
| **Analysis Orchestrator** | Dequeue opportunities; spawn 5 persona agent tasks in parallel; wait for group completion; trigger merge | Celery (fan-out), Redis (results), PostgreSQL (analysis records) |
| **Persona Agent Workers** (x5) | One Celery worker per persona (Buffett, Munger, Ackman, Cohen, Dalio); execute LLM call with persona-specific system prompt + opportunity data; return structured JSON verdict | LLM API (OpenAI/Anthropic), PostgreSQL (write agent verdicts), Redis (publish progress) |
| **10X / Asymmetric Layer** | Apply asymmetric opportunity scoring pass over aggregated persona verdicts; flag outliers | Analysis Orchestrator (inline or separate Celery task), PostgreSQL |
| **Committee Aggregator** | Merge all persona verdicts + 10X score into committee view; compute consensus, dissent, conviction weight | PostgreSQL (read verdicts, write committee result) |
| **CIO Decision Engine** | Apply final decisioning rules (threshold, conviction, position sizing logic) against committee result; produce decision record | PostgreSQL (write decision), Redis (pub/sub topic: `decisions.new`) |
| **FastAPI Backend** | REST + SSE endpoints; receive scan triggers; expose opportunity/decision data; stream real-time events to frontend | PostgreSQL (read), Redis (subscribe), Celery (dispatch) |
| **Next.js Frontend** | React Flow graph visualization; SSE consumer for live updates; dashboard, alert config | FastAPI (HTTP + SSE) |
| **PostgreSQL** | Persistent store for all domain objects: signals, opportunities, agent verdicts, committee results, decisions, alerts | All backend components |
| **Redis** | Celery broker + result backend; pub/sub channels for real-time updates; opportunity stream | All backend components |
| **Celery Beat** | Periodic task scheduler — triggers market scanner workers on cron schedule | Market Scanner Workers |
| **Docker Compose** | Local orchestration of all services | All containers |

---

## Data Flow Diagram

```
INGESTION PLANE (background / scheduled)
=========================================

[Celery Beat]
    |
    | (cron: every N minutes)
    v
[Market Scanner Workers]
    | Poll Polygon.io / FMP REST APIs
    | Write raw OHLCV, news, insider filings to PostgreSQL
    v
[Signal Detector]  <-- reads raw market data from PostgreSQL
    | Apply detection rules:
    |   - Volume anomaly: current vol vs 20-day avg > threshold
    |   - Price breakout: close > N-day high with volume confirm
    |   - Insider activity: Form 4 filings above $X
    |   - News catalyst: sentiment score + ticker mention spike
    | Score signal confidence (0-100)
    | Write Signal record to PostgreSQL
    | Publish to Redis channel: signals.detected
    v
[Opportunity Scorer]
    | Consume signals.detected
    | Deduplicate by ticker + signal_type within TTL window
    | Apply composite score (signal strength + market cap filter + liquidity)
    | If score >= THRESHOLD:
    |     Write Opportunity record to PostgreSQL (status: QUEUED)
    |     Push opportunity_id to Redis stream: opportunities.pending
    v
[Redis stream: opportunities.pending]


ANALYSIS PLANE (triggered per opportunity)
===========================================

[Analysis Orchestrator]  <-- consumes opportunities.pending
    |
    | Fan-out: dispatch 5 Celery tasks in parallel
    |   (group() chord in Celery)
    |
    +---> [Buffett Agent Worker]  ---> LLM call --> structured JSON verdict
    +---> [Munger Agent Worker]   ---> LLM call --> structured JSON verdict
    +---> [Ackman Agent Worker]   ---> LLM call --> structured JSON verdict
    +---> [Cohen Agent Worker]    ---> LLM call --> structured JSON verdict
    +---> [Dalio Agent Worker]    ---> LLM call --> structured JSON verdict
    |
    | Each worker:
    |   1. Fetches enriched opportunity data from PostgreSQL
    |   2. Constructs persona-specific prompt
    |   3. Calls LLM API (streaming or single-turn)
    |   4. Parses response into: {rating, conviction, thesis, risks, targets}
    |   5. Writes AgentVerdict to PostgreSQL
    |   6. Publishes progress event to Redis: analysis.progress.<opportunity_id>
    |
    | [Celery chord callback] -- fires when all 5 complete
    v
[10X / Asymmetric Layer]  (inline in chord callback or chained task)
    | Reads all 5 verdicts
    | Computes: consensus direction, conviction spread, asymmetric upside flag
    | Writes 10X score to Opportunity record
    v
[Committee Aggregator]
    | Produces CommitteeResult:
    |   - majority_direction (BUY/HOLD/AVOID)
    |   - conviction_weighted_score
    |   - dissenting_agents: []
    |   - key_thesis_points: []
    |   - key_risks: []
    | Writes CommitteeResult to PostgreSQL
    v
[CIO Decision Engine]
    | Applies decision rules:
    |   - Conviction >= threshold AND majority >= 3/5 -> APPROVED
    |   - High dissent -> WATCHLIST
    |   - Low conviction -> PASS
    | Writes Decision record to PostgreSQL
    | Publishes to Redis: decisions.new
    v
[FastAPI SSE endpoint]
    | Subscribes to Redis channels:
    |   - analysis.progress.<opportunity_id>
    |   - decisions.new
    | Streams events to connected frontend clients


FRONTEND PLANE (Next.js)
=========================

[Next.js Client]
    | HTTP: fetch opportunities list, decision history, agent verdicts
    | SSE: EventSource connects to /api/stream?opportunity_id=X
    |
    | React Flow Graph:
    |   - Nodes: Scanner, Signal Detector, Opportunity, 5 Persona Agents,
    |            10X Layer, Committee, CIO Decision
    |   - Edges animate when data flows through them
    |   - Node status: IDLE / PROCESSING / COMPLETE / ERROR
    |   - Updates driven by SSE events
    v
[User sees the system "come alive" in real-time]
```

---

## Database Schema (PostgreSQL — Core Tables)

### `signals`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| ticker | VARCHAR | e.g. AAPL |
| signal_type | ENUM | VOLUME_ANOMALY, BREAKOUT, INSIDER, NEWS_CATALYST |
| detected_at | TIMESTAMPTZ | |
| raw_data | JSONB | source-specific payload |
| confidence_score | DECIMAL(5,2) | 0-100 |
| source | VARCHAR | polygon, fmp, etc. |

### `opportunities`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| signal_id | UUID FK → signals | |
| ticker | VARCHAR | |
| composite_score | DECIMAL(5,2) | |
| status | ENUM | QUEUED, ANALYZING, COMMITTEE, DECIDED, ARCHIVED |
| asymmetric_flag | BOOLEAN | 10X layer output |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### `agent_verdicts`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| opportunity_id | UUID FK → opportunities | |
| persona | ENUM | BUFFETT, MUNGER, ACKMAN, COHEN, DALIO |
| direction | ENUM | BUY, HOLD, AVOID |
| conviction_score | DECIMAL(5,2) | 0-100 |
| thesis | TEXT | LLM-generated reasoning |
| risks | JSONB | array of risk strings |
| price_targets | JSONB | {low, base, high} |
| llm_model | VARCHAR | which model was used |
| created_at | TIMESTAMPTZ | |

### `committee_results`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| opportunity_id | UUID FK → opportunities | |
| majority_direction | ENUM | |
| conviction_weighted_score | DECIMAL(5,2) | |
| dissenting_agents | JSONB | array of persona names |
| key_thesis_points | JSONB | aggregated bullets |
| key_risks | JSONB | aggregated risks |
| created_at | TIMESTAMPTZ | |

### `decisions`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| opportunity_id | UUID FK → opportunities | |
| committee_result_id | UUID FK → committee_results | |
| outcome | ENUM | APPROVED, WATCHLIST, PASS |
| rationale | TEXT | |
| created_at | TIMESTAMPTZ | |

### `alerts` (optional, user-configured)
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| user_id | UUID | |
| trigger_type | ENUM | DECISION_APPROVED, TICKER_SIGNAL, etc. |
| filter_criteria | JSONB | e.g. {min_conviction: 80} |
| channel | ENUM | EMAIL, SLACK, WEBHOOK |
| active | BOOLEAN | |

### Supporting tables
- `raw_market_data` — time-series OHLCV (candidate for TimescaleDB hypertable)
- `scan_runs` — log of scanner executions, timing, errors
- `llm_call_logs` — audit log: prompt, response, tokens, latency, cost per call

---

## Suggested Build Order

**Phase 1 — Data Foundation**
Must exist before anything else can run.
1. Docker Compose skeleton (PostgreSQL, Redis, FastAPI stub, Celery worker stub)
2. PostgreSQL schema migrations (Alembic)
3. Celery + Redis configuration, beat scheduler setup
4. Polygon.io / FMP API clients (rate-limited, retry-safe)
5. Market scanner worker (raw OHLCV + news ingestion, scheduled)

**Phase 2 — Signal & Opportunity Pipeline**
Must exist before analysis can be triggered.
1. Signal detector logic (volume anomaly first — simplest)
2. Opportunity scorer + deduplication
3. Redis stream producer (opportunities.pending)
4. PostgreSQL writes for signals + opportunities
5. Basic FastAPI endpoints: GET /opportunities, GET /signals (read-only)

**Phase 3 — Agent Analysis Engine**
Core value delivery; requires Phase 1-2 complete.
1. Persona prompt library (one per investor, version-controlled)
2. Single-agent analysis task (one persona, prove round-trip works)
3. LLM call wrapper (streaming support, retry, cost logging)
4. Celery group/chord for parallel fan-out of all 5 agents
5. AgentVerdict persistence
6. 10X asymmetric scoring layer
7. Committee aggregator
8. CIO decision engine
9. Redis event publishing at each stage

**Phase 4 — Real-Time Frontend**
Requires Phase 3 pub/sub events to be working.
1. FastAPI SSE endpoint subscribing to Redis channels
2. Next.js SSE consumer (EventSource hook)
3. React Flow graph: static layout of all nodes
4. Dynamic node status updates driven by SSE events
5. Opportunity detail view (all 5 verdicts, committee result, decision)

**Phase 5 — Polish and Alerts**
1. Alert configuration UI + backend delivery (email/webhook)
2. Historical decision browser
3. Performance metrics dashboard
4. Additional signal detectors (breakout, insider, news catalyst)
5. Mobile-responsive layout audit

---

## Async vs Synchronous Boundaries

| Layer | Execution Model | Rationale |
|-------|----------------|-----------|
| Market scanner workers | Async background (Celery beat) | Must not block API; runs on schedule |
| Signal detection | Async background (Celery task) | CPU/IO bound; decoupled from ingestion |
| Opportunity scoring | Async background (Celery task) | Chained after signal detection |
| Persona agent LLM calls | Parallel async (Celery group) | 5 independent LLM calls; parallelization cuts latency ~5x |
| Committee + CIO logic | Async background (Celery chord callback) | Fires only when all 5 agents complete |
| FastAPI request handlers | Synchronous or async | Simple reads from PostgreSQL |
| SSE streaming endpoint | Async long-poll | Keeps HTTP connection open; subscribes to Redis |
| Frontend data fetches | Synchronous HTTP | REST calls for historical data |
| Frontend live updates | SSE (EventSource) | One-way server push; no WebSocket complexity needed |

---

## Real-Time Update Flow (Backend to Frontend)

The chosen mechanism is **Server-Sent Events (SSE)** over WebSocket. Rationale:

- Communication is one-directional (server pushes, client consumes)
- Works over standard HTTP — no special infrastructure, no nginx WebSocket proxy config
- Native browser EventSource API; reconnects automatically
- Sufficient for the "system feels alive" requirement

**Event flow:**

```
Celery Worker
    | publishes JSON event to Redis pub/sub channel
    | e.g. PUBLISH analysis.progress.{opportunity_id} '{"stage": "BUFFETT_COMPLETE", "verdict": {...}}'
    v
FastAPI SSE Handler
    | async Redis subscriber (aioredis)
    | listens on channel for opportunity_id
    | yields: data: {json payload}\n\n
    v
Next.js EventSource
    | receives event
    | updates React state
    v
React Flow node for that agent
    | transitions: PROCESSING -> COMPLETE
    | edge animates
    | verdict summary renders in node tooltip/panel
```

**Event types to emit:**
- `SCAN_RUN_STARTED` / `SCAN_RUN_COMPLETE` — scanner activity
- `SIGNAL_DETECTED` — new signal with ticker + type
- `OPPORTUNITY_QUEUED` — opportunity entered analysis queue
- `AGENT_STARTED` / `AGENT_COMPLETE` — per-persona status
- `COMMITTEE_COMPLETE` — aggregation done
- `DECISION_MADE` — final CIO outcome

---

## LLM Call Parallelization Strategy

**Pattern: Celery `group()` with `chord()` callback** (MEDIUM confidence — well-documented Celery pattern)

```python
from celery import group, chord

# Fan-out: 5 tasks in parallel
analysis_group = group(
    run_persona_analysis.s(opportunity_id, "BUFFETT"),
    run_persona_analysis.s(opportunity_id, "MUNGER"),
    run_persona_analysis.s(opportunity_id, "ACKMAN"),
    run_persona_analysis.s(opportunity_id, "COHEN"),
    run_persona_analysis.s(opportunity_id, "DALIO"),
)

# Fan-in: callback fires when all 5 complete
workflow = chord(analysis_group)(aggregate_committee.s(opportunity_id))
workflow.delay()
```

Each `run_persona_analysis` task:
1. Fetches opportunity context from PostgreSQL
2. Constructs persona-specific system prompt
3. Calls LLM API (synchronous within worker)
4. Parses and validates JSON response
5. Writes AgentVerdict to PostgreSQL
6. Publishes `AGENT_COMPLETE` event to Redis

**LLM call timing estimate:** ~8-15 seconds per call. With full parallelization, total analysis wall-clock time = time of slowest single agent (~15s) rather than 5 × 15s = 75s.

**Concurrency tuning:** Deploy Celery workers with `--concurrency=10` (I/O-bound LLM calls suit high concurrency). Each persona can share the same worker pool — no need for per-persona dedicated workers in MVP.

---

## Anti-Patterns to Avoid

### Synchronous LLM calls in API request path
**What:** Calling LLM APIs directly inside a FastAPI route handler and blocking until all 5 complete.
**Why bad:** 15-75 second HTTP response; client timeouts; no progress visibility; no retry capability.
**Instead:** Dispatch to Celery immediately; return `{opportunity_id, status: "QUEUED"}`; frontend subscribes to SSE for progress.

### Storing LLM outputs as unstructured free text
**What:** Saving the raw LLM string response to a TEXT column without schema enforcement.
**Why bad:** Aggregation, scoring, and committee logic become brittle string parsing; breaks on model updates.
**Instead:** Define a strict JSON schema for verdicts; validate at the worker level before persistence; fail + retry if parsing fails.

### Single Redis channel for all events
**What:** Publishing all events to one `events` channel; all clients subscribe to everything.
**Why bad:** Clients receive events for opportunities they're not viewing; O(clients × events) pub/sub fan-out.
**Instead:** Per-opportunity channels (`analysis.progress.{opportunity_id}`); frontend subscribes only to active opportunity.

### Polling instead of pub/sub for frontend updates
**What:** Frontend polls `GET /opportunities/{id}/status` every second.
**Why bad:** Unnecessary load; stale by up to 1 second; feels choppy not alive.
**Instead:** SSE subscription per active opportunity view; push events the moment they occur.

### TimescaleDB before proving correctness
**What:** Adding TimescaleDB hypertables in Phase 1 before schema is validated.
**Why bad:** Adds operational complexity (extension install, hypertable DDL) before data model is stable.
**Instead:** Plain PostgreSQL TIMESTAMPTZ indexed tables first; migrate to TimescaleDB hypertable only if query performance on raw market data becomes a bottleneck.

---

## Scalability Notes

| Concern | MVP (1 user, ~100 ops/day) | Scale-up (10+ users, 1000+ ops/day) |
|---------|--------------------------|--------------------------------------|
| LLM call cost | 5 calls × ~$0.01 = ~$0.05/opportunity; manageable | Add conviction pre-filter — only send high-score opportunities to full 5-agent analysis |
| Worker concurrency | Single Celery worker, concurrency=10 | Horizontal worker scaling; separate queues per workload type |
| PostgreSQL load | Trivial | Add read replicas; index on ticker + created_at |
| Redis | Single instance | Redis Cluster or Sentinel for HA |
| Celery broker | Redis as broker sufficient | Consider RabbitMQ broker + Redis result backend at high throughput |
| Scanner frequency | Every 15 minutes | Per-ticker streaming via WebSocket market data feeds |

---

## Sources

- Azure Architecture Center — AI Agent Orchestration Patterns (updated 2026-02-12): https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns
- TradingAgents: Multi-Agents LLM Financial Trading Framework (arXiv 2412.20138): https://arxiv.org/abs/2412.20138
- Handling Long-Running AI Jobs with Redis and Celery: https://markaicode.com/redis-celery-long-running-ai-jobs/
- FastAPI + Celery + Redis Production Guide (2025): https://medium.com/@dewasheesh.rana/celery-redis-fastapi-the-ultimate-2025-production-guide-broker-vs-backend-explained-5b84ef508fa7
- AI Agent Chat: Choosing Between WebSockets and SSE: https://www.karls.io/ai-agent-progress-chat-websocket-server-sent-events/
- Streaming AI Agents Responses with SSE: https://akanuragkumar.medium.com/streaming-ai-agents-responses-with-server-sent-events-sse-a-technical-case-study-f3ac855d0755
- React Flow — Node-Based UIs in React: https://reactflow.dev
- AI Agent Interfaces with React Flow (2025 pattern): https://damiandabrowski.medium.com/day-90-of-100-days-agentic-engineer-challenge-ai-agent-interfaces-with-react-flow-21538a35d098
- PostgreSQL Time-Series for Financial Data: https://www.bluetickconsultants.com/how-timescaledb-streamlines-time-series-data-for-stock-market-analysis/
- Agentic AI in Financial Services 2026: https://neurons-lab.com/article/agentic-ai-in-financial-services-2026/
