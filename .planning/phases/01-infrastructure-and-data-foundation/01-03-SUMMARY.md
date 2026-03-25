---
phase: 01
plan: 03
subsystem: agent-prompt-infrastructure
tags: [personas, data-partitioning, llm-wrapper, cost-control, redis, anthropic]

dependency-graph:
  requires: ["01-01"]
  provides: ["persona-files", "data-partitioner", "persona-loader", "llm-cost-gate"]
  affects: ["03-01", "03-02", "03-03"]

tech-stack:
  added: ["anthropic==0.40.0"]
  patterns: ["information-asymmetry-by-design", "pre-call-budget-gate", "per-task-atomic-commit"]

key-files:
  created:
    - backend/app/agents/personas/buffett.md
    - backend/app/agents/personas/munger.md
    - backend/app/agents/personas/ackman.md
    - backend/app/agents/personas/cohen.md
    - backend/app/agents/personas/dalio.md
    - backend/app/agents/loader.py
    - backend/app/agents/partitioner.py
    - backend/app/llm/exceptions.py
    - backend/app/llm/spend_tracker.py
    - backend/app/llm/wrapper.py
  modified: []

decisions:
  - id: D-01-03-1
    description: "TYPE_CHECKING guard for FinancialSnapshot import"
    rationale: "Plan 01-02 runs in parallel; partitioner.py uses TYPE_CHECKING so mypy sees the full type but import does not fail at runtime before 01-02 merges"
  - id: D-01-03-2
    description: "from __future__ import annotations in all modules"
    rationale: "Production container runs Python 3.12 but local system Python is 3.9; PEP 563 annotations makes X | Y union syntax work on 3.9 for local verification"
  - id: D-01-03-3
    description: "Sync + async interface on SpendTracker"
    rationale: "Celery tasks are sync; FastAPI routes are async; both need spend tracking without requiring an extra wrapper layer"
  - id: D-01-03-4
    description: "_PREFLIGHT_ESTIMATE_USD pre-flight check rather than exact token count"
    rationale: "Exact cost is unknown before the call; a conservative estimate ($0.003) prevents budget overrun while not over-blocking near-limit calls"

metrics:
  duration: "4m 34s"
  completed: "2026-03-25"
---

# Phase 1 Plan 03: Agent Prompt Infrastructure Summary

**One-liner:** Five investor persona prompts with enforced data partition rules, a DataPartitioner enforcing information asymmetry via PERSONA_DATA_ACCESS matrix, and a Redis-backed LLM cost gate raising BudgetExceededError before any Anthropic API call.

---

## What Was Built

### Five Investor Persona Files

Each persona file is a versioned Markdown template containing:
- A header with persona name, version (1.0.0), and explicit data partition declaration
- A role section with investor philosophy and voice
- A STRICT CONSTRAINTS section explicitly listing inaccessible data types
- A `{{data_context_json}}` placeholder for runtime injection
- A 5-step analysis framework specific to each investor's lens
- A structured JSON output format

**Data partition assignments:**
| Persona | Data Access |
|---------|------------|
| buffett | FUNDAMENTALS ONLY |
| munger | FUNDAMENTALS + NEWS |
| ackman | FUNDAMENTALS + INSIDER TRADES |
| cohen | PRICE ACTION (OHLCV) ONLY |
| dalio | PRICE ACTION + NEWS |

No two personas share identical access. Buffett and Cohen have entirely disjoint data views — they literally cannot see any of the same signals.

### DataPartitioner (backend/app/agents/partitioner.py)

`PERSONA_DATA_ACCESS` is the single source of truth for the information asymmetry design. `DataPartitioner.partition_for_persona()` accepts a list of `FinancialSnapshot` objects (Pydantic models or dicts) and strips all disallowed top-level keys before returning a context dict. `partition_raw()` handles pre-assembled flat dicts. A `TYPE_CHECKING` guard prevents the `FinancialSnapshot` import from hard-failing before plan 01-02 merges.

### PersonaLoader (backend/app/agents/loader.py)

`PersonaLoader.render_persona(name, data_context)` is the single call-site for injecting partitioned data into a persona prompt. It serialises the context dict as indented JSON and replaces the `{{data_context_json}}` placeholder in the Markdown template.

### LLM Exceptions (backend/app/llm/exceptions.py)

- `BudgetExceededError` carries `current_spend_usd`, `limit_usd`, and `projected_cost_usd` as structured attributes so callers can format useful error messages.
- `LLMCallError` wraps any API-level failure with `model` and `original_error` attributes.

### SpendTracker (backend/app/llm/spend_tracker.py)

- Redis key: `llm:spend:YYYY-MM-DD` (UTC date), TTL 25 hours.
- `COST_PER_MTOK` pricing table: haiku-4-5 ($0.80/$4.00 per M tokens), sonnet-4-6 ($3.00/$15.00 per M tokens).
- Both sync and async interfaces (`record_spend` / `async_record_spend`, etc.) to support Celery tasks and FastAPI routes without adapter layers.
- `incrbyfloat` is atomic in Redis — no race condition on concurrent agent calls.

### LLM Wrapper (backend/app/llm/wrapper.py)

- `llm_call()`: pre-flight budget check → `AsyncAnthropic().messages.create()` → exact cost calculation from response usage → `async_record_spend()`.
- `llm_call_with_persona()`: convenience function that chains `DataPartitioner.partition_raw()` → `PersonaLoader.render_persona()` → `llm_call()`.
- `BudgetExceededError` is raised before any API request if the pre-flight estimate would breach the limit.
- All API errors are caught and re-raised as `LLMCallError`.

---

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| D-01-03-1 | TYPE_CHECKING guard for FinancialSnapshot | Parallel execution with 01-02; avoids hard import failure at merge time |
| D-01-03-2 | `from __future__ import annotations` | Local Python 3.9 vs container Python 3.12; PEP 563 makes union syntax portable |
| D-01-03-3 | Sync + async SpendTracker interface | Celery tasks (sync) and FastAPI routes (async) both need spend tracking |
| D-01-03-4 | Conservative pre-flight estimate ($0.003) | Exact cost unknown pre-call; estimate prevents overrun without over-blocking |

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Python 3.9 type hint syntax incompatibility**

- **Found during:** Task 1 verification (PersonaLoader import failed on local Python 3.9)
- **Issue:** `Path | None` union syntax requires Python 3.10+; local system is 3.9
- **Fix:** Added `from __future__ import annotations` to `loader.py`, `exceptions.py`; used `Optional[Path]` in loader; `from __future__ import annotations` makes all annotations strings at runtime, resolving the issue on 3.9 while preserving correct typing on 3.12
- **Files modified:** `backend/app/agents/loader.py`, `backend/app/llm/exceptions.py`
- **Commits:** b8e4736, 38bd7de

---

## Next Phase Readiness

Plan 01-03 is the final plan in Phase 1. The agent prompt infrastructure is now complete. Phase 3 (Agent Orchestration) can:
- Call `PersonaLoader.render_persona()` to get system prompts
- Call `DataPartitioner.partition_for_persona()` to enforce data asymmetry
- Call `llm_call_with_persona()` to execute gated LLM calls
- Catch `BudgetExceededError` to handle daily limit exhaustion

**Dependency note:** `partitioner.py` imports `FinancialSnapshot` under `TYPE_CHECKING`. Once plan 01-02 merges, the full type will be available. No code changes required in this plan's files.

**Concern carried forward:** The `COST_PER_MTOK` pricing table in `spend_tracker.py` is hardcoded. When Anthropic updates pricing, this must be updated manually. Consider adding a test that alerts when the pricing table is stale (Phase 3 task).
