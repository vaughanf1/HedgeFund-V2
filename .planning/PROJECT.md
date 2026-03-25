# HedgeFund V2 — AI Alpha Discovery Engine

## What This Is

A proactive, multi-agent AI hedge fund platform that continuously scans markets and autonomously discovers, evaluates, and ranks high-conviction investment opportunities — without any user input. The system runs a full pipeline: signal detection → agent analysis → committee scoring → CIO decision, all visible in a real-time visual interface. Built for personal use, running locally via Docker Compose.

## Core Value

The system discovers investment opportunities before the user has to think about them — a living alpha engine, not a reactive analyzer.

## Requirements

### Validated

(None yet — ship to validate)

### Active

**Opportunity Discovery**
- [ ] System continuously scans for signals: unusual volume/price, insider buying, institutional accumulation, earnings catalysts, sector momentum, macro dislocations
- [ ] Each detected opportunity is scored and ranked automatically
- [ ] Opportunities are passed into the agent pipeline without user input
- [ ] Scanner runs on a configurable schedule (e.g. every 15 min)

**Visual Agent Operating System**
- [ ] Opportunities flow through a visual pipeline: detected → validating → analyzing → debating → scored → approved/rejected
- [ ] Agent nodes show live status with animated state transitions
- [ ] Connections between agents are visible
- [ ] Event timeline shows what is happening in real time
- [ ] Users can watch the entire flow without touching anything

**Investor Agents**
- [ ] Warren Buffett agent (fundamental/value analysis)
- [ ] Charlie Munger agent (mental models/quality)
- [ ] Bill Ackman agent (activist/concentrated bets)
- [ ] Steve Cohen agent (short-term/flow/momentum)
- [ ] Ray Dalio agent (macro/cycle/risk parity)
- [ ] Each agent: independent score (0–100), conviction level, structured reasoning, identified risks, upside scenario, suggested time horizon
- [ ] Agents must disagree — no forced consensus

**10X / Asymmetric Opportunity Layer**
- [ ] Dedicated analysis layer identifying asymmetric bets (5x–10x potential)
- [ ] Output: catalyst justification, probability vs payoff framing, risk flags

**Committee + CIO Decision Layer**
- [ ] Aggregates all agent outputs
- [ ] Identifies consensus and conflict
- [ ] Context-weighted agent influence (e.g. Dalio weighted higher in macro regimes)
- [ ] Final output: conviction score, suggested allocation %, time horizon, risk rating, key catalysts, kill conditions

**Data Pipeline**
- [ ] Polygon.io connector: real-time price, volume, market movers
- [ ] Financial Modeling Prep connector: fundamentals, financials, insider trades, institutional holdings
- [ ] News connector (Polygon news or FMP news)
- [ ] Data normalization layer before agents consume it
- [ ] Connectors are modular and replaceable

**UI / Frontend**
- [ ] Dark mode, premium aesthetic (Bloomberg × Palantir)
- [ ] Canvas/graph-based visual agent view (React Flow)
- [ ] Animated agent cards with live state
- [ ] Opportunity feed (live stream of detections)
- [ ] Expandable analysis panels per opportunity
- [ ] Side-by-side agent comparison view
- [ ] Final output screen: top 5–10 opportunities with full breakdown

**Intermediate Visibility / Inspection**
- [ ] Raw signals stored and viewable
- [ ] Filtered opportunities inspectable
- [ ] Agent outputs with scoring breakdowns
- [ ] Full logs with timestamps

**Opportunity Feed**
- [ ] Live feed: new detections, trending ideas, highest conviction plays, recently rejected (with reason)

### Out of Scope

- Multi-user / auth system — personal use only, no login needed
- Cloud deployment — local Docker Compose only for v1
- Actual trade execution — analysis and recommendations only, no brokerage integration
- Mobile app — desktop web only
- Real-time websocket price streaming at tick level — scheduled polling is sufficient for v1
- Sentiment/social scanning (Reddit, Twitter) — modular slot reserved but not built in v1

## Context

- **Previous version** was reactive (user inputs ticker → agents analyze). This version inverts that entirely.
- **Personal use** — no auth, no multi-tenancy, no billing. Optimize for richness of output.
- **APIs available**: Polygon.io (market data, news), Financial Modeling Prep (fundamentals, insider data, institutional holdings), Anthropic Claude (agent reasoning).
- **Local Docker Compose** — all services containerized, single `docker-compose up` to run.
- **Stack decisions** (chosen, not asked): Next.js + TypeScript frontend, Python FastAPI backend, PostgreSQL for persistence, Redis for job queues and real-time state, React Flow for agent graph visualization, Celery for background scanning workers, Anthropic Claude claude-sonnet-4-6 for agent LLM calls.

## Constraints

- **Deployment**: Local only — Docker Compose. No cloud infra required.
- **Data**: Polygon.io + FMP + Anthropic only. No additional paid APIs unless explicitly added.
- **Users**: Single user, no authentication layer.
- **Execution**: No actual trade execution — recommendations only.
- **Performance**: UI must feel real-time (optimistic updates, polling, or SSE for live feel).

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python backend (FastAPI + Celery) | Agent orchestration, LLM calls, data pipelines are Python-native. Celery handles background scanning workers cleanly. | — Pending |
| Next.js + TypeScript frontend | Fastest path to premium interactive UI. React Flow for agent graph. Strong ecosystem. | — Pending |
| PostgreSQL + Redis | Postgres for structured opportunity/agent output storage. Redis for job queues and real-time pub/sub to frontend. | — Pending |
| Anthropic Claude as agent LLM | User has API key. claude-sonnet-4-6 is current best for structured reasoning at reasonable cost. | — Pending |
| React Flow for agent graph | Purpose-built for node/edge visualizations. Handles animated state transitions cleanly. | — Pending |
| Proactive scan loop (no user input) | Core product shift — system discovers, not user. Scanners run on schedule via Celery Beat. | — Pending |
| Docker Compose for local setup | Single command to run everything. No cloud complexity for personal use. | — Pending |

---
*Last updated: 2026-03-25 after initialization*
