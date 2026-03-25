# Domain Pitfalls: AI Hedge Fund / Multi-Agent Investment Discovery Platform

**Domain:** Proactive AI trading system with multi-agent LLM committee
**Researched:** 2026-03-25
**Research Mode:** Pitfalls dimension — Greenfield milestone

---

## Critical Pitfalls

Mistakes that cause rewrites, major production incidents, or fundamental loss of trust in the system.

---

### Pitfall 1: LLM Agents Achieve Sycophantic Consensus Instead of Genuine Disagreement

**What goes wrong:** All five persona agents (Buffett, Munger, Ackman, Cohen, Dalio) reach the same conclusion on nearly every signal, not because they agree analytically, but because LLMs are trained to be agreeable. When agent outputs feed into a committee layer, sycophantic cascades move through the system in seconds — faster than any human review cycle.

**Why it happens:** LLMs default toward consensus when given similar input context. Without explicit structural constraints forcing divergence, personas become cosmetic wrappers on the same underlying reasoning. Research at ACL 2025 (CONSENSAGENT) identifies sycophancy as the primary mechanism through which groupthink emerges in multi-agent LLM debate.

**Consequences:** The committee always signals "BUY" or always signals "HOLD." The system produces no real analytical differentiation. The entire value proposition of a multi-persona committee collapses.

**Prevention:**
- Assign each agent a mandatory contrarian role structure in the system prompt: one agent must always argue the bear case, one must challenge valuation assumptions, one must challenge timing.
- Feed agents different subsets of input data (Buffett agent gets fundamentals only; Cohen agent gets price action and momentum only) to create information asymmetry that forces genuine divergence.
- Score agent outputs for inter-agent agreement — if variance is below a threshold, the committee round is invalid and must re-run with temperature increased.
- Use structured debate format: Agent A proposes → Agent B critiques → Agent A defends → CIO arbitrates.

**Detection (warning signs):**
- Agreement rate across agents exceeds 80% over any 24-hour window.
- Committee overrides CIO layer less than 5% of the time.
- All agents produce similar token-length responses.

**Build phase:** Address in Phase 1 (agent prompt design). Do not proceed to committee aggregation layer until disagreement is measurable and consistent.

---

### Pitfall 2: API Cost Explosion from Unthrottled Parallel LLM Calls

**What goes wrong:** Celery workers continuously scan Polygon.io for signals. Each signal triggers 5 parallel Claude API calls (one per persona). At even modest signal detection rates (10 signals/hour), you have 50 Claude calls/hour. At Claude Sonnet 4.6 pricing ($3 input / $15 output per million tokens) with rich financial context in each prompt (2,000–4,000 input tokens, 500–1,000 output tokens), costs reach $150–300/day before any testing or debugging traffic.

**Why it happens:** There is no back-pressure between the signal detector and the LLM invocation layer. Background workers are designed to be efficient at detection — but that efficiency becomes a cost liability when each detection unconditionally triggers expensive downstream calls.

**Consequences:** Unexpected $4,000–9,000/month API bills within the first production week. Anthropic enforces weekly spend limits at scale and will rate-limit or suspend accounts.

**Prevention:**
- Implement a signal quality gate before any LLM call: only signals scoring above a configurable threshold (e.g., composite score > 0.7) trigger agent analysis.
- Apply per-symbol deduplication: if a symbol triggered analysis within the last N hours, skip.
- Use Claude Haiku for initial triage / pre-screening and only escalate high-confidence signals to Sonnet for full committee analysis.
- Use the Anthropic Batch API (50% discount) for non-urgent analysis queues.
- Implement prompt caching for shared system prompt context (base persona instructions) — cache reads cost 10% of base input price.
- Set hard daily spend limits in the Anthropic console and wire an alert when 70% is consumed.
- Log token usage per signal type to identify which signal categories generate the most cost.

**Detection (warning signs):**
- No `max_signals_per_hour` configuration in the Celery worker.
- No deduplication cache in Redis keyed by `symbol:signal_type:timestamp_window`.
- LLM call is made unconditionally on any scanner hit.

**Build phase:** Address in Phase 1 before any real signal scanning. Wire cost tracking before any Celery worker goes live.

---

### Pitfall 3: Hallucinated Financial Figures Propagate Through the Agent Pipeline

**What goes wrong:** LLM agents confidently state specific financial metrics (P/E ratios, revenue figures, debt levels, earnings dates) that are fabricated or outdated. Because the output looks authoritative and numerically precise, downstream committee aggregation treats it as ground truth. Even at a 10–20% hallucination rate on complex financial reasoning (documented in 2025 research), the system generates unreliable committee outputs.

**Why it happens:** LLMs are trained to predict probable token sequences, not to verify factual accuracy. Financial figures are especially vulnerable because numbers change continuously and the model's training data is months to years stale. When context windows overflow (e.g., large earnings reports), the model starts silently dropping early context — so Microsoft Q3 figures can end up in Apple Q4 analysis.

**Consequences:** Investment theses built on invented data. Positions initiated based on metrics the target company never actually reported. Legal and reputational exposure if the system is used for real trading decisions.

**Prevention:**
- All financial figures cited by agents must be grounded in data passed explicitly in the prompt context — agents should never be asked to recall facts from training.
- Use a retrieval-verified analysis loop: the data pipeline fetches and normalises metrics from Polygon.io/FMP, injects them as structured context, and agents are instructed to cite only from the provided context block.
- Add a post-processing verification step: extract all numerical claims from agent output and cross-check against the original data payload before forwarding to committee.
- System prompt must include: "Only reference numbers provided in the DATA CONTEXT section below. If a figure is not in the data context, state 'data unavailable' rather than estimating."
- Keep individual agent prompts under 6,000 tokens total to avoid context window mid-document loss.

**Detection (warning signs):**
- Agent outputs cite figures not present in the injected data payload.
- Prompts include general instructions like "analyse this company" without structured data context.
- No automated extraction and cross-check of numeric claims.

**Build phase:** Address in Phase 1 (prompt architecture). The data injection pattern must be established before any agent output is trusted.

---

### Pitfall 4: Celery Worker State Loss and Duplicate Signal Processing

**What goes wrong:** Celery workers crash mid-task, leaving partial state. On restart, tasks re-execute and the same signal triggers multiple committee analyses. Alternatively, Chord/Group workflows used for fan-out to five agents fail silently when any single agent call raises an unserializable exception — the chord callback never fires, the result is lost, and there is no visibility into the failure.

**Why it happens:** Celery amplifies distributed system coordination problems. The combination of five parallel LLM calls per signal (all of which can fail independently), Redis as both broker and result backend, and long-running tasks (LLM calls can take 15–45 seconds) creates many failure points. Celery Canvas (chord/group) has documented issues with task loss on exception propagation.

**Consequences:** Duplicate analyses for the same signal. Lost analyses with no error surfaced to the UI. Redis result backend accumulating stale, unclaimed task results. Workers stuck in retry loops with exponential backoff causing compounding API costs.

**Prevention:**
- Use idempotency keys: before processing any signal, write a Redis key `signal:{symbol}:{signal_hash}:in_progress` with a TTL of 10 minutes. If the key exists, skip.
- Use `bind=True` on all Celery tasks and implement explicit retry with `max_retries=3` and `countdown` backoff.
- Avoid Celery Chord for the agent fan-out. Instead, use individual tasks with a Redis counter to track completion and trigger the committee aggregation task manually when all five agent results arrive.
- Pass only data references (symbol, timestamp, signal ID) as task arguments — never serialise large data payloads into the task message. Fetch context from PostgreSQL/Redis inside the task.
- Implement a dead-letter queue for tasks that exceed max retries.
- Monitor `celery inspect active` and `celery inspect reserved` regularly.

**Detection (warning signs):**
- Task arguments include large data structures (>1KB) being serialised into the broker.
- Using Celery Chord without explicit exception handling for each child task.
- No idempotency key check at task entry.

**Build phase:** Address in Phase 2 (Celery worker architecture). The fan-out pattern must be tested with deliberate failure injection before any LLM calls are integrated.

---

### Pitfall 5: Signal Detection Tuned for Recall, Not Precision — Noise Flood

**What goes wrong:** The Celery scanner is tuned to detect many potential signals (high recall) to avoid missing opportunities. In practice, >90% of detected signals are noise — routine price moves, normal volatility, earnings season churn. The agent committee is invoked on noise, burning API budget, and the UI floods with low-quality analysis. Over time, the committee is seen as unreliable because it flags everything.

**Why it happens:** In the absence of a validated signal quality model, the instinct is to cast a wide net. Common backtesting pitfalls compound this: survivorship bias (testing only on stocks that did well), look-ahead bias (using data unavailable at signal time), and data snooping (parameter-mining historical data until something looks good).

**Consequences:** The system generates more noise than signal. Costs explode. The real-time UI becomes a wall of indistinguishable alerts. Users disengage.

**Prevention:**
- Define a minimum signal quality bar before any scanner goes live: the signal must be statistically anomalous (e.g., >2 standard deviations from 60-day baseline) on at least two independent indicators simultaneously.
- Use walk-forward validation, not static backtests: test signal rules on held-out recent data periods they were not tuned on.
- Implement a signal scoring model that combines volume anomaly, price momentum, and fundamental trigger — only scores above a threshold proceed to LLM analysis.
- Instrument signal false-positive rate from day one: tag every signal as "acted on / not acted on" and review weekly.
- Do not combine Polygon.io real-time data with FMP fundamental data in a single signal without explicit normalisation for timing differences (Polygon ticks vs. FMP quarterly snapshots have very different latency characteristics).

**Detection (warning signs):**
- Scanner triggers on any single-indicator threshold breach.
- No signal scoring layer between scanner and LLM invocation.
- Backtests show Sharpe ratio >1.5 — almost certainly overfitted.

**Build phase:** Address in Phase 2 (signal pipeline). Do not wire scanner output directly to LLM invocation until signal scoring middleware exists.

---

## Moderate Pitfalls

Mistakes that cause delays, technical debt, or degraded output quality.

---

### Pitfall 6: React Flow Performance Degradation with Real-Time Node Updates

**What goes wrong:** The React Flow graph updates in real-time as Celery workers process signals. Each agent node updates its status (idle → processing → complete). With 5 agent nodes, 1 committee node, 1 CIO node, and multiple signal history nodes, frequent state updates trigger re-renders of the entire graph. At >50 nodes or high-frequency updates, the UI becomes noticeably laggy.

**Why it happens:** React Flow nodes and edges change reference on every state update. Any component in the parent tree that accesses the `nodes` or `edges` array directly will re-render on every drag, pan, zoom, or status update. This is the most common React Flow performance anti-pattern.

**Prevention:**
- Use `useStore` with selectors to subscribe only to specific node state rather than the full nodes array.
- Memoize all custom node components with `React.memo`.
- Declare custom node component types outside the parent component (not inline) to prevent reference recreation.
- Batch agent status updates: collect updates over a 500ms window and apply them together rather than triggering one re-render per WebSocket message.
- Store agent processing status in a separate React context, not in the React Flow node data directly — only merge into node data when the batch window closes.

**Detection (warning signs):**
- Custom node components defined inline as JSX props to `ReactFlow`.
- Agent status updates trigger individual `setNodes()` calls per message.
- No `React.memo` on node components.

**Build phase:** Address in Phase 3 (UI implementation). Establish the update batching pattern before wiring WebSocket to node state.

---

### Pitfall 7: Heterogeneous Data Normalisation Failures Between Polygon.io and FMP

**What goes wrong:** Polygon.io and FMP aggregate from different upstream sources. Field naming, units, and update frequencies differ. Polygon uses standardised fundamental accounting concepts; FMP has inconsistent naming conventions across endpoints, especially for less common financial metrics. When both sources are combined in a single agent context payload, agents receive contradictory or duplicated figures.

**Why it happens:** Each API has its own schema designed independently. Polygon REST and WebSocket data have different timestamp formats. FMP quarterly snapshots arrive on different schedules than Polygon real-time ticks. Without an explicit normalisation layer, the raw payloads are concatenated and injected as context.

**Prevention:**
- Build a canonical `FinancialSnapshot` schema that all data sources must conform to before entering the agent context pipeline.
- Write explicit field mappers for each source: `polygon_mapper.py`, `fmp_mapper.py` — never pass raw API responses to prompts.
- Include `data_source` and `as_of_timestamp` on every field in the canonical schema so agents can reason about data recency.
- Write unit tests for each mapper against known fixture responses.
- Flag any field where Polygon and FMP disagree by more than 5% — surface this as a data quality warning rather than silently choosing one source.

**Detection (warning signs):**
- Raw API response dictionaries passed directly as f-string injections into prompts.
- No canonical intermediate model between API client and prompt builder.
- No tests for data mapper logic.

**Build phase:** Address in Phase 1 (data pipeline foundation). The normalisation schema must exist before any prompt context is built.

---

### Pitfall 8: Prompt Drift Across Persona Agents Over Time

**What goes wrong:** Persona system prompts are written once and evolve informally as developers tweak outputs. After several iterations, the Buffett agent has absorbed concepts from the Munger agent's original prompt, personas lose their distinctive analytical lens, and what was five differentiated viewpoints becomes five slightly varied versions of the same generic financial analyst.

**Why it happens:** No version control or testing discipline is applied to prompts. Prompts are treated as configuration strings rather than first-class code artifacts. Changes are made reactively to fix one bad output without considering downstream effects on persona consistency.

**Prevention:**
- Store all persona system prompts in version-controlled files under `agents/prompts/` — not in database records or environment variables.
- Write a persona consistency test suite: for each agent, a set of canonical test cases (known signals with known expected analytical stance) that must pass before any prompt change is merged.
- Include a structured "analytical lens" block in each persona prompt that defines 3–5 non-negotiable investment criteria that persona always applies (e.g., Buffett agent always requires evidence of durable competitive moat and consistent FCF; if absent, it must be the bear).
- Require a diff review of prompt changes as part of PR review.

**Detection (warning signs):**
- Persona prompts stored in environment variables or database fields.
- No automated test cases for persona-specific analytical stances.
- Multiple prompts contain identical paragraphs.

**Build phase:** Address in Phase 1 (agent design). Treat prompts as code from day one.

---

### Pitfall 9: WebSocket / SSE State Desync Between Celery Workers and UI

**What goes wrong:** Multiple Celery workers run in parallel. Worker A picks up a signal and starts agent analysis. Worker B simultaneously processes a different signal. The React frontend receives WebSocket messages in a non-deterministic order, rendering node states that jump between processing states, or showing completion before processing, or showing stale "processing" state after a worker has died.

**Why it happens:** Redis Pub/Sub is fire-and-forget — messages are not persisted. If the WebSocket connection drops briefly, all intermediate state updates are lost. The frontend has no way to recover the current state without a full refresh. When multiple Celery workers publish to the same Redis channel, the UI must handle concurrent, unordered events correctly.

**Prevention:**
- Use Redis Streams (not Pub/Sub) for worker-to-UI events — Streams persist messages and support consumer group replay on reconnect.
- Define a canonical event schema with `event_id`, `signal_id`, `agent_id`, `status`, and `timestamp` on every message. Never send status updates without a unique `signal_id` to correlate them.
- Implement a REST endpoint `/api/signals/{id}/state` that the frontend calls on WebSocket reconnect to recover full current state.
- Implement optimistic locking: a node's status can only transition forward (IDLE → PROCESSING → COMPLETE → ERROR), never backward. If an out-of-order message arrives, ignore it.

**Detection (warning signs):**
- Using Redis Pub/Sub without a fallback state-recovery mechanism.
- WebSocket messages contain only status strings with no signal correlation ID.
- Frontend has no reconnection + state-recovery logic.

**Build phase:** Address in Phase 3 (real-time UI). Define the event schema and recovery mechanism before building any React Flow status animation.

---

### Pitfall 10: Polygon.io and FMP Rate Limit Breaches from Uncoordinated Workers

**What goes wrong:** Multiple Celery workers independently query Polygon.io and FMP without a shared rate limit budget. Polygon's free tier allows 5 API calls/minute; even paid tiers have per-minute limits. With 4 Celery workers each making independent API calls, the effective rate is 4x what any single worker would use. Rate limit errors (HTTP 429) are retried immediately by each worker, compounding the breach.

**Why it happens:** Each Celery worker instance maintains its own HTTP client with no shared state tracking API consumption. Rate limit budgets are per-account, not per-process — but default worker architecture treats each worker as independent.

**Prevention:**
- Implement a Redis-based rate limiter as a shared token bucket: before any API call, a worker must acquire a token from the bucket. The bucket refills at the API's allowed rate. This is shared across all workers.
- Implement exponential backoff with jitter on 429 responses — never retry immediately.
- Centralise all Polygon.io and FMP calls through a single `DataFetchService` layer that enforces rate limits. Workers call this service; they never call the APIs directly.
- Monitor API quota consumption in the same dashboard as LLM costs.

**Detection (warning signs):**
- API clients instantiated directly inside Celery task functions.
- No Redis token bucket or shared rate limit state.
- 429 retry logic uses fixed `countdown` without jitter.

**Build phase:** Address in Phase 2 (data pipeline). The rate limit middleware must exist before any multi-worker deployment.

---

## Minor Pitfalls

Issues that cause friction but are straightforward to fix.

---

### Pitfall 11: Docker Compose Service Startup Order Causing Silent Failures

**What goes wrong:** Celery workers start before PostgreSQL migrations have run, or before Redis is healthy. Workers fail on startup, Docker marks them as running (exit code not immediately non-zero), and the system appears healthy while no tasks are being processed.

**Prevention:** Use `depends_on` with `healthcheck` conditions in `docker-compose.yml` for all service dependencies. Run Alembic migrations as an explicit `init` service that must complete before workers start. Add a startup probe to Celery workers that verifies broker connectivity before accepting tasks.

**Build phase:** Address in Phase 1 (infrastructure setup).

---

### Pitfall 12: No Observability Into Agent Output Quality Over Time

**What goes wrong:** Agents produce outputs, the committee aggregates them, the CIO makes decisions — but no one tracks whether agent outputs are improving or degrading. Prompt changes, model version updates, or data quality shifts silently degrade output quality with no detection mechanism.

**Prevention:** Log every agent output with `signal_id`, `agent_id`, `model_version`, `prompt_hash`, `input_token_count`, `output_token_count`, and a human-readable quality score (even just a thumbs-up/down initially). Build a simple internal review interface for sampling and rating outputs weekly.

**Build phase:** Address in Phase 2. Wire logging before any committee aggregation output is trusted.

---

### Pitfall 13: CIO Aggregation Layer Treats All Agents Equally Regardless of Track Record

**What goes wrong:** All five persona agents have equal weight in the committee vote regardless of their historical accuracy on similar signal types. An agent that is systematically wrong on tech sector signals continues to have equal influence.

**Prevention:** Build a per-agent, per-signal-category accuracy tracking table from day one. Wire the CIO aggregation layer to weight agents by their rolling accuracy score (even if initially all equal). Design the schema to support weighted voting before the data exists to calibrate it.

**Build phase:** Address in Phase 3. The data model must support weighted aggregation even if calibration comes later.

---

## Phase-Specific Warnings

| Build Phase | Likely Pitfall | Mitigation |
|---|---|---|
| Phase 1: Agent Prompt Design | Sycophantic consensus; prompt drift; hallucinated figures | Enforce information asymmetry between agents; version-control prompts; require structured data context |
| Phase 1: Data Pipeline Foundation | Normalisation failures between Polygon and FMP | Canonical `FinancialSnapshot` schema with field mappers and unit tests before any prompt building |
| Phase 1: Infrastructure | Docker service ordering failures | `depends_on` with healthchecks; migration init service |
| Phase 2: Celery Workers | Duplicate processing; cost explosion; rate limit breaches | Idempotency keys; signal quality gate; Redis token bucket for API calls |
| Phase 2: Signal Detection | Noise flood from over-eager scanning | Minimum signal quality score; walk-forward validation; no direct scanner-to-LLM wiring |
| Phase 3: Real-Time UI | React Flow re-render performance; WebSocket desync | Memoised node components; update batching; Redis Streams with event correlation IDs |
| Phase 3: Committee Aggregation | Equal weighting ignoring track record | Design weighted voting schema even before calibration data exists |

---

## Sources

- [LLM Hallucinations in Financial Institutions — BizTech Magazine](https://biztechmagazine.com/article/2025/08/llm-hallucinations-what-are-implications-financial-institutions)
- [Hallucination and Inaccurate Outputs — FINOS AIR Governance Framework](https://air-governance-framework.finos.org/risks/ri-4_hallucination-and-inaccurate-outputs.html)
- [The Multi-Agent Trap — Towards Data Science](https://towardsdatascience.com/the-multi-agent-trap/)
- [Why do Multi-Agent LLM Systems Fail? — Hakunamatata Tech](https://www.hakunamatatatech.com/our-resources/blog/why-do-multi-agent-llm-systems-fail)
- [TradingAgents: Multi-Agents LLM Financial Trading Framework — arxiv](https://arxiv.org/abs/2412.20138)
- [CONSENSAGENT: Sycophancy Mitigation in Multi-Agent LLM — ACL Anthology](https://aclanthology.org/2025.findings-acl.1141/)
- [Hierarchical AI Multi-Agent Fundamental Investing — arxiv](https://arxiv.org/pdf/2510.21147)
- [Claude API Rate Limits — Anthropic Official Docs](https://platform.claude.com/docs/en/api/rate-limits)
- [Anthropic API Pricing — Finout](https://www.finout.io/blog/anthropic-api-pricing)
- [Celery Task Resilience: Advanced Strategies — GitGuardian Blog](https://blog.gitguardian.com/celery-tasks-retries-errors/)
- [Advanced Celery for Django: Fixing Unreliable Background Tasks — Vinta Software](https://www.vintasoftware.com/blog/guide-django-celery-tasks)
- [React Flow Performance — Official Docs](https://reactflow.dev/learn/advanced-use/performance)
- [Ultimate Guide to Optimize React Flow Performance — Synergy Codes](https://www.synergycodes.com/blog/guide-to-optimize-react-flow-project-performance)
- [Common Pitfalls in Backtesting — Medium / Funny AI & Quant](https://medium.com/funny-ai-quant/ai-algorithmic-trading-common-pitfalls-in-backtesting-a-comprehensive-guide-for-algorithmic-ce97e1b1f7f7)
- [Redis WebSocket Integration for Real-Time Systems — Reintech Media](https://reintech.io/blog/redis-websockets-real-time-web-interfaces)
- [Financial Data APIs Compared: Polygon vs IEX vs Alpha Vantage](https://www.ksred.com/the-complete-guide-to-financial-data-apis-building-your-own-stock-market-data-pipeline-in-2025/)
- [When Algorithms Go Wrong: The Growing Crisis in Financial AI — Medium](https://medium.com/@cliu2263/when-algorithms-go-wrong-the-growing-crisis-in-financial-ai-f9da05adf377)
