# Requirements: HedgeFund V2

**Defined:** 2026-03-25
**Core Value:** The system discovers investment opportunities before the user has to think about them — a living alpha engine, not a reactive analyzer.

## v1 Requirements

### Data Pipeline

- [x] **DATA-01**: System ingests real-time and recent market data (price, volume, market movers) from Polygon.io/Massive.com API
- [x] **DATA-02**: System ingests fundamental data (P/E, revenue, earnings, balance sheet) from Financial Modeling Prep
- [x] **DATA-03**: System ingests insider trades and institutional holdings (13F filings) from Financial Modeling Prep
- [x] **DATA-04**: System ingests news headlines and article summaries tied to tickers from Polygon news API
- [x] **DATA-05**: All ingested data is normalized into a unified schema before agents consume it
- [x] **DATA-06**: Data connectors are modular and replaceable without changing downstream logic

### Signal Detection

- [x] **SGNL-01**: System detects unusual volume spikes relative to recent history
- [x] **SGNL-02**: System detects significant price movements (breakouts, gap-ups/downs)
- [x] **SGNL-03**: System detects insider buying clusters (multiple insiders buying within short windows)
- [x] **SGNL-04**: System detects news catalysts (earnings surprises, partnerships, regulatory changes)
- [x] **SGNL-05**: System detects sector momentum shifts (rotating capital flows, relative strength changes)
- [x] **SGNL-06**: Each detected signal is scored and ranked automatically
- [x] **SGNL-07**: Signal quality gate filters low-quality signals before passing to LLM agents (cost control)
- [x] **SGNL-08**: Scanning runs on a configurable schedule (e.g. every 15 minutes)

### Investor Agents

- [x] **AGNT-01**: Warren Buffett agent evaluates opportunities through fundamental/value lens
- [x] **AGNT-02**: Charlie Munger agent evaluates through mental models and quality filters
- [x] **AGNT-03**: Bill Ackman agent evaluates through activist/concentrated bet lens
- [x] **AGNT-04**: Steve Cohen agent evaluates through short-term flow and momentum lens
- [x] **AGNT-05**: Ray Dalio agent evaluates through macro/cycle/risk parity lens
- [x] **AGNT-06**: Each agent assigns independent score (0-100), conviction level, structured reasoning, risks, upside scenario, and time horizon
- [x] **AGNT-07**: Agents receive different data subsets to prevent sycophantic consensus (information asymmetry)
- [x] **AGNT-08**: All five agents run in parallel for each opportunity

### 10X / Asymmetric Layer

- [x] **ASYM-01**: Dedicated analysis layer identifies asymmetric bets with 5x-10x potential
- [x] **ASYM-02**: Output includes catalyst justification and probability vs payoff framing
- [x] **ASYM-03**: Risks and required conditions for upside scenario are explicitly flagged

### Committee + CIO Decision

- [x] **CIO-01**: Committee aggregates all agent outputs per opportunity
- [x] **CIO-02**: Committee identifies consensus and conflict across agents
- [x] **CIO-03**: Agent influence is context-weighted (e.g. Dalio weighted higher in macro regimes)
- [x] **CIO-04**: CIO produces final output: conviction score, suggested allocation %, time horizon, risk rating, key catalysts, kill conditions
- [x] **CIO-05**: Top opportunities are ranked and surfaced to the user

### Visual Agent Operating System

- [x] **UI-01**: Canvas/graph-based view (React Flow) showing the full agent pipeline
- [x] **UI-02**: Opportunities flow visually through states: detected → validating → analyzing → debating → scored → approved/rejected
- [x] **UI-03**: Agent nodes show live status with animated state transitions
- [x] **UI-04**: Connections between agents are visible with data flow direction

### Opportunity Feed

- [x] **FEED-01**: Live feed showing new opportunity detections in real time
- [x] **FEED-02**: Feed shows trending ideas and highest conviction plays
- [x] **FEED-03**: Feed shows recently rejected ideas with rejection reasons

### Final Output Screen

- [x] **OUT-01**: Dashboard showing top 5-10 ranked opportunities with full breakdown
- [x] **OUT-02**: Each opportunity shows: conviction score, risk rating, expected upside, time horizon, key catalysts
- [x] **OUT-03**: Each opportunity shows per-agent score breakdown and reasoning
- [x] **OUT-04**: CIO summary with final recommendation per opportunity

### Intermediate Visibility

- [x] **VIS-01**: Raw detected signals are stored and viewable
- [x] **VIS-02**: Filtered opportunities are inspectable at each pipeline stage
- [x] **VIS-03**: Agent outputs with full scoring breakdowns are viewable
- [x] **VIS-04**: Full logs with timestamps for every pipeline event

### Infrastructure

- [x] **INFR-01**: All services run via Docker Compose with a single `docker-compose up` command
- [x] **INFR-02**: Dark mode, premium aesthetic (Bloomberg x Palantir inspired)
- [x] **INFR-03**: UI feels real-time via SSE updates from backend to frontend

## v2 Requirements

### History & Replay

- **HIST-01**: User can view past opportunities and replay how the system analyzed them
- **HIST-02**: User can inspect full decision paths for historical opportunities

### UI Enhancements

- **UI-05**: Side-by-side agent comparison view
- **UI-06**: Expandable deep-dive analysis panels per opportunity

### Additional Signals

- **SOCL-01**: Social/sentiment scanning (Reddit, Twitter)
- **MACRO-01**: Macro dislocation detection and regime classification

## Out of Scope

| Feature | Reason |
|---------|--------|
| Trade execution / brokerage integration | Recommendations only — no live trading |
| Multi-user auth / accounts | Personal use only |
| Cloud deployment | Local Docker Compose only for v1 |
| Mobile app | Desktop web only |
| Real-time tick-level websocket streaming | Scheduled polling sufficient for v1 |
| Backtesting engine | Discovery platform, not a backtester |
| Telegram alerts | All opportunities surfaced in-app instead |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 1 | Complete |
| DATA-02 | Phase 1 | Complete |
| DATA-03 | Phase 1 | Complete |
| DATA-04 | Phase 1 | Complete |
| DATA-05 | Phase 1 | Complete |
| DATA-06 | Phase 1 | Complete |
| INFR-01 | Phase 1 | Complete |
| INFR-02 | Phase 4 | Complete |
| SGNL-01 | Phase 2 | Complete |
| SGNL-02 | Phase 2 | Complete |
| SGNL-03 | Phase 2 | Complete |
| SGNL-04 | Phase 2 | Complete |
| SGNL-05 | Phase 2 | Complete |
| SGNL-06 | Phase 2 | Complete |
| SGNL-07 | Phase 2 | Complete |
| SGNL-08 | Phase 2 | Complete |
| VIS-01 | Phase 2 | Complete |
| VIS-04 | Phase 2 | Complete |
| AGNT-01 | Phase 3 | Complete |
| AGNT-02 | Phase 3 | Complete |
| AGNT-03 | Phase 3 | Complete |
| AGNT-04 | Phase 3 | Complete |
| AGNT-05 | Phase 3 | Complete |
| AGNT-06 | Phase 3 | Complete |
| AGNT-07 | Phase 3 | Complete |
| AGNT-08 | Phase 3 | Complete |
| ASYM-01 | Phase 3 | Complete |
| ASYM-02 | Phase 3 | Complete |
| ASYM-03 | Phase 3 | Complete |
| CIO-01 | Phase 3 | Complete |
| CIO-02 | Phase 3 | Complete |
| CIO-03 | Phase 3 | Complete |
| CIO-04 | Phase 3 | Complete |
| CIO-05 | Phase 3 | Complete |
| UI-01 | Phase 4 | Complete |
| UI-02 | Phase 4 | Complete |
| UI-03 | Phase 4 | Complete |
| UI-04 | Phase 4 | Complete |
| FEED-01 | Phase 4 | Complete |
| FEED-02 | Phase 4 | Complete |
| FEED-03 | Phase 4 | Complete |
| OUT-01 | Phase 4 | Complete |
| OUT-02 | Phase 4 | Complete |
| OUT-03 | Phase 4 | Complete |
| OUT-04 | Phase 4 | Complete |
| VIS-02 | Phase 4 | Complete |
| VIS-03 | Phase 4 | Complete |
| INFR-03 | Phase 4 | Complete |

**Coverage:**
- v1 requirements: 47 total
- Mapped to phases: 47
- Unmapped: 0

---
*Requirements defined: 2026-03-25*
*Last updated: 2026-03-25 — Phase 4 requirements marked Complete (all v1 requirements complete)*
