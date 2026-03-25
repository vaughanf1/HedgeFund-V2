# Requirements: HedgeFund V2

**Defined:** 2026-03-25
**Core Value:** The system discovers investment opportunities before the user has to think about them — a living alpha engine, not a reactive analyzer.

## v1 Requirements

### Data Pipeline

- [ ] **DATA-01**: System ingests real-time and recent market data (price, volume, market movers) from Polygon.io/Massive.com API
- [ ] **DATA-02**: System ingests fundamental data (P/E, revenue, earnings, balance sheet) from Financial Modeling Prep
- [ ] **DATA-03**: System ingests insider trades and institutional holdings (13F filings) from Financial Modeling Prep
- [ ] **DATA-04**: System ingests news headlines and article summaries tied to tickers from Polygon news API
- [ ] **DATA-05**: All ingested data is normalized into a unified schema before agents consume it
- [ ] **DATA-06**: Data connectors are modular and replaceable without changing downstream logic

### Signal Detection

- [ ] **SGNL-01**: System detects unusual volume spikes relative to recent history
- [ ] **SGNL-02**: System detects significant price movements (breakouts, gap-ups/downs)
- [ ] **SGNL-03**: System detects insider buying clusters (multiple insiders buying within short windows)
- [ ] **SGNL-04**: System detects news catalysts (earnings surprises, partnerships, regulatory changes)
- [ ] **SGNL-05**: System detects sector momentum shifts (rotating capital flows, relative strength changes)
- [ ] **SGNL-06**: Each detected signal is scored and ranked automatically
- [ ] **SGNL-07**: Signal quality gate filters low-quality signals before passing to LLM agents (cost control)
- [ ] **SGNL-08**: Scanning runs on a configurable schedule (e.g. every 15 minutes)

### Investor Agents

- [ ] **AGNT-01**: Warren Buffett agent evaluates opportunities through fundamental/value lens
- [ ] **AGNT-02**: Charlie Munger agent evaluates through mental models and quality filters
- [ ] **AGNT-03**: Bill Ackman agent evaluates through activist/concentrated bet lens
- [ ] **AGNT-04**: Steve Cohen agent evaluates through short-term flow and momentum lens
- [ ] **AGNT-05**: Ray Dalio agent evaluates through macro/cycle/risk parity lens
- [ ] **AGNT-06**: Each agent assigns independent score (0-100), conviction level, structured reasoning, risks, upside scenario, and time horizon
- [ ] **AGNT-07**: Agents receive different data subsets to prevent sycophantic consensus (information asymmetry)
- [ ] **AGNT-08**: All five agents run in parallel for each opportunity

### 10X / Asymmetric Layer

- [ ] **ASYM-01**: Dedicated analysis layer identifies asymmetric bets with 5x-10x potential
- [ ] **ASYM-02**: Output includes catalyst justification and probability vs payoff framing
- [ ] **ASYM-03**: Risks and required conditions for upside scenario are explicitly flagged

### Committee + CIO Decision

- [ ] **CIO-01**: Committee aggregates all agent outputs per opportunity
- [ ] **CIO-02**: Committee identifies consensus and conflict across agents
- [ ] **CIO-03**: Agent influence is context-weighted (e.g. Dalio weighted higher in macro regimes)
- [ ] **CIO-04**: CIO produces final output: conviction score, suggested allocation %, time horizon, risk rating, key catalysts, kill conditions
- [ ] **CIO-05**: Top opportunities are ranked and surfaced to the user

### Visual Agent Operating System

- [ ] **UI-01**: Canvas/graph-based view (React Flow) showing the full agent pipeline
- [ ] **UI-02**: Opportunities flow visually through states: detected → validating → analyzing → debating → scored → approved/rejected
- [ ] **UI-03**: Agent nodes show live status with animated state transitions
- [ ] **UI-04**: Connections between agents are visible with data flow direction

### Opportunity Feed

- [ ] **FEED-01**: Live feed showing new opportunity detections in real time
- [ ] **FEED-02**: Feed shows trending ideas and highest conviction plays
- [ ] **FEED-03**: Feed shows recently rejected ideas with rejection reasons

### Final Output Screen

- [ ] **OUT-01**: Dashboard showing top 5-10 ranked opportunities with full breakdown
- [ ] **OUT-02**: Each opportunity shows: conviction score, risk rating, expected upside, time horizon, key catalysts
- [ ] **OUT-03**: Each opportunity shows per-agent score breakdown and reasoning
- [ ] **OUT-04**: CIO summary with final recommendation per opportunity

### Intermediate Visibility

- [ ] **VIS-01**: Raw detected signals are stored and viewable
- [ ] **VIS-02**: Filtered opportunities are inspectable at each pipeline stage
- [ ] **VIS-03**: Agent outputs with full scoring breakdowns are viewable
- [ ] **VIS-04**: Full logs with timestamps for every pipeline event

### Infrastructure

- [ ] **INFR-01**: All services run via Docker Compose with a single `docker-compose up` command
- [ ] **INFR-02**: Dark mode, premium aesthetic (Bloomberg x Palantir inspired)
- [ ] **INFR-03**: UI feels real-time via SSE updates from backend to frontend

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
| DATA-01 | Phase 1 | Pending |
| DATA-02 | Phase 1 | Pending |
| DATA-03 | Phase 1 | Pending |
| DATA-04 | Phase 1 | Pending |
| DATA-05 | Phase 1 | Pending |
| DATA-06 | Phase 1 | Pending |
| INFR-01 | Phase 1 | Pending |
| INFR-02 | Phase 1 | Pending |
| SGNL-01 | Phase 2 | Pending |
| SGNL-02 | Phase 2 | Pending |
| SGNL-03 | Phase 2 | Pending |
| SGNL-04 | Phase 2 | Pending |
| SGNL-05 | Phase 2 | Pending |
| SGNL-06 | Phase 2 | Pending |
| SGNL-07 | Phase 2 | Pending |
| SGNL-08 | Phase 2 | Pending |
| VIS-01 | Phase 2 | Pending |
| VIS-04 | Phase 2 | Pending |
| AGNT-01 | Phase 3 | Pending |
| AGNT-02 | Phase 3 | Pending |
| AGNT-03 | Phase 3 | Pending |
| AGNT-04 | Phase 3 | Pending |
| AGNT-05 | Phase 3 | Pending |
| AGNT-06 | Phase 3 | Pending |
| AGNT-07 | Phase 3 | Pending |
| AGNT-08 | Phase 3 | Pending |
| ASYM-01 | Phase 3 | Pending |
| ASYM-02 | Phase 3 | Pending |
| ASYM-03 | Phase 3 | Pending |
| CIO-01 | Phase 3 | Pending |
| CIO-02 | Phase 3 | Pending |
| CIO-03 | Phase 3 | Pending |
| CIO-04 | Phase 3 | Pending |
| CIO-05 | Phase 3 | Pending |
| UI-01 | Phase 4 | Pending |
| UI-02 | Phase 4 | Pending |
| UI-03 | Phase 4 | Pending |
| UI-04 | Phase 4 | Pending |
| FEED-01 | Phase 4 | Pending |
| FEED-02 | Phase 4 | Pending |
| FEED-03 | Phase 4 | Pending |
| OUT-01 | Phase 4 | Pending |
| OUT-02 | Phase 4 | Pending |
| OUT-03 | Phase 4 | Pending |
| OUT-04 | Phase 4 | Pending |
| VIS-02 | Phase 4 | Pending |
| VIS-03 | Phase 4 | Pending |
| INFR-03 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 47 total
- Mapped to phases: 47
- Unmapped: 0

---
*Requirements defined: 2026-03-25*
*Last updated: 2026-03-25 — traceability updated after roadmap creation*
