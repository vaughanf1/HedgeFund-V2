# Phase 03: Agent Analysis Engine - Research

**Researched:** 2026-03-25
**Domain:** LangGraph agent orchestration, Celery fan-out/fan-in, Anthropic structured outputs, Redis event publishing, committee aggregation
**Confidence:** HIGH for Anthropic SDK patterns and Redis patterns; HIGH for Celery individual-task fan-out; MEDIUM for LangGraph-in-Celery asyncio integration (documented pitfalls but workarounds exist); MEDIUM for committee/CIO weighting algorithm design (empirical)

---

## Summary

Phase 3 builds the core LLM analysis pipeline on top of the existing Celery/Redis/FastAPI stack from Phases 1–2. The primary architectural question is how to run five persona agents in parallel and fan-in their results — without using Celery Chord (which has known reliability issues on Redis). The answer is: use individual Celery tasks per agent, write results to Redis hashes, use atomic HINCRBY as a counter, and trigger the aggregation task manually when the counter reaches 5. LangGraph provides a graph execution container for each individual persona invocation, called via `asyncio.run(graph.ainvoke(...))` inside the Celery task.

The second critical question is structured output parsing. The Anthropic SDK now provides a native `client.messages.parse()` method (public beta as of November 2025) that accepts a Pydantic model and returns a validated `parsed_output` object — no regex or JSON.loads required. Use this instead of hand-rolling JSON extraction from the text response. The existing `llm_call_with_persona` wrapper in `app/llm/wrapper.py` must be extended to support `messages.parse()`.

For Redis events (AGENT_STARTED, AGENT_COMPLETE, COMMITTEE_COMPLETE, DECISION_MADE), use Redis Pub/Sub via `r.publish(channel, json_payload)` from Celery workers, with a FastAPI SSE endpoint that subscribes via `redis.asyncio` and yields events. The PITFALLS.md recommends Redis Streams for durability, but given the prior decisions that SSE is the transport, Redis Pub/Sub is sufficient for Phase 3 — the SSE reconnect recovery endpoint required for production resilience is Phase 4 scope.

**Primary recommendation:** No new Python packages are strictly required. Add `langgraph` and `langchain-anthropic` (flagged in STACK.md but not yet in requirements.txt). The Anthropic SDK already in requirements supports `messages.parse()` from version 0.40+. All fan-out/fan-in coordination uses the existing redis-py client via atomic counter pattern.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| langgraph | 1.1.3 | Graph execution container per persona agent; stateful node execution | Recommended in STACK.md; maps directly to persona-as-node mental model |
| langchain-anthropic | latest | LangGraph's adapter to call `claude-haiku-4-5` via LangGraph nodes | Required companion to langgraph when using Anthropic models inside graphs |
| anthropic | 0.40.0 | Direct SDK already in requirements; `messages.parse()` for structured output | Already installed; `.parse()` is available from 0.40+ |
| celery[redis] | 5.6.2 | Individual tasks per agent; Redis counter fan-in; already in stack | Already in stack; no Chord needed |
| redis | already in stack | Atomic HINCRBY counter for fan-in; HSET/HGET for agent result storage; Pub/Sub for SSE events | Already in stack |
| pydantic | v2 (already in stack) | `AgentVerdict` and `CIODecision` schemas; output validation via `messages.parse()` | Already in stack |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sse-starlette | latest | `EventSourceResponse` for FastAPI SSE endpoint | Needed for Phase 4 but the SSE endpoint for agent events is first wired here |
| nest_asyncio | latest | Patch asyncio to allow `asyncio.run()` inside Celery worker if event loop already running | Apply as fallback only; prefer `asyncio.get_event_loop().run_until_complete()` pattern |

### New Packages Required (not yet in requirements.txt)

```
langgraph==1.1.3
langchain-anthropic
sse-starlette
```

`nest_asyncio` is optional — only needed if the Celery worker event loop is already active when LangGraph is invoked. Add to requirements only if the `asyncio.run()` pattern fails in testing (Plan 03-01 spike will determine this).

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| LangGraph per-agent graph | Raw asyncio.gather on llm_call_with_persona | asyncio.gather is simpler but loses LangGraph's stateful checkpointing, retry hooks, and the graph structure that the roadmap calls for in the spike |
| Individual Celery tasks + Redis counter | Celery Chord | Chord has documented silent failure on exception propagation (PITFALLS.md Pitfall 4); Redis counter is explicit and observable |
| `client.messages.parse()` for structured output | Manual JSON extraction with regex | Parse provides validated Pydantic object with automatic retries; regex fails on malformed JSON from edge-case LLM outputs |
| Redis Pub/Sub for pipeline events | Redis Streams | Streams are more durable (persist on reconnect) but add consumer group management; Pub/Sub is sufficient for Phase 3 if SSE reconnect recovery is deferred to Phase 4 |

### Installation

```bash
pip install langgraph==1.1.3 langchain-anthropic sse-starlette
```

---

## Architecture Patterns

### Recommended Project Structure Addition

```
backend/app/
├── agents/
│   ├── personas/          # Already exists: buffett.md, munger.md, ackman.md, cohen.md, dalio.md
│   ├── partitioner.py     # Already exists
│   ├── loader.py          # Already exists
│   ├── graph.py           # NEW: builds and compiles the per-persona LangGraph graph
│   └── schemas.py         # NEW: AgentVerdict, CommitteeReport, CIODecision Pydantic models
├── analysis/
│   ├── __init__.py
│   ├── variance.py        # NEW: inter-agent variance scoring (std dev on confidence scores)
│   ├── asymmetric.py      # NEW: 10X asymmetric bet detection layer
│   ├── committee.py       # NEW: committee aggregation with context-weighted influence
│   └── cio.py             # NEW: CIO meta-agent, final decision output
├── tasks/
│   ├── celery_app.py      # Already exists; no changes needed
│   ├── scan_market.py     # Already exists; Phase 2 complete
│   └── analyse_opportunity.py  # NEW: BLPOP consumer + fan-out coordinator task
├── events/
│   ├── __init__.py
│   └── publisher.py       # NEW: Redis Pub/Sub publish helpers (AGENT_STARTED, AGENT_COMPLETE, etc.)
├── routers/
│   └── events.py          # NEW: GET /api/v1/events/stream — FastAPI SSE endpoint
db/
├── models.py              # Add AgentVerdict and CIODecision ORM models
alembic/versions/
└── 0003_agent_verdicts.py  # NEW: agent_verdicts and cio_decisions hypertables
```

---

### Pattern 1: Per-Persona LangGraph Graph (Minimal Single-Agent Round-Trip)

**What:** A compiled LangGraph StateGraph with a single node that calls the Anthropic API via the existing `llm_call_with_persona` wrapper (extended to use `messages.parse()`). The graph is compiled once at module level and invoked per opportunity.

**When to use:** Every time a persona agent needs to analyse an opportunity. The graph provides the retry boundary, structured state, and future extension point for multi-step reasoning.

**Example:**

```python
# Source: LangGraph StateGraph pattern — docs.langchain.com/oss/python/langgraph/quickstart
# backend/app/agents/graph.py

from __future__ import annotations
from typing import TypedDict, Any
from langgraph.graph import StateGraph, START, END
from app.agents.schemas import AgentVerdict
from app.llm.wrapper import llm_call_with_persona_parsed  # extended version

class AgentState(TypedDict):
    persona_name: str
    data_context: dict[str, Any]
    verdict: AgentVerdict | None

async def run_persona_node(state: AgentState) -> dict[str, Any]:
    verdict = await llm_call_with_persona_parsed(
        persona_name=state["persona_name"],
        data_context=state["data_context"],
    )
    return {"verdict": verdict}

def build_persona_graph() -> Any:
    builder = StateGraph(AgentState)
    builder.add_node("run_persona", run_persona_node)
    builder.add_edge(START, "run_persona")
    builder.add_edge("run_persona", END)
    return builder.compile()

# Compile once at module level — not inside the Celery task
PERSONA_GRAPH = build_persona_graph()
```

---

### Pattern 2: Celery Task Invoking LangGraph (asyncio bridge)

**What:** A Celery task (synchronous by default) calls `asyncio.run()` to bridge into LangGraph's async `ainvoke()`. This is the confirmed pattern from community examples.

**The asyncio pitfall:** If the Celery worker already has a running event loop (some configurations), `asyncio.run()` raises `RuntimeError: This event loop is already running`. The safe pattern is to use `asyncio.get_event_loop().run_until_complete()` with a fallback to `asyncio.run()`.

**Example:**

```python
# Source: community pattern confirmed via celery/celery Discussion #9058
# backend/app/tasks/analyse_opportunity.py

import asyncio
from app.agents.graph import PERSONA_GRAPH

@app.task(name="app.tasks.analyse_opportunity.run_persona_agent", bind=True, max_retries=3)
def run_persona_agent(self, opportunity_id: str, persona_name: str, data_context: dict) -> dict:
    """Run a single persona agent for one opportunity."""
    async def _invoke():
        result = await PERSONA_GRAPH.ainvoke({
            "persona_name": persona_name,
            "data_context": data_context,
            "verdict": None,
        })
        return result["verdict"].model_dump()

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # nest_asyncio fallback — apply at worker startup if needed
            import nest_asyncio
            nest_asyncio.apply()
        return asyncio.run(_invoke())
    except RuntimeError:
        return asyncio.get_event_loop().run_until_complete(_invoke())
```

---

### Pattern 3: Redis Counter Fan-In (No Chord)

**What:** Each of the five persona agent tasks, on completion, atomically increments a Redis hash counter keyed by `opportunity_id`. When the counter reaches 5, the final task to complete dispatches the committee aggregation task. No Celery Chord is used.

**Why:** Celery Chord on Redis has documented silent failure when any child task raises an unserializable exception — the chord callback never fires. The Redis counter is explicit, atomic, and observable.

**Example:**

```python
# backend/app/tasks/analyse_opportunity.py

AGENTS = ["buffett", "munger", "ackman", "cohen", "dalio"]
AGENT_COUNT = len(AGENTS)  # 5

@app.task(name="app.tasks.analyse_opportunity.run_persona_agent", bind=True, max_retries=3)
def run_persona_agent(self, opportunity_id: str, persona_name: str, data_context: dict) -> None:
    r = redis.from_url(_REDIS_URL)

    # Publish AGENT_STARTED event
    publish_event(r, "AGENT_STARTED", {"opportunity_id": opportunity_id, "persona": persona_name})

    verdict_dict = _run_graph_sync(persona_name, data_context)  # asyncio.run bridge

    # Persist verdict to Redis hash
    r.hset(f"verdicts:{opportunity_id}", persona_name, json.dumps(verdict_dict))

    # Atomic counter: HINCRBY is atomic — safe across concurrent workers
    completed = r.hincrby(f"verdicts_counter:{opportunity_id}", "count", 1)

    # Publish AGENT_COMPLETE event
    publish_event(r, "AGENT_COMPLETE", {"opportunity_id": opportunity_id, "persona": persona_name})

    # Last agent to complete triggers committee
    if int(completed) >= AGENT_COUNT:
        run_committee.delay(opportunity_id)

@app.task(name="app.tasks.analyse_opportunity.fan_out", bind=True)
def fan_out(self, opportunity: dict) -> None:
    """Fan-out: dispatch one Celery task per persona agent."""
    opportunity_id = opportunity["ticker"] + ":" + opportunity["detected_at"]
    data_context = build_data_context(opportunity)  # fetch from DB
    for persona in AGENTS:
        run_persona_agent.delay(opportunity_id, persona, data_context)
```

---

### Pattern 4: Anthropic Structured Output via `messages.parse()`

**What:** Extend the existing `llm_call_with_persona` wrapper to call `client.messages.parse()` with the `AgentVerdict` Pydantic model, returning a validated object instead of raw text.

**When to use:** All LLM calls that need structured agent verdict output (AGNT-06). The existing `llm_call` function for unstructured calls remains unchanged.

**Example:**

```python
# Source: platform.claude.com/docs/en/build-with-claude/structured-outputs
# backend/app/llm/wrapper.py — new function alongside existing llm_call

from app.agents.schemas import AgentVerdict

async def llm_call_with_persona_parsed(
    persona_name: str,
    data_context: dict[str, Any],
    redis_client: Any,
    model: str = DEFAULT_MODEL,
    daily_limit_usd: float = DEFAULT_DAILY_LIMIT_USD,
) -> AgentVerdict:
    """Call LLM with persona prompt, return validated AgentVerdict via messages.parse()."""
    tracker = SpendTracker(redis_client, daily_limit_usd=daily_limit_usd)
    within_budget, _ = await tracker.async_check_budget(_PREFLIGHT_ESTIMATE_USD)
    if not within_budget:
        raise BudgetExceededError(...)

    partitioner = DataPartitioner()
    loader = PersonaLoader()
    partitioned = partitioner.partition_raw(persona_name, data_context)
    system_prompt = loader.render_persona(persona_name, partitioned)

    client = anthropic.AsyncAnthropic()
    response = await client.messages.parse(
        model=model,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": "Analyse the data in your system prompt and return your verdict."}],
        output_format=AgentVerdict,
    )
    # Record spend from usage
    cost_usd = calculate_call_cost(model, response.usage.input_tokens, response.usage.output_tokens)
    await tracker.async_record_spend(cost_usd)

    return response.parsed_output  # Validated AgentVerdict instance
```

---

### Pattern 5: AgentVerdict and CIODecision Pydantic Schemas

**What:** Canonical Pydantic models for the output of each persona agent and the final CIO decision. These serve as both the `messages.parse()` output contract and the SQLAlchemy-serialisable persistence format.

**Note:** The persona Markdown templates already define the JSON output format (score, verdict, rationale, risks, upside_scenario, time_horizon). The Pydantic schema must match exactly.

```python
# backend/app/agents/schemas.py

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal

class AgentVerdict(BaseModel):
    persona: str
    verdict: Literal["BUY", "HOLD", "PASS"]
    confidence: int = Field(ge=0, le=100)
    rationale: str
    key_metrics_used: list[str]
    risks: list[str]
    upside_scenario: str
    time_horizon: str
    data_gaps: list[str]

class CommitteeReport(BaseModel):
    opportunity_id: str
    verdicts: list[AgentVerdict]
    consensus: str          # "BUY" | "HOLD" | "PASS" | "SPLIT"
    dissent_agents: list[str]
    variance_score: float   # std dev of confidence scores
    weighted_conviction: float  # context-weighted average confidence
    asymmetric_flag: bool
    asymmetric_justification: str | None

class CIODecision(BaseModel):
    opportunity_id: str
    conviction_score: int = Field(ge=0, le=100)
    suggested_allocation_pct: float = Field(ge=0.0, le=100.0)
    time_horizon: str
    risk_rating: Literal["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]
    key_catalysts: list[str]
    kill_conditions: list[str]
    final_verdict: Literal["INVEST", "MONITOR", "PASS"]
```

---

### Pattern 6: Inter-Agent Variance Scoring

**What:** Compute standard deviation of agent confidence scores to validate genuine disagreement. If variance falls below the threshold, the committee round is invalid (AGNT-07 / success criterion 2).

**Algorithm:**

```python
# backend/app/analysis/variance.py
from __future__ import annotations
import statistics
from app.agents.schemas import AgentVerdict

MINIMUM_VARIANCE_THRESHOLD = 8.0  # std dev on 0-100 confidence scale; tune via env var

def compute_variance_score(verdicts: list[AgentVerdict]) -> float:
    """Return standard deviation of agent confidence scores."""
    scores = [v.confidence for v in verdicts]
    if len(scores) < 2:
        return 0.0
    return statistics.stdev(scores)

def is_committee_valid(verdicts: list[AgentVerdict]) -> bool:
    """Return False if all agents converged to a narrow band (sycophantic consensus)."""
    return compute_variance_score(verdicts) >= MINIMUM_VARIANCE_THRESHOLD
```

---

### Pattern 7: Context-Weighted Committee Aggregation

**What:** The committee weights each agent's conviction based on the detected market regime. Dalio is weighted higher in macro regimes; Buffett/Munger higher when fundamental signals dominate; Cohen higher on price-action signals.

**Implementation note:** The weighting table should start as a static dict keyed by (regime, persona) → weight, with all weights defaulting to 1.0 when regime is unknown. The regime is extracted from the opportunity's signal composition (which signal types fired highest).

```python
# backend/app/analysis/committee.py

REGIME_WEIGHTS: dict[str, dict[str, float]] = {
    "macro":       {"buffett": 0.7, "munger": 0.8, "ackman": 0.9, "cohen": 1.0, "dalio": 1.5},
    "fundamental": {"buffett": 1.5, "munger": 1.4, "ackman": 1.2, "cohen": 0.8, "dalio": 0.9},
    "momentum":    {"buffett": 0.7, "munger": 0.8, "ackman": 1.0, "cohen": 1.5, "dalio": 1.2},
    "default":     {"buffett": 1.0, "munger": 1.0, "ackman": 1.0, "cohen": 1.0, "dalio": 1.0},
}

def detect_regime(opportunity: dict) -> str:
    """Infer market regime from the opportunity's highest-scoring signal types."""
    signals = opportunity.get("signals", [])
    signal_types = {s["signal_type"] for s in signals if s.get("score", 0) > 0.5}
    if "sector_momentum" in signal_types or "price_breakout" in signal_types:
        return "momentum"
    if "volume_spike" in signal_types and "insider_cluster" in signal_types:
        return "fundamental"
    return "default"
```

---

### Pattern 8: Redis Event Publishing (AGENT_STARTED, AGENT_COMPLETE, COMMITTEE_COMPLETE, DECISION_MADE)

**What:** Celery workers publish JSON payloads to a Redis Pub/Sub channel. The FastAPI SSE endpoint subscribes and forwards events to the browser.

```python
# backend/app/events/publisher.py
from __future__ import annotations
import json
import redis as redis_sync

EVENTS_CHANNEL = "pipeline:events"

def publish_event(r: redis_sync.Redis, event_type: str, payload: dict) -> None:
    """Publish a pipeline event to the Redis Pub/Sub channel."""
    message = json.dumps({"event": event_type, "data": payload}, default=str)
    r.publish(EVENTS_CHANNEL, message)
```

```python
# backend/app/routers/events.py — FastAPI SSE endpoint
from __future__ import annotations
import asyncio
import json
import redis.asyncio as aioredis
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

router = APIRouter(prefix="/api/v1/events")

@router.get("/stream")
async def stream_pipeline_events():
    async def event_generator():
        r = aioredis.from_url("redis://redis:6379/0")
        pubsub = r.pubsub()
        await pubsub.subscribe("pipeline:events")
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield {"event": "pipeline", "data": message["data"]}
        finally:
            await pubsub.unsubscribe("pipeline:events")
            await r.aclose()
    return EventSourceResponse(event_generator())
```

---

### Pattern 9: BLPOP Consumer Task (Opportunity Queue)

**What:** A dedicated Celery task that BLPOP-blocks on `opportunity_queue` (Phase 2 output) and dispatches the fan-out. This is the entry point connecting Phase 2 to Phase 3.

**Critical note from prior decisions:** BLPOP is per-ticker dedup (Phase 2 decision 02-03). The consumer task must not add its own dedup — Phase 2 handles it.

```python
# backend/app/tasks/analyse_opportunity.py

@app.task(name="app.tasks.analyse_opportunity.consume_queue", bind=True)
def consume_queue(self) -> None:
    """Long-running task: BLPOP from opportunity_queue, fan-out to persona agents."""
    r = redis.from_url(_REDIS_URL)
    while True:
        result = r.blpop("opportunity_queue", timeout=30)
        if result is None:
            continue  # timeout — check worker health and loop
        _, raw = result
        opportunity = json.loads(raw)
        fan_out.delay(opportunity)
```

---

### Anti-Patterns to Avoid

- **Celery Chord for agent fan-out:** Use Redis counter + individual tasks. Chord's callback silently fails on Redis when any child task raises an unserializable exception (PITFALLS.md Pitfall 4, confirmed in celery/celery Issue #5229 and #6220).
- **`asyncio.run()` inside LangGraph nodes:** Creates a nested event loop per node. Only call `asyncio.run()` at the Celery task boundary, not inside graph nodes.
- **Passing large data payloads as Celery task arguments:** Pass `opportunity_id` and fetch data from DB/Redis inside the task. Large task messages overflow the broker and slow serialization.
- **Agent sycophantic convergence:** All five agents have different data partitions (enforced by existing `DataPartitioner`). Do not give any two agents identical input context. Validate variance_score > threshold before accepting a committee round.
- **LangGraph Server dependency:** Phase 3 uses LangGraph as a Python library, NOT LangGraph Cloud / LangGraph Server. No separate deployment, no separate infrastructure.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured JSON output from LLM | Custom JSON regex/parsing | `client.messages.parse(output_format=AgentVerdict)` | Parse retries automatically on validation failure; no regex brittle to whitespace; validated Pydantic object |
| Async-to-sync bridge in Celery | Thread pool executor hacks | `asyncio.run()` with nest_asyncio fallback | Standard pattern; nest_asyncio is the known-good solution for the event loop conflict |
| Inter-agent fan-in coordination | Celery Chord | Redis HINCRBY counter + individual tasks | Chord silent failures on Redis; counter is atomic, visible, debuggable |
| Agent graph execution | Raw async function calls | LangGraph StateGraph (one per agent) | Provides retry boundary, state checkpointing, future extension to multi-step without refactor |
| Variance gate logic | Custom clustering algorithm | Standard deviation on confidence scores (Python `statistics.stdev`) | Simple, interpretable, no extra dependency |

**Key insight:** The hardest problems in this phase (structured output, fan-in coordination, event loop bridging) all have well-established library-level solutions. Build none of them from scratch.

---

## Common Pitfalls

### Pitfall 1: Celery Chord Silent Failure

**What goes wrong:** Chord callback never fires because one child task raised an exception. No error is surfaced. The committee task never runs. The opportunity is silently lost.

**Why it happens:** Celery on Redis propagates exceptions through chord in a way that breaks the counter mechanism in edge cases (celery/celery Issues #5229, #6220, #3812).

**How to avoid:** Use individual Celery tasks + Redis HINCRBY counter. The last task to increment to 5 dispatches the committee task explicitly.

**Warning signs:** Using `chord(group(...), callback)` in any part of the fan-out.

---

### Pitfall 2: `asyncio.run()` RuntimeError Inside Celery

**What goes wrong:** `RuntimeError: This event loop is already running` when calling `asyncio.run(graph.ainvoke(...))` inside a Celery task, because some Celery configurations (gevent pool, eventlet pool, or certain ASGI transports) already have a running event loop.

**Why it happens:** `asyncio.run()` is designed to be called from synchronous context with no running loop. Celery gevent/eventlet pools break this assumption.

**How to avoid:** Use `asyncio.get_event_loop().run_until_complete()` as primary; add `nest_asyncio.apply()` as fallback if gevent/eventlet pool is configured. The Plan 03-01 spike must test this explicitly before full build.

**Warning signs:** Celery configured with `--pool=gevent` or `--pool=eventlet`; `asyncio.run()` used without checking `loop.is_running()`.

---

### Pitfall 3: Sycophantic Consensus (Variance Gate Skipped)

**What goes wrong:** All five agents converge to BUY within a narrow confidence band. The committee accepts this and outputs maximum conviction. The system produces no genuine disagreement.

**Why it happens:** Agents share underlying LLM weights and are easily pulled toward consensus. Without the variance gate enforced at committee time, the system silently degrades.

**How to avoid:** Enforce `is_committee_valid(verdicts)` before aggregating. If False, re-run agents with `temperature` increased (or flag the round as `LOW_VARIANCE` and surface to user). The data partitioner (already built) is the structural prevention; the variance gate is the runtime detection.

**Warning signs:** `variance_score < MINIMUM_VARIANCE_THRESHOLD`; all five agents returning identical `verdict` and `time_horizon` values.

---

### Pitfall 4: Persona Template Output Format Mismatch with Pydantic Schema

**What goes wrong:** `messages.parse()` fails because the persona Markdown template's JSON output format does not exactly match the `AgentVerdict` Pydantic schema field names. Anthropic's constrained decoding enforces the schema, but field name mismatches cause validation errors.

**Why it happens:** The persona templates were written with a JSON output format block (visible in `buffett.md`, `dalio.md`). If the Pydantic field names differ (e.g., template says `"time_horizon"` but schema says `"investment_horizon"`), parsing fails.

**How to avoid:** Derive the `AgentVerdict` Pydantic model directly from the output format defined in the persona Markdown files. Both are currently in the codebase — synchronize them before writing any tests.

**Warning signs:** `ValidationError` on `response.parsed_output` during Plan 03-01 single-agent spike.

---

### Pitfall 5: `opportunity_id` Key Collision in Redis

**What goes wrong:** Two different opportunities for the same ticker (e.g., AAPL analysed at 09:00 and again at 10:00 after dedup TTL expires) share the same `verdicts:{ticker}` Redis key. The second run overwrites the first's agent results mid-analysis.

**Why it happens:** Using just `ticker` as the Redis hash key for agent results, instead of `ticker + detected_at` as the compound key.

**How to avoid:** Use `opportunity_id = f"{ticker}:{detected_at_iso}"` as the key. Set a TTL of 24h on all `verdicts:*` and `verdicts_counter:*` keys to prevent Redis memory growth.

---

### Pitfall 6: CIO Agent Not Getting Committee Context

**What goes wrong:** The CIO meta-agent receives the raw five verdicts as a list but lacks the committee's weighted conviction score and consensus/dissent analysis. The CIO then repeats committee work in its prompt, bloating token cost.

**Why it happens:** Committee aggregation result is not serialised and passed as structured context to the CIO prompt.

**How to avoid:** The CIO agent receives the `CommitteeReport` (including `variance_score`, `weighted_conviction`, `consensus`, `dissent_agents`) as its input context, not the raw five verdicts. Build a `CommitteeReport` object first, then pass it to the CIO.

---

## Code Examples

### AgentVerdict Pydantic Schema (from existing persona template output format)

```python
# Source: backend/app/agents/personas/buffett.md output format section
# backend/app/agents/schemas.py

from pydantic import BaseModel, Field
from typing import Literal

class AgentVerdict(BaseModel):
    persona: str
    verdict: Literal["BUY", "HOLD", "PASS"]
    confidence: int = Field(ge=0, le=100)
    rationale: str
    key_metrics_used: list[str]
    risks: list[str]
    upside_scenario: str
    time_horizon: str
    data_gaps: list[str]
```

### Redis Counter Fan-In (Atomic, No Chord)

```python
# Source: redis.io/docs/latest/commands/hincrby — HINCRBY is atomic
# Pattern: last task to complete (counter hits 5) dispatches aggregation

r = redis.from_url(_REDIS_URL)
completed = int(r.hincrby(f"verdicts_counter:{opportunity_id}", "count", 1))
r.expire(f"verdicts_counter:{opportunity_id}", 86400)  # 24h TTL

if completed >= AGENT_COUNT:
    run_committee.delay(opportunity_id)
```

### FastAPI SSE Endpoint (Redis Pub/Sub subscriber)

```python
# Source: gist.github.com/lbatteau/1bc7ae630d5b7844d58f038085590f97
# Adapted for redis.asyncio v4+ API (aioredis merged into redis-py)

@router.get("/stream")
async def stream_pipeline_events():
    async def event_generator():
        r = aioredis.from_url("redis://redis:6379/0")
        pubsub = r.pubsub()
        await pubsub.subscribe("pipeline:events")
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield {"event": "pipeline", "data": message["data"]}
        finally:
            await pubsub.unsubscribe("pipeline:events")
            await r.aclose()
    return EventSourceResponse(event_generator())
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual JSON extraction from LLM text with regex | `client.messages.parse(output_format=PydanticModel)` — native constrained decoding | Anthropic structured outputs public beta: November 2025 | Eliminates retry logic for malformed JSON; schema-guaranteed output; direct Pydantic object |
| LangChain `ChatAnthropic` wrapping Anthropic SDK | Direct Anthropic SDK with `langchain-anthropic` as thin adapter inside LangGraph | 2024–2025 | Cleaner cost tracking; direct SDK access for `messages.parse()` |
| Celery Chord for parallel task fan-in | Individual tasks + Redis HINCRBY counter | Documented pitfall known since Celery 4.x; now standard avoidance pattern | Eliminates silent chord callback failures on Redis backend |

**Deprecated/outdated:**
- `aioredis` as separate package: Merged into `redis-py` as `redis.asyncio` — use `redis.asyncio` directly, not the old `aioredis` package.
- `client.messages.create()` for structured output: Still works but `.parse()` with Pydantic is the new standard when structured output is required.

---

## Open Questions

1. **LangGraph value in Phase 3 (spike question)**
   - What we know: LangGraph provides stateful graph execution, retry hooks, and future multi-step agent capability. The STACK.md decision locked it in.
   - What's unclear: Whether a single-node graph adds meaningful value over `asyncio.run(llm_call_with_persona_parsed(...))` directly. The spike in Plan 03-01 must measure this.
   - Recommendation: Plan 03-01 spike must explicitly answer "does LangGraph add complexity without benefit for a single-node graph?" If yes, document the finding and use LangGraph anyway (per STACK.md decision) but simplify node structure.

2. **`messages.parse()` availability on `anthropic==0.40.0`**
   - What we know: The Anthropic structured outputs feature entered public beta in November 2025. The codebase currently has `anthropic==0.40.0` pinned in requirements.txt.
   - What's unclear: Whether `messages.parse()` is available in 0.40.0 or requires upgrading to 0.86.0 (the version in STACK.md).
   - Recommendation: Upgrade `anthropic` to `0.86.0` in requirements.txt as the first action of Plan 03-01. The 0.40.0 pin predates the structured outputs beta.

3. **MINIMUM_VARIANCE_THRESHOLD calibration**
   - What we know: Standard deviation < 8 points on a 0-100 scale signals sycophantic convergence. This is a starting value, not a validated threshold.
   - What's unclear: The right threshold will vary by opportunity type. 8.0 may be too tight or too loose.
   - Recommendation: Make `MINIMUM_VARIANCE_THRESHOLD` an environment variable (`AGENT_VARIANCE_THRESHOLD`, default 8.0). Log variance score on every committee round for empirical calibration in later phases.

4. **CIO agent: LLM call or deterministic function?**
   - What we know: Requirements say the CIO "produces a final output" with conviction score, allocation %, etc. Whether this is an LLM call or deterministic computation from the committee report is not specified.
   - What's unclear: Using another LLM call for the CIO adds cost and latency. A deterministic function on the `CommitteeReport` fields is cheaper and more predictable.
   - Recommendation: Implement the CIO as a deterministic function in Phase 3 (deriving conviction from weighted committee conviction, allocation from a simple tier table). Reserve CIO-as-LLM for a future phase if the deterministic version proves insufficient.

---

## Sources

### Primary (HIGH confidence)
- `platform.claude.com/docs/en/build-with-claude/structured-outputs` — Anthropic `messages.parse()` API pattern verified
- `docs.celeryq.dev/en/stable/userguide/canvas.html` — Celery Chord/Group mechanics; synchronization cost warning
- `redis.io/docs/latest/commands/hincrby/` — HINCRBY atomic semantics confirmed
- `gist.github.com/lbatteau/1bc7ae630d5b7844d58f038085590f97` — FastAPI SSE + Redis Pub/Sub pattern
- `python.useinstructor.com/` — Instructor library; Anthropic structured output ecosystem

### Secondary (MEDIUM confidence)
- LangGraph quickstart docs (`docs.langchain.com/oss/python/langgraph/quickstart`) — StateGraph + compile + invoke pattern; parallel branches confirmed
- `celery/celery Discussion #9058` — `asyncio.run()` inside Celery task pattern; `loop.run_until_complete()` recommendation
- `aipractitioner.substack.com/p/scaling-langgraph-agents-parallelization` — LangGraph parallel superstep pattern; asyncio.gather integration confirmed

### Tertiary (LOW confidence — flag for validation)
- Community examples of LangGraph + Celery integration (Medium articles, blocked 403): Integration is possible per multiple sources but exact `asyncio.run` vs `get_event_loop` pattern needs Plan 03-01 spike validation
- `MINIMUM_VARIANCE_THRESHOLD = 8.0`: Derived from the 0-100 scale and the requirement for "non-trivial" disagreement; empirical, needs calibration

### Internal sources (HIGH confidence — codebase verified)
- `backend/app/agents/partitioner.py` — DataPartitioner with PERSONA_DATA_ACCESS matrix confirmed
- `backend/app/agents/loader.py` — PersonaLoader with `render_persona()` confirmed
- `backend/app/agents/personas/*.md` — All five persona templates confirmed; output JSON format matches proposed AgentVerdict schema
- `backend/app/llm/wrapper.py` — Existing `llm_call_with_persona` pattern; extension point identified
- `backend/app/signals/queue.py` — `OPP_QUEUE_KEY = "opportunity_queue"` confirmed as BLPOP source
- `.planning/research/PITFALLS.md` — Pitfall 4 (Chord reliability) and Pitfall 9 (SSE/WebSocket state desync) confirmed

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Anthropic SDK upgrade and LangGraph patterns verified via official docs and community; Celery/Redis patterns from official Celery docs and confirmed issues
- Architecture: HIGH for fan-out/fan-in, structured output, Redis event publishing; MEDIUM for LangGraph-in-Celery asyncio bridge (spike required)
- Pitfalls: HIGH — all sourced from either official issue trackers, PITFALLS.md (already researched), or confirmed SDK behavior

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (30 days — LangGraph and Anthropic SDK are active; re-check `messages.parse()` GA status if delayed)
