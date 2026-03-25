# Roadmap: HedgeFund V2 — AI Alpha Discovery Engine

## Overview

A proactive multi-agent investment discovery platform built in four dependency-ordered phases: data foundation → signal pipeline → agent analysis engine → real-time visual UI. Each phase is a hard prerequisite for the next — the data schema determines agent prompt structure, the signal quality gate is the primary cost control for LLM calls, event publishing in the agent layer is the prerequisite for the visual graph, and the React Flow UI has no meaning without live SSE events flowing from the pipeline. The result is a living alpha engine that discovers and evaluates opportunities continuously, without user input, displayed in a Bloomberg-style visual agent operating system.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Infrastructure and Data Foundation** - Docker Compose stack running, all data connectors ingesting, canonical data schema established, agent prompt architecture designed with divergence constraints baked in
- [ ] **Phase 2: Signal Detection and Opportunity Pipeline** - Background scanner running on schedule, signal detectors live, quality gate filtering before any LLM call, raw signals and opportunities persisted and inspectable
- [ ] **Phase 3: Agent Analysis Engine** - All five investor persona agents running in parallel, 10X asymmetric layer active, committee aggregation and CIO final decision producing structured verdicts, Redis events emitted at every pipeline stage
- [ ] **Phase 4: Real-Time Frontend and Visual Agent Operating System** - React Flow agent graph rendering live pipeline state, opportunity feed streaming, full output dashboard showing top opportunities with per-agent breakdowns

## Phase Details

### Phase 1: Infrastructure and Data Foundation

**Goal**: The entire platform stack runs with a single command, market data flows reliably into a normalized schema, and agent prompt architecture enforces divergence from the start

**Depends on**: Nothing (first phase)

**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, INFR-01, INFR-02

**Success Criteria** (what must be TRUE):
  1. `docker-compose up` starts all services (FastAPI, Celery, TimescaleDB, Redis) with passing healthchecks and no manual steps
  2. Polygon.io and FMP connectors fetch real market data and write it to TimescaleDB; swapping one connector does not require changes downstream of the normalization layer
  3. All ingested data — price, fundamentals, insider trades, news — is readable from a single canonical `FinancialSnapshot` schema
  4. The agent prompt library has versioned persona files with explicit data partitioning rules (Buffett gets fundamentals only; Cohen gets price action only) that prevent sycophantic consensus by design
  5. LLM call wrapper is wired with cost logging and a hard daily spend limit before any agent makes a real call

**Plans:** 3 plans

Plans:
- [x] 01-01-PLAN.md — Docker Compose stack, FastAPI skeleton, TimescaleDB schema via Alembic, Celery app with beat schedule
- [x] 01-02-PLAN.md — Massive.com and FMP data connectors with abstract interface, FinancialSnapshot schema, Celery ingest tasks
- [x] 01-03-PLAN.md — Five investor persona files with data partitioning, DataPartitioner, LLM wrapper with Redis cost gate

---

### Phase 2: Signal Detection and Opportunity Pipeline

**Goal**: The system continuously scans the market on schedule, detects statistically anomalous signals, scores and filters them through a quality gate, and queues only high-quality opportunities for agent analysis — without any LLM calls for low-quality signals

**Depends on**: Phase 1

**Requirements**: SGNL-01, SGNL-02, SGNL-03, SGNL-04, SGNL-05, SGNL-06, SGNL-07, SGNL-08, VIS-01, VIS-04

**Success Criteria** (what must be TRUE):
  1. Celery Beat triggers market scanner workers on a configurable schedule (default 15 minutes) without manual intervention
  2. Signal detectors fire on volume spikes, price breakouts, insider buying clusters, news catalysts, and sector momentum shifts — and each detection is written to the database with a timestamp
  3. The composite signal quality gate rejects low-scoring signals before any LLM call; only opportunities above the threshold reach the agent queue
  4. Raw detected signals are queryable via the FastAPI read endpoint; each signal shows its score, detection type, and timestamp
  5. Per-symbol deduplication in Redis prevents the same opportunity from entering the queue multiple times within a configurable window

**Plans**: TBD

Plans:
- [ ] 02-01: Celery Beat scheduler, market scanner workers, signal detector rules (volume anomaly, price breakout, sector momentum)
- [ ] 02-02: Insider buying cluster detector, news catalyst detector, composite signal scorer, quality gate
- [ ] 02-03: Redis opportunity queue with idempotency keys and deduplication; FastAPI read endpoints for signals (VIS-01, VIS-04)

---

### Phase 3: Agent Analysis Engine

**Goal**: Qualifying opportunities trigger five investor persona agents running in parallel, each producing an independent structured verdict; a 10X asymmetric layer flags high-upside bets; a committee aggregates all verdicts with context-weighted influence; and a CIO meta-agent issues a final decision — with Redis events emitted at every stage

**Depends on**: Phase 2

**Requirements**: AGNT-01, AGNT-02, AGNT-03, AGNT-04, AGNT-05, AGNT-06, AGNT-07, AGNT-08, ASYM-01, ASYM-02, ASYM-03, CIO-01, CIO-02, CIO-03, CIO-04, CIO-05

**Success Criteria** (what must be TRUE):
  1. A qualifying opportunity triggers all five agents (Buffett, Munger, Ackman, Cohen, Dalio) running in parallel; each produces an independent score (0-100), conviction level, structured reasoning, identified risks, upside scenario, and time horizon
  2. Agents demonstrably disagree — the inter-agent variance score is non-trivial on contested opportunities; no committee round is accepted if all five agents converge to within a narrow band
  3. The 10X asymmetric layer runs and flags opportunities with 5x-10x potential, including catalyst justification, probability-vs-payoff framing, and required upside conditions
  4. The committee aggregates all five verdicts with context-weighted influence (e.g. Dalio weighted higher in macro regimes), identifies consensus and dissent, and the CIO produces a final output with conviction score, suggested allocation %, time horizon, risk rating, key catalysts, and kill conditions
  5. Every pipeline state transition emits a Redis event (`AGENT_STARTED`, `AGENT_COMPLETE`, `COMMITTEE_COMPLETE`, `DECISION_MADE`) that is consumable by downstream SSE subscribers

**Plans**: TBD

Plans:
- [ ] 03-01: Single-agent round-trip proof (one persona end-to-end with LangGraph + Celery task); validate fan-out/fan-in pattern before full build
- [ ] 03-02: All five persona agents with parallel Celery group fan-out; AgentVerdict persistence; inter-agent variance scoring (AGNT-01 through AGNT-08)
- [ ] 03-03: 10X asymmetric scoring layer (ASYM-01 through ASYM-03); Committee Aggregator with context-weighted voting; CIO Decision Engine (CIO-01 through CIO-05)
- [ ] 03-04: Redis event publishing at every pipeline stage; verify all five event types are consumable before Phase 4 begins

---

### Phase 4: Real-Time Frontend and Visual Agent Operating System

**Goal**: A Bloomberg-style dark dashboard renders the full agent pipeline as a live React Flow graph, streams new opportunity detections in a feed, and displays a ranked output screen with full per-agent and CIO breakdowns — all driven by SSE events from the backend

**Depends on**: Phase 3

**Requirements**: UI-01, UI-02, UI-03, UI-04, FEED-01, FEED-02, FEED-03, OUT-01, OUT-02, OUT-03, OUT-04, VIS-02, VIS-03, INFR-03

**Success Criteria** (what must be TRUE):
  1. The React Flow agent graph shows the full pipeline (scanner -> signal detector -> quality gate -> five agents -> committee -> CIO) and every node updates its visual state in real time as SSE events arrive, without requiring a page refresh
  2. Opportunities animate visually through pipeline states (detected -> validating -> analyzing -> debating -> scored -> approved/rejected) with clear state transitions on agent nodes and connection edges
  3. The live opportunity feed shows new detections, trending ideas, highest conviction plays, and recently rejected ideas with rejection reasons -- all updating in real time
  4. The final output dashboard ranks the top 5-10 opportunities and each entry shows conviction score, risk rating, expected upside, time horizon, key catalysts, per-agent score breakdown, and CIO summary
  5. Pipeline stages (filtered opportunities, agent outputs with scoring breakdowns) are inspectable via detail views without leaving the dashboard; SSE reconnects automatically if the connection drops

**Plans**: TBD

Plans:
- [ ] 04-01: FastAPI SSE endpoint subscribing to Redis channels; static React Flow graph layout with all pipeline nodes; Bloomberg dark aesthetic scaffolding (INFR-02, INFR-03, UI-01)
- [ ] 04-02: Dynamic node state driven by SSE events; animated state transitions; connection direction indicators (UI-02, UI-03, UI-04)
- [ ] 04-03: Live opportunity feed (FEED-01, FEED-02, FEED-03); pipeline stage inspection views for filtered opportunities and agent outputs (VIS-02, VIS-03)
- [ ] 04-04: Final output dashboard — ranked opportunity list with full breakdown per opportunity including per-agent scores and CIO recommendation (OUT-01 through OUT-04)

---

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure and Data Foundation | 3/3 | ✓ Complete | 2026-03-25 |
| 2. Signal Detection and Opportunity Pipeline | 0/3 | Not started | - |
| 3. Agent Analysis Engine | 0/4 | Not started | - |
| 4. Real-Time Frontend and Visual Agent Operating System | 0/4 | Not started | - |

---
*Roadmap created: 2026-03-25*
*Last updated: 2026-03-25 after Phase 1 execution complete*
