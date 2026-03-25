# Project Research Summary

**Project:** AI Hedge Fund — Multi-Agent Investment Discovery Platform
**Domain:** Proactive autonomous multi-agent AI investment discovery / alpha generation
**Researched:** 2026-03-25
**Confidence:** HIGH (stack fully verified; architecture and pitfalls cross-referenced with production sources and academic research)

## Executive Summary

This is a proactive, autonomous investment discovery platform built on a multi-agent LLM committee. Unlike reactive screeners or chatbots, the system runs continuously without user input: a background scanner ingests market data from Polygon.io and FMP, a signal detection layer filters for statistically anomalous events, and qualifying opportunities trigger a fan-out to five named investor persona agents (Buffett, Munger, Ackman, Cohen, Dalio) that each analyze the opportunity independently before a committee aggregates verdicts and a CIO meta-agent issues a final decision. The entire pipeline is visible in real-time through a React Flow agent graph. The architecture splits cleanly into two planes: an ingestion/scheduling plane (Celery Beat + workers + TimescaleDB) and an analysis plane (LangGraph agents + Celery chord fan-out + SSE push to frontend).

The recommended approach is to build strictly in dependency order: infrastructure and data foundation first, then signal pipeline, then agents, then real-time UI. The critical architectural insight is that the visual agent graph requires the pipeline to emit granular state events throughout processing — not just on completion. This event design must be established in Phase 1; retrofitting it onto a completed pipeline is painful and typically results in a full backend rewrite. The stack is mature and well-validated: FastAPI + LangGraph + Celery + TimescaleDB + Redis + React Flow is the consensus pattern for this class of system in 2025-2026.

The two most dangerous failure modes are cost explosion and sycophantic consensus. Unthrottled parallel LLM calls on noisy signals can reach $150-300/day within the first production week. And without explicit structural constraints forcing agent divergence, all five personas will converge on identical conclusions — a cosmetically multi-agent system with no analytical value. Both risks must be mitigated in Phase 1 before any real scanning begins, not addressed as post-launch cleanup.

---

## Key Findings

### Recommended Stack

The backend is FastAPI 0.135.2 with LangGraph 1.1.3 as the agent orchestration layer and Anthropic SDK 0.86.0 for Claude Sonnet 4.6. Celery 5.6.2 with Redis 7.x handles task queuing, scheduling (Celery Beat), and pub/sub for SSE fan-out. TimescaleDB (PostgreSQL extension) is the primary store — it handles both relational data (agent verdicts, committee results) and time-series market data (OHLCV hypertables) in a single engine, eliminating the need for a separate time-series database. SQLAlchemy 2.0 + Alembic handle ORM and migrations.

The frontend is a React 18 + TypeScript + Vite SPA (not Next.js — no SSR needed). React Flow v12 (`@xyflow/react`) renders the live agent graph. shadcn/ui + Tailwind CSS v4 provide the Bloomberg-style dark dashboard aesthetic. TanStack Query handles REST data fetching; Zustand manages UI state; SSE via the browser's `EventSource` API handles live updates. The SSE-over-WebSocket decision is correct: all updates are server-push only; WebSocket bidirectionality adds complexity for no benefit.

**Core technologies:**
- **FastAPI 0.135.2**: Async backend with SSE streaming support via `sse-starlette`
- **LangGraph 1.1.3**: Stateful agent graph with persistent state, `interrupt()` for human-in-loop, cross-agent memory store
- **anthropic 0.86.0**: Direct SDK; wrapped by `langchain-anthropic` for LangGraph integration
- **Celery 5.6.2 + Redis 7.x**: Task queue, beat scheduler, and SSE pub/sub channel — dual-role Redis eliminates a separate broker
- **TimescaleDB (pg16)**: PostgreSQL extension for time-series partitioning; SQLAlchemy/Alembic toolchain unchanged
- **React Flow v12**: Node-based agent graph visualization with custom nodes showing live status, confidence bars, and sparklines
- **SSE (not WebSocket)**: Unidirectional server-push over HTTP/2; native browser reconnect; no protocol upgrade needed
- **PydanticAI 1.71.0**: Used as output schema validator for each agent node's return type — not as the primary orchestrator

Full versions and install commands: see `STACK.md`.

### Expected Features

The key insight from FEATURES.md is that this system's differentiating value sits in three specific areas that no existing open-source alternative covers simultaneously: named investor personas with divergent analytical lenses, a real-time visual agent operating system, and proactive autonomous scanning. TradingAgents (ICML 2025) has the debate mechanism but no personas, no visual UI, and no autonomous loop. AutoHedge has clean architecture but no committee, no personas, no UI. Neither has the asymmetric/10x opportunity filter.

**Must have for MVP (table stakes):**
- Volume anomaly pre-filter before any LLM call — cheap pre-screen that reduces API cost dramatically
- Polygon.io + FMP data ingestion with retry and error handling
- Fundamental + sentiment + technical analyst agents (minimum 3 roles)
- Committee vote with at least 2 investor personas
- Persistent opportunity feed with conviction tier (Strong / Watch / Speculative)
- Persistent opportunity log in PostgreSQL (audit trail required for trust)
- Telegram alert on Strong conviction decisions

**Should have (differentiators, Phase 3-4):**
- Full 5-persona committee (Buffett, Munger, Ackman, Cohen, Dalio)
- Bull/bear structured debate with configurable rounds
- CIO meta-agent final decision layer
- Visual agent operating system (React Flow graph with live state)
- Agent disagreement score as a signal (disagreement delta surfaces contested opportunities)
- Asymmetric/10x filter (analyst coverage gap + short interest + catalyst proximity)
- Opportunity replay / history mode

**Defer to post-MVP (v2+):**
- Insider transaction signal layer (high value, adds complexity; Phase 4+)
- Regime detection / macro context injection agent
- Options flow signals (requires different data provider)
- Alternative data sources (SimilarWeb, job postings, credit card spend)

**Hard anti-features — never build:**
- Autonomous real-money execution (catastrophic risk for personal use; Knight Capital lost $440M in 45 minutes)
- Backtesting as a trust signal (backtested returns 30-40% better than live; strategy half-life now 11 months)
- Per-tick LLM calls (cost-prohibitive; LLMs are for reasoning, not streaming data)
- Confidence scores as percentages (LLM confidence is not calibrated probability; use qualitative tiers)

### Architecture Approach

The system has two distinct processing planes connected by Redis. The ingestion plane is background-scheduled: Celery Beat triggers market scanner workers on a cron, which write raw OHLCV and news data to TimescaleDB, then a signal detector applies detection rules and scores signals, and an opportunity scorer deduplicates and queues high-scoring candidates to a Redis stream. The analysis plane is event-triggered: an Analysis Orchestrator consumes the queue and fans out five persona agent tasks in parallel via a Celery group/chord, each agent independently calls the LLM and writes a structured verdict, then a Committee Aggregator and CIO Decision Engine run in sequence and publish the final decision to Redis, where FastAPI SSE subscribers stream it to the frontend.

**Major components:**
1. **Market Scanner Workers** — Celery Beat tasks; poll Polygon.io + FMP; write raw data to TimescaleDB; emit `SIGNAL_DETECTED` events
2. **Signal Detector + Opportunity Scorer** — applies volume anomaly / breakout / insider / news catalyst rules; deduplicates; quality-gates before LLM invocation
3. **Analysis Orchestrator + Persona Agent Workers** — Celery group fan-out of 5 parallel LLM calls; each worker constructs persona-specific prompt, calls Claude, validates JSON verdict schema, writes to DB, publishes `AGENT_COMPLETE` event
4. **Committee Aggregator + CIO Decision Engine** — Celery chord callback; computes conviction-weighted consensus, dissent score, and asymmetric flag; CIO applies final decision rules; publishes `DECISION_MADE`
5. **FastAPI SSE Layer** — subscribes to Redis channels per opportunity; streams events to frontend `EventSource`; also serves REST endpoints for historical data
6. **React Flow Frontend** — static graph layout of all nodes; node states animate via SSE events; opportunity detail view shows all 5 verdicts + committee result + CIO rationale

LLM call timing: ~8-15 seconds per call. With full parallelization, total analysis wall-clock time = slowest single agent (~15s) vs 75s sequential.

Database schema: see `ARCHITECTURE.md` for full table definitions (signals, opportunities, agent_verdicts, committee_results, decisions, alerts, raw_market_data, llm_call_logs).

### Critical Pitfalls

1. **Sycophantic LLM consensus (Critical — Phase 1)** — Without structural constraints, all 5 personas converge on identical outputs. Prevention: assign each agent a mandatory role structure; feed agents different data subsets to force information asymmetry (Buffett gets fundamentals only; Cohen gets price action only); score inter-agent variance and invalidate committee rounds below a minimum divergence threshold.

2. **API cost explosion from unthrottled LLM calls (Critical — Phase 1)** — 10 signals/hour × 5 Claude calls = 50 calls/hour; at Sonnet pricing this reaches $150-300/day before debugging traffic. Prevention: signal quality gate before any LLM call (composite score threshold); per-symbol deduplication in Redis; use Claude Haiku for triage and Sonnet only for confirmed high-quality signals; enable Anthropic Batch API (50% discount) for non-urgent queues; set hard daily spend limits in Anthropic console before any worker goes live.

3. **Hallucinated financial figures propagating through pipeline (Critical — Phase 1)** — LLMs fabricate specific P/E ratios, revenue figures, and earnings dates with high confidence. Prevention: inject all financial figures explicitly in a structured DATA CONTEXT block; system prompt must forbid recalling facts not in context; post-processing step cross-checks all numerical claims against the original data payload; keep prompts under 6,000 tokens to avoid context window mid-document loss.

4. **Celery worker state loss and duplicate signal processing (Critical — Phase 2)** — Workers crash mid-task; Chord callbacks fail silently on any unserializable exception; duplicates corrupt committee aggregation. Prevention: idempotency keys in Redis (`signal:{symbol}:{hash}:in_progress` with TTL); avoid Celery Chord for fan-out — use individual tasks + a Redis counter to track completion; pass only data references (IDs) as task arguments, never serialise large payloads.

5. **Signal detector noise flood (Critical — Phase 2)** — Over-eager scanning generates 90%+ noise, burning API budget and flooding the UI with low-quality alerts. Prevention: minimum signal quality bar requiring statistical anomaly on at least two independent indicators simultaneously; signal scoring model combining volume + momentum + fundamental trigger; no direct scanner-to-LLM wiring until scoring middleware exists.

---

## Implications for Roadmap

The architecture and pitfall research converge on the same 5-phase structure. Phase dependencies are hard: the visual UI requires the event system; the event system requires the analysis pipeline; the analysis pipeline requires signal quality gates; signal quality gates require the data foundation. Shortcuts in any phase propagate as rewrites in later phases.

### Phase 1: Infrastructure, Data Foundation, and Agent Design

**Rationale:** Nothing else can run without a working data pipeline and correctly structured agent prompts. Phase 1 pitfalls (sycophancy, hallucination, cost controls, data normalisation) are architectural decisions that cannot be patched later — they determine whether the entire system has analytical value.

**Delivers:** Docker Compose with all 7 services healthy; TimescaleDB schema and Alembic migrations; Polygon.io + FMP clients with canonical `FinancialSnapshot` normalisation layer; version-controlled persona prompt library with divergence-enforcing structure; LLM call wrapper with cost logging and daily spend limits wired.

**Addresses (from FEATURES.md):** Data ingestion foundation; error handling; audit log schema.

**Avoids (from PITFALLS.md):** Sycophantic consensus (prompt architecture), hallucinated figures (data injection pattern), data normalisation failures (canonical schema + field mappers), Docker service ordering failures (healthchecks + init migration service), prompt drift (prompts as versioned code files).

**Research flag:** Standard patterns — no additional research needed. FastAPI + Celery + TimescaleDB + Alembic setup is well-documented.

---

### Phase 2: Signal Detection and Opportunity Pipeline

**Rationale:** The signal quality gate is the primary cost control mechanism for the entire system. Building it before any LLM integration enforces the correct architecture: scanner output never reaches the LLM directly. This phase also establishes the Celery worker resilience patterns (idempotency, retry, rate limiting) that protect all downstream phases.

**Delivers:** Volume anomaly signal detector; opportunity scorer with composite threshold; Redis stream producer for `opportunities.pending`; Redis-based rate limiter (token bucket) shared across all workers; per-symbol deduplication cache; FastAPI read endpoints for signals and opportunities.

**Addresses (from FEATURES.md):** Volume anomaly pre-filter (table stakes); proactive scanning loop foundation; data source error handling.

**Avoids (from PITFALLS.md):** API cost explosion (quality gate before LLM invocation), noise flood (multi-indicator threshold before LLM), Celery state loss (idempotency keys + individual tasks + Redis counter), Polygon/FMP rate limit breaches (shared Redis token bucket), agent output logging (wire before any committee output is trusted).

**Research flag:** Standard patterns for Celery + Redis. The signal scoring model thresholds need empirical validation during implementation — treat initial thresholds as configurable and instrument false-positive rate from day one.

---

### Phase 3: Agent Analysis Engine

**Rationale:** This is the core value delivery. It requires Phase 1-2 complete (reliable data, working queue, prompt architecture established). The fan-out pattern must be tested with deliberate failure injection before any real LLM calls are integrated. The event publishing at each stage is not optional polish — it is the prerequisite for Phase 4's visual UI.

**Delivers:** Persona prompt library for all 5 investors; LangGraph-based single-agent round-trip (prove one persona end-to-end); Celery group fan-out of all 5 agents in parallel; AgentVerdict persistence with full structured schema; 10X asymmetric scoring layer; Committee Aggregator; CIO Decision Engine; Redis event publishing at every pipeline stage (`AGENT_STARTED`, `AGENT_COMPLETE`, `COMMITTEE_COMPLETE`, `DECISION_MADE`); disagreement delta calculation.

**Addresses (from FEATURES.md):** Named investor persona agents (key differentiator); bull/bear structured debate; CIO final decision layer; agent disagreement score as signal; conviction tier system.

**Avoids (from PITFALLS.md):** LLM output as unstructured text (strict JSON schema + Pydantic validation before persistence), synchronous LLM calls in API request path (all via Celery; API returns `QUEUED` immediately), equal agent weighting (design weighted voting schema now even before calibration data exists).

**Research flag:** Needs deeper research during planning. LangGraph chord integration with Celery is not a well-documented combination — plan a spike on the fan-out/fan-in pattern before committing to the full implementation. Persona prompt design is iterative; budget 2-3 tuning cycles per persona.

---

### Phase 4: Real-Time Frontend and Visual Agent Graph

**Rationale:** The frontend is the "wow" feature but requires Phase 3's event publishing to be working first. Building the static graph layout before wiring live data lets you validate the visual design before the live integration complexity. The SSE state recovery mechanism (Redis Streams + REST fallback) must be designed before wiring any SSE to node state — retrofitting reconnect logic is the most common cause of production UI bugs in event-driven systems.

**Delivers:** FastAPI SSE endpoint subscribing to per-opportunity Redis channels; React Flow static graph of all pipeline nodes; dynamic node status driven by SSE events (IDLE / PROCESSING / COMPLETE / ERROR); opportunity detail view (all 5 verdicts, committee result, CIO rationale, disagreement delta); SSE reconnect + state recovery via REST fallback endpoint; Telegram alert integration for Strong conviction decisions; Bloomberg-style dark dashboard aesthetic.

**Addresses (from FEATURES.md):** Visual agent operating system (key differentiator); opportunity feed; alert system; persistent opportunity log UI.

**Avoids (from PITFALLS.md):** React Flow re-render performance (memoized node components, batched updates over 500ms windows, `useStore` selectors), WebSocket/SSE state desync (Redis Streams not Pub/Sub; canonical event schema with correlation IDs; optimistic forward-only state transitions), polling anti-pattern (SSE push replaces polling).

**Research flag:** Standard patterns for React Flow + SSE. The update batching pattern is well-documented in React Flow performance docs. No additional research needed.

---

### Phase 5: Enrichment, Polish, and Observability

**Rationale:** Additional signal detectors, insider transaction layer, history browser, and agent track record system are valuable but don't change the core architecture. They extend a working Phase 1-4 system. This phase also adds the observability needed to identify prompt quality degradation and agent track record calibration.

**Delivers:** Additional signal detectors (breakout, insider cluster buying, news catalyst); insider transaction signal layer (FMP); opportunity replay / history mode; agent track record table and weighted voting calibration; performance metrics dashboard; internal output quality review interface; mobile-responsive layout audit; Flower task monitoring UI integration.

**Addresses (from FEATURES.md):** Insider transaction signal; regime detection / macro context agent (if scoped in); opportunity replay; asymmetric/10x filter refinement.

**Avoids (from PITFALLS.md):** No observability into agent output quality (weekly sampling + quality score logging), CIO aggregation ignoring track record (per-agent per-signal-type accuracy table now has calibration data from Phases 3-4).

**Research flag:** Regime detection / macro context injection is the most complex item here — if included, plan a research spike. Insider signal layer is straightforward (FMP endpoint + event trigger).

---

### Phase Ordering Rationale

- **Data before agents:** Agents are worthless without reliable, normalized data. The canonical `FinancialSnapshot` schema and field mappers cannot be added after agent prompts are built — they determine the prompt structure.
- **Signal quality gate before LLM integration:** This is the primary cost control. Adding the quality gate after connecting the scanner to LLM calls means the first thing you learn is your bill, not your signal quality.
- **Events before visual UI:** The React Flow graph has no meaning without live state events from the pipeline. The event schema and Redis Streams pattern must be established in Phase 3 — it cannot be a Phase 4 decision because it affects how each Celery worker publishes its outputs.
- **Agent design in Phase 1 (not Phase 3):** The divergence architecture (information asymmetry between agents, contrarian role structure, variance scoring) must be decided at prompt design time. You cannot add genuine disagreement to agents after the fact by tweaking prompts — the data partitioning strategy is baked into the data pipeline design.
- **Personas before committee:** Prove a single-agent round-trip works end-to-end before attempting the 5-agent fan-out. The chord/group pattern with deliberate failure injection must be validated before real LLM calls.

### Research Flags

Phases requiring deeper research during planning:
- **Phase 3 (Agent Analysis Engine):** LangGraph + Celery fan-out integration is not well-documented. Plan a dedicated spike before full implementation. Persona prompt design is iterative — budget explicit tuning cycles.
- **Phase 5 (Enrichment — Regime Detection):** If macro context injection is in scope, the regime classification model and data source need research.

Phases with standard patterns (can skip research-phase):
- **Phase 1:** FastAPI + Celery + TimescaleDB + Alembic setup is extensively documented. Docker Compose healthcheck patterns are standard.
- **Phase 2:** Celery + Redis rate limiting and idempotency patterns are well-documented. Signal scoring thresholds are empirical, not a research question.
- **Phase 4:** React Flow + SSE is well-documented. The update batching and state recovery patterns are in official React Flow performance docs.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified against PyPI/npm on 2026-03-25. Every technology choice cross-referenced with 2025-2026 production sources. SSE vs WebSocket decision is especially well-supported across multiple independent sources. |
| Features | MEDIUM-HIGH | Cross-referenced against 5 comparable systems (TradingAgents, AutoHedge, FinGPT, Perplexity Finance, Kavout) and academic research (ICML 2025). MVP feature set is clear. Differentiator implementation complexity (persona tuning, debate quality) carries inherent uncertainty. |
| Architecture | MEDIUM-HIGH | Patterns verified via Azure Architecture Center, TradingAgents paper, and FastAPI/Celery/Redis production guides. The Celery group/chord + LangGraph combination is the main uncertainty area — documented separately. Database schema is a suggested starting point, not a finalized design. |
| Pitfalls | HIGH | Sycophancy risk is backed by ACL 2025 (CONSENSAGENT) research. Cost explosion figures are based on current Anthropic published pricing. Celery chord failure modes are documented in production guides. React Flow performance issues are documented in official React Flow docs. |

**Overall confidence:** HIGH

### Gaps to Address During Planning

- **LangGraph + Celery integration:** The combination of LangGraph stateful graphs running inside Celery tasks is not a commonly documented pattern. A dedicated architecture spike (1-2 days) before Phase 3 planning is warranted to validate the worker design.
- **Persona prompt quality:** The effectiveness of the investor persona differentiation depends on prompt engineering quality that cannot be verified through research alone. Budget explicit evaluation cycles in Phase 3's timeline.
- **Signal scoring thresholds:** The specific thresholds for the signal quality gate (composite score, standard deviation cutoffs) are empirical. They should be treated as configurable parameters from day one, not hardcoded values — initial values need forward-testing to calibrate.
- **TimescaleDB migration timing:** ARCHITECTURE.md notes that hypertable conversion should happen only after schema is stable, not in Phase 1. The planning milestone for this migration should be explicit.
- **Celery Chord reliability:** PITFALLS.md specifically recommends avoiding Celery Chord for the agent fan-out in favor of a manual Redis counter pattern. This is a critical design decision that should be settled in Phase 3 planning before any implementation begins.

---

## Sources

### Primary (HIGH confidence — verified official sources)
- FastAPI SSE docs: https://fastapi.tiangolo.com/tutorial/server-sent-events/
- LangGraph v1.1.3 release / PyPI verified 2026-03-25
- TradingAgents paper (ICML 2025): https://arxiv.org/abs/2412.20138 and https://tradingagents-ai.github.io/
- React Flow v12: https://xyflow.com/blog/react-flow-12-release and https://reactflow.dev/learn/advanced-use/performance
- shadcn/ui (updated Mar 2026): https://ui.shadcn.com/
- TimescaleDB Docker: https://docs.timescale.com/self-hosted/latest/install/installation-docker/
- Anthropic API pricing and rate limits: https://platform.claude.com/docs/en/api/rate-limits
- Azure Architecture Center — AI Agent Orchestration Patterns: https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns

### Secondary (MEDIUM confidence — community/cross-referenced sources)
- CONSENSAGENT sycophancy research (ACL 2025): https://aclanthology.org/2025.findings-acl.1141/
- Celery vs ARQ / Dramatiq comparison 2025: https://leapcell.io/blog/celery-versus-arq-choosing-the-right-task-queue-for-python-applications
- LangGraph vs CrewAI vs PydanticAI 2026 guide: https://dev.to/linou518/the-2026-ai-agent-framework-decision-guide-langgraph-vs-crewai-vs-pydantic-ai-b2h
- FastAPI + Celery + Redis production guide 2025: https://medium.com/@dewasheesh.rana/celery-redis-fastapi-the-ultimate-2025-production-guide-broker-vs-backend-explained-5b84ef508fa7
- LLM hallucinations in financial institutions: https://biztechmagazine.com/article/2025/08/llm-hallucinations-what-are-implications-financial-institutions
- AutoHedge guide (Nov 2025): https://www.blog.brightcoding.dev/2025/11/26/autohedge-build-your-autonomous-ai-hedge-fund-in-minutes-2025-guide/
- FinGPT capabilities assessment (arxiv 2025): https://arxiv.org/html/2507.08015v1

### Tertiary (supporting context)
- React stack 2025 recommendation: https://x.com/housecor/status/1948105214017380774
- Polygon/Massive.com rebranding note: https://www.ksred.com/the-complete-guide-to-financial-data-apis-building-your-own-stock-market-data-pipeline-in-2025/
- All PyPI package versions verified: 2026-03-25

---
*Research completed: 2026-03-25*
*Ready for roadmap: yes*
