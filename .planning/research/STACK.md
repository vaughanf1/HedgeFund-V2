# Technology Stack

**Project:** AI Hedge Fund — Multi-Agent Investment Discovery Platform
**Researched:** 2026-03-25
**Research Mode:** Ecosystem (Stack dimension)
**Overall Confidence:** HIGH (all versions verified against PyPI/npm, rationale cross-referenced with 2025-2026 sources)

---

## Recommended Stack at a Glance

| Layer | Choice | Version |
|-------|--------|---------|
| Python backend framework | FastAPI | 0.135.2 |
| Agent orchestration | LangGraph | 1.1.3 |
| LLM SDK | anthropic | 0.86.0 |
| Data validation | Pydantic v2 | 2.12.5 |
| Task queue | Celery | 5.6.2 |
| Task scheduler | Celery Beat (built-in) | — |
| Message broker / cache | Redis | 7.x (Docker: redis:7-alpine) |
| Primary database | TimescaleDB (PostgreSQL extension) | 2.18+ (Docker: timescale/timescaledb:latest-pg16) |
| ORM | SQLAlchemy | 2.0.48 |
| Migrations | Alembic | 1.18.4 |
| Market data — prices/news | polygon-api-client | 1.16.3 |
| Frontend framework | React 18 + TypeScript + Vite | React 18.x, Vite 5.x |
| Agent graph visualization | @xyflow/react (React Flow v12) | 12.x |
| UI components | shadcn/ui + Radix UI + Tailwind CSS v4 | — |
| Server state | TanStack Query | 5.x |
| Client state | Zustand | 4.x |
| Real-time transport | Server-Sent Events (SSE) via FastAPI | — |
| Containerisation | Docker Compose v2 | — |

---

## Detailed Rationale by Layer

### 1. Python Backend Framework — FastAPI 0.135.2

**Why FastAPI:**
FastAPI is the standard choice for AI/agent backend services in 2025. Its native async/await support is critical for two reasons unique to this project: (1) calling the Anthropic API and Polygon.io WebSocket stream concurrently without blocking, and (2) streaming SSE events to the frontend while agent tasks run. FastAPI's `EventSourceResponse` (via the `sse-starlette` package) is the idiomatic pattern for pushing live agent state updates. It uses Pydantic v2 natively for request/response validation, which eliminates a separate serialisation layer.

**Why not Flask / Django:**
Both are synchronous by default. Django's ORM conflicts with TimescaleDB's hypertable patterns. Flask has no async streaming primitives. Neither are used for new AI services in 2025.

**Why not Litestar:**
Technically superior on benchmarks but small ecosystem, thin community resources for agent patterns, and almost no tutorials exist for the Anthropic SDK integration patterns needed here.

---

### 2. Agent Orchestration — LangGraph 1.1.3

**Why LangGraph:**
This project requires stateful, long-running agents that poll markets, accumulate context over multiple ticks, and hand off signals between personas. LangGraph's directed graph model maps directly to that pattern: each investor persona (Buffett, Munger, etc.) is a subgraph node with persistent state. LangGraph v1.0 (stable since Oct 2024) ships `interrupt()` for human-in-the-loop pauses, `Command` for flow control, and a `Store` API for cross-agent memory — all features this system needs.

LangGraph also integrates directly with Anthropic's Claude via `langchain-anthropic`, meaning the persona agents can call `claude-sonnet-4-6` with tool use (structured fundamental analysis, news scoring) without custom plumbing.

**Why not CrewAI:**
CrewAI's role-based abstraction is better for one-shot research tasks. This system needs long-running polling loops with stateful accumulation between cycles — CrewAI's architecture fights that pattern.

**Why not PydanticAI alone:**
PydanticAI (v1.71.0) is excellent for structured output enforcement on individual LLM calls. Use it alongside LangGraph for validating each agent's output schema, but it lacks LangGraph's stateful graph execution model needed for the polling loop.

**Why not raw Anthropic SDK:**
Viable but requires hand-rolling the state graph, retry logic, tool dispatch, and inter-agent message passing. LangGraph provides all of this tested and maintained.

**Recommended pattern:** LangGraph graph per persona agent, each node calling Anthropic via `langchain-anthropic`. PydanticAI models used as the output type contracts for each node's return value.

---

### 3. LLM SDK — anthropic 0.86.0

**Why direct Anthropic SDK:**
The project is locked to `claude-sonnet-4-6`. The anthropic Python SDK (0.86.0) supports streaming, tool use, and the Messages API. LangGraph's `langchain-anthropic` adapter wraps this SDK — you get the graph ergonomics of LangGraph plus access to raw SDK for any model-specific tuning.

---

### 4. Task Queue — Celery 5.6.2 + Redis broker

**Why Celery:**
Each market scan cycle (fetch Polygon data → run 5 persona agents → store signals → push SSE) is a multi-step async pipeline that must survive restarts, support retries on API failures, and allow monitoring. Celery with Redis broker provides all three.

**Why Celery over ARQ:**
ARQ is asyncio-native and lighter, but its task visibility and retry semantics are weaker. For a system where a failed Anthropic call at step 3 of 5 must retry only that step — not the whole chain — Celery's task primitives (chords, chains, retry backoff) are necessary.

**Why Celery over Dramatiq:**
Dramatiq has better raw throughput but lacks Celery's built-in scheduler (Celery Beat) needed for cron-style market scan intervals. Adding a separate APScheduler alongside Dramatiq duplicates infrastructure; Celery Beat eliminates that.

**Scheduling:** Use Celery Beat for periodic market scan tasks (e.g., every 5 minutes during market hours). No APScheduler needed separately.

**Monitoring:** Flower (Celery monitoring UI) added as a Docker Compose service for visibility into task queues.

---

### 5. Database — TimescaleDB (PostgreSQL extension)

**Why TimescaleDB over plain PostgreSQL:**
The system stores: (a) time-series price/volume ticks from Polygon, (b) agent signal events with timestamps, (c) fundamentals snapshots from FMP. All three are append-heavy time-series writes with range queries. TimescaleDB's hypertables provide automatic time-based partitioning, native `time_bucket()` aggregations, and 3-8x compression on historical data — none of which vanilla PostgreSQL offers without manual partitioning work.

Critically, TimescaleDB is a PostgreSQL extension, not a separate database engine. The entire SQLAlchemy + Alembic toolchain works unchanged. Docker image `timescale/timescaledb:latest-pg16` is a drop-in.

**Why not InfluxDB:**
InfluxDB 3.0 uses a custom query language (or Flux) and has no relational model. The agent signals need JOINs between time-series events and relational metadata (ticker symbols, persona configs, decisions). TimescaleDB handles both natively. InfluxDB's compression advantage does not outweigh the query complexity cost for this use case.

**Why not plain Redis for storage:**
Redis is ephemeral by default, requires manual data modelling for time-series, and has no SQL query surface. Use Redis only as the Celery broker and SSE pub/sub channel.

**Secondary storage:** Redis (7.x) for Celery broker, SSE fan-out, and per-agent working memory cache (agent state between ticks).

---

### 6. ORM + Migrations — SQLAlchemy 2.0.48 + Alembic 1.18.4

**Why SQLAlchemy 2.0:**
The 2.0 API is the current standard. It has full async support (`AsyncSession` with `asyncpg` driver), native Pydantic v2 integration, and works with TimescaleDB hypertables via raw SQL extensions when needed. The `mapped_column()` declarative style reduces boilerplate significantly vs 1.x.

**Why Alembic:**
The de facto standard for SQLAlchemy schema migrations. `--autogenerate` detects model changes. Docker entrypoint pattern: run `alembic upgrade head` before starting the FastAPI app.

---

### 7. Market Data APIs

**Polygon.io — polygon-api-client 1.16.3**
The official Python client. Supports both REST (historical OHLCV, news) and WebSocket streaming (real-time trades, quotes). Note: Polygon.io rebranded as Massive.com in Oct 2025, but API keys and `api.polygon.io` endpoint remain valid. The SDK defaults to `api.massive.com` in 1.16.x but supports both.

**Financial Modeling Prep — requests / httpx (no dedicated SDK)**
FMP has no official Python SDK with the quality of polygon-api-client. Use `httpx` (async HTTP) directly against their REST API. Endpoints needed: `/financial-statements/`, `/insider-trading/`, `/ratios/`. Cache aggressively — fundamentals change quarterly.

---

### 8. Frontend Framework — React 18 + TypeScript + Vite

**Why React + Vite (not Next.js):**
This is a single-user local app with no SEO, no SSR requirements, and no server components. Next.js overhead (file-based routing, RSC complexity, build tooling) is unnecessary. Vite provides sub-second HMR for rapid UI iteration. Plain React SPA with TanStack Router for client-side routing is the right fit.

**Why TypeScript:**
The agent state objects (graph nodes, signal payloads, SSE event types) are complex nested structures. TypeScript catches mismatches between FastAPI Pydantic models and frontend types at compile time. Generate frontend types from FastAPI's `/openapi.json` using `openapi-typescript`.

---

### 9. Agent Graph Visualization — @xyflow/react (React Flow v12)

**Why React Flow:**
React Flow v12 is the standard library for node-based UIs in React in 2025. It directly maps to the mental model of this system: each investor persona agent is a node, data flows between them are edges, and the operating system view shows real-time state transitions. React Flow's custom node API allows embedding live sparklines, signal counters, and status indicators inside each agent node.

React Flow v12 added server-side rendering support, improved performance for viewport-heavy graphs, and a `onBeforeDelete` hook for guarded node interactions.

**Why not D3-force or vis.js:**
D3's learning curve for interactive node UIs is high, and it requires manual React integration. vis.js is not React-native and has limited TypeScript support. React Flow has 25k+ GitHub stars and is actively maintained for exactly this use case.

---

### 10. UI Components — shadcn/ui + Tailwind CSS v4

**Why shadcn/ui:**
shadcn/ui is the dominant React component library for custom dashboards in 2025. Components ship as TypeScript source you own — no runtime library dependency, full Tailwind customisation, built on Radix UI primitives for accessibility. The March 2026 shadcn/cli v4 release improved code generation. Ideal for the data-dense, financial dashboard aesthetic.

**Why Tailwind CSS v4:**
v4 (released early 2025) ships with CSS variables by default, improved performance, and a simpler config. Paired with shadcn/ui it covers all layout, colour, typography, and spacing needs without a separate CSS codebase.

---

### 11. State Management

**TanStack Query 5.x — server state**
Handles all API calls to the FastAPI backend: fetching signal history, agent configs, decision logs. Provides caching, background refetch, and optimistic updates. Works alongside SSE — TanStack Query for initial load and historical data; SSE for live streaming updates.

**Zustand 4.x — client state**
Manages UI state: which agent is selected, panel open/closed, animation states of React Flow nodes. Lightweight, no boilerplate, TypeScript-native. The combination of TanStack Query (server) + Zustand (client) is the 2025 consensus stack, confirmed by Cory House's widely circulated 2025 React stack recommendation.

---

### 12. Real-Time Transport — Server-Sent Events (SSE)

**Why SSE over WebSockets:**
This system has a unidirectional update pattern: server pushes agent state changes, signal events, and market tick summaries to the browser. SSE is one-directional (server → client), works over standard HTTP/2, and the browser's native `EventSource` API handles reconnection automatically. There is no user action that needs to be pushed from browser to backend in real-time — all user interactions are REST calls.

WebSockets add bidirectional complexity (heartbeating, protocol upgrade, connection state management) for no benefit in this use case.

**Implementation pattern:**
- FastAPI endpoint: `GET /stream/agent-events` returns `EventSourceResponse` (via `sse-starlette`)
- Agent tasks publish events to a Redis pub/sub channel when state changes
- FastAPI SSE endpoint subscribes to Redis and yields events to the browser
- Frontend: `EventSource` API (or `@microsoft/fetch-event-source` for custom headers) consumes the stream and updates Zustand + React Flow node states

---

## Docker Compose Service Breakdown

```yaml
services:

  # --- Data Layer ---
  db:
    image: timescale/timescaledb:latest-pg16
    # TimescaleDB = PostgreSQL + time-series extension. One container, no separate DB.
    ports: ["5432:5432"]
    volumes: [db_data:/var/lib/postgresql/data]
    environment:
      POSTGRES_DB: hedgefund
      POSTGRES_USER: app
      POSTGRES_PASSWORD: secret
    command: postgres -c shared_preload_libraries=timescaledb

  redis:
    image: redis:7-alpine
    # Dual role: Celery broker + SSE pub/sub channel
    ports: ["6379:6379"]
    volumes: [redis_data:/data]
    command: redis-server --appendonly yes

  # --- Backend ---
  api:
    build: ./backend
    # FastAPI app: REST endpoints + SSE streaming
    ports: ["8000:8000"]
    depends_on: [db, redis]
    environment:
      DATABASE_URL: postgresql+asyncpg://app:secret@db/hedgefund
      REDIS_URL: redis://redis:6379/0
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      POLYGON_API_KEY: ${POLYGON_API_KEY}
      FMP_API_KEY: ${FMP_API_KEY}
    command: >
      sh -c "alembic upgrade head &&
             uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

  worker:
    build: ./backend
    # Celery worker: executes market scan tasks + runs LangGraph agent pipelines
    depends_on: [db, redis]
    environment:
      DATABASE_URL: postgresql+asyncpg://app:secret@db/hedgefund
      REDIS_URL: redis://redis:6379/0
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      POLYGON_API_KEY: ${POLYGON_API_KEY}
      FMP_API_KEY: ${FMP_API_KEY}
    command: celery -A app.worker worker --loglevel=info --concurrency=4

  beat:
    build: ./backend
    # Celery Beat: cron scheduler for periodic market scans
    depends_on: [redis]
    environment:
      REDIS_URL: redis://redis:6379/0
    command: celery -A app.worker beat --loglevel=info

  flower:
    image: mher/flower:2.0
    # Task queue monitoring UI
    ports: ["5555:5555"]
    depends_on: [redis]
    environment:
      CELERY_BROKER_URL: redis://redis:6379/0

  # --- Frontend ---
  frontend:
    build: ./frontend
    # React + Vite SPA: Agent OS visualisation
    ports: ["3000:3000"]
    depends_on: [api]

volumes:
  db_data:
  redis_data:
```

**Service count: 6** (db, redis, api, worker, beat, flower, frontend — 7 with frontend)

---

## Alternatives Considered and Rejected

| Category | Recommended | Rejected | Reason Rejected |
|----------|-------------|----------|-----------------|
| Agent orchestration | LangGraph 1.1.3 | CrewAI | CrewAI is one-shot task oriented; no stateful polling loop support |
| Agent orchestration | LangGraph 1.1.3 | PydanticAI (as sole orchestrator) | PydanticAI lacks graph execution model; use as output validator alongside LangGraph |
| Task queue | Celery 5.6.2 | ARQ | ARQ has weak retry semantics, no built-in beat scheduler |
| Task queue | Celery 5.6.2 | Dramatiq | Lacks native beat scheduler; would require adding APScheduler separately |
| Database | TimescaleDB | InfluxDB 3.0 | Non-relational model; no SQL JOINs; custom query language |
| Database | TimescaleDB | Plain PostgreSQL | No time-series partitioning; manual hypertable work; no `time_bucket()` |
| Real-time | SSE | WebSocket | Bidirectional complexity unnecessary; this is server-push only |
| Frontend build | Vite | Next.js | No SSR/SEO need; Next.js overhead unjustified for single-user local SPA |
| Graph viz | React Flow v12 | D3-force | High integration complexity; not React-native |
| Component library | shadcn/ui | MUI / Ant Design | Heavy bundle, opinionated visual style conflicts with custom financial aesthetic |
| State — server | TanStack Query | Redux Toolkit Query | RTK Query adds Redux overhead; TanStack Query is lighter and more ergonomic |

---

## Key Library Install Reference

### Backend (Python)

```bash
# Core
pip install fastapi==0.135.2 uvicorn[standard] sse-starlette
pip install anthropic==0.86.0
pip install langgraph==1.1.3 langchain-anthropic
pip install pydantic==2.12.5 pydantic-ai==1.71.0
pip install celery[redis]==5.6.2 flower

# Database
pip install sqlalchemy==2.0.48 alembic==1.18.4 asyncpg psycopg2-binary

# Data APIs
pip install polygon-api-client==1.16.3 httpx

# Redis client
pip install redis==7.4.0
```

### Frontend (Node)

```bash
# Core
npm install react@18 react-dom@18 typescript vite
npm install @tanstack/react-query@5 zustand@4

# Graph visualisation
npm install @xyflow/react

# UI
npm install tailwindcss@4 shadcn-ui
# (shadcn components added via: npx shadcn@latest add <component>)

# Type generation from OpenAPI
npm install -D openapi-typescript
```

---

## Confidence Assessment

| Area | Level | Source | Notes |
|------|-------|--------|-------|
| FastAPI | HIGH | PyPI verified (0.135.2) + official docs | Stable, production standard |
| LangGraph | HIGH | PyPI verified (1.1.3) + multiple 2025 production case studies | v1.0 stable since Oct 2024 |
| Anthropic SDK | HIGH | PyPI verified (0.86.0) | Actively maintained |
| Celery | HIGH | PyPI verified (5.6.2) + 2025 comparison articles | Mature, battle-tested |
| TimescaleDB | HIGH | Docker Hub verified + official docs | timescaledb 2.18+ on pg16 |
| SQLAlchemy | HIGH | PyPI verified (2.0.48) | 2.0 async API is stable |
| Alembic | HIGH | PyPI verified (1.18.4) | De facto standard |
| React Flow v12 | HIGH | xyflow.com official blog + npm | Latest stable major |
| shadcn/ui | HIGH | ui.shadcn.com (updated Mar 2026) | Dominant in 2025-2026 |
| TanStack Query | HIGH | tanstack.com official docs | v5 stable |
| SSE over WebSocket | HIGH | Multiple official FastAPI + IBM sources agree | Correct pattern for unidirectional push |
| Polygon SDK version | HIGH | PyPI verified (1.16.3) | Note: rebranded to Massive.com Oct 2025 |
| PydanticAI | MEDIUM | PyPI verified (1.71.0) but role is supporting validator, not primary orchestrator | Newer library, patterns still maturing |

---

## Sources

- FastAPI SSE docs: https://fastapi.tiangolo.com/tutorial/server-sent-events/
- LangGraph release: https://github.com/JoshuaC215/agent-service-toolkit
- React Flow v12: https://xyflow.com/blog/react-flow-12-release
- shadcn/ui: https://ui.shadcn.com/
- TimescaleDB Docker: https://docs.timescale.com/self-hosted/latest/install/installation-docker/
- Celery vs ARQ: https://leapcell.io/blog/celery-versus-arq-choosing-the-right-task-queue-for-python-applications
- Python task queues 2025: https://devproportal.com/languages/python/python-background-tasks-celery-rq-dramatiq-comparison-2025/
- LangGraph vs PydanticAI vs CrewAI: https://dev.to/linou518/the-2026-ai-agent-framework-decision-guide-langgraph-vs-crewai-vs-pydantic-ai-b2h
- TimescaleDB vs InfluxDB: https://www.timescale.com/blog/timescaledb-vs-influxdb-for-time-series-data-timescale-influx-sql-nosql-36489299877
- React stack 2025: https://x.com/housecor/status/1948105214017380774
- Polygon rebranding note: https://www.ksred.com/the-complete-guide-to-financial-data-apis-building-your-own-stock-market-data-pipeline-in-2025/
- All PyPI versions verified 2026-03-25
