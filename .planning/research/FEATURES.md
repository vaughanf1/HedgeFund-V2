# Feature Landscape: AI Hedge Fund / Multi-Agent Investment Discovery Platform

**Domain:** Autonomous multi-agent AI investment discovery and alpha generation
**Researched:** 2026-03-25
**Confidence:** MEDIUM-HIGH (cross-referenced across TradingAgents paper, AutoHedge, FinGPT, Perplexity Finance, Kavout, BattleFin alpha platform survey, and multiple 2025/2026 industry sources)

---

## Table Stakes

Features users and the system require to function at all. Missing any of these = the platform is either useless or untrustworthy.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Real-time market data ingestion | Without live prices, analysis is stale and signals are noise | Low | Polygon.io covers this; FMP for fundamentals |
| Multi-signal analysis (technical + fundamental + sentiment) | Every credible AI trading system uses at least 3 signal types; single-signal systems have poor edge | Medium | RSI, MACD, momentum windows; P/E, revenue, EPS; news sentiment |
| Persistent opportunity log / history | Users need to audit what the system found, why, and what happened — trust requires trail | Low | Database-backed; not just in-memory |
| Backtested or at minimum explainable decisions | Without "why" reasoning, the system is a black box; users won't trust or learn from it | Medium | LLM-generated rationale per opportunity is the minimum |
| Risk exposure per opportunity | No professional system surfaces opportunities without sizing/risk context | Medium | Position sizing, expected drawdown, conviction score |
| Agent specialization (not one general agent) | Every serious multi-agent framework (TradingAgents, AutoHedge, FinRobot) uses distinct roles: analyst, risk, execution | Medium | Minimum: analyst + risk + decision roles |
| Proactive scanning loop (no user trigger required) | This is the project's core premise — system must run continuously without user input | Medium | Background scheduler; periodic or event-driven sweep |
| Opportunity feed / results surface | Users need somewhere to see what the system discovered | Low | List/feed UI at minimum |
| Alert system | If a 10x opportunity fires, the system must notify — email, Telegram, or push | Low | Telegram bot is low effort and sufficient |
| Data source error handling | APIs fail; bad data corrupts signals; uncaught errors halt the system | Medium | Retry logic, data validation, graceful degradation |
| Audit log / decision trail | Reproducibility: what data was used, at what time, which agents ran, what was decided | Low-Medium | Append-only log per opportunity |

---

## Differentiators

Features that set this system apart from generic screeners, FinGPT clones, and AutoGPT wrappers. Not expected, but highly valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Named investor persona agents (Buffett, Munger, Ackman, Cohen, Dalio) | Applies documented investment philosophy as a lens — not generic "AI analyst"; gives the system a knowable character and teachable framework | High | Each persona needs a system prompt encoding their philosophy, heuristics, and language; needs tuning and testing per persona |
| Bull/bear structured debate before committee vote | TradingAgents research shows structured debate improves decision quality vs single-pass analysis; surfaces genuine disagreement | High | Configurable rounds; facilitator agent reads transcript and records prevailing view; disagreement delta is itself a signal |
| CIO final decision layer (meta-agent) | Adds institutional governance; the CIO synthesizes committee divergence and applies portfolio-level logic | High | Most open-source frameworks stop at committee; CIO-as-meta-agent is rare |
| Asymmetric/10x filter as a first-class feature | Most platforms screen for conventional buy signals; explicit asymmetry hunting (upside/downside ratio, catalyst proximity, small float, institutional neglect) is not standard | High | Requires custom scoring model; catalyst detection + float + analyst coverage gaps as inputs |
| Visual agent operating system (graph view) | Watching agents work in real-time is the "wow" feature; makes the invisible visible; differentiates from any terminal-style tool | Very High | React Flow or D3-based; live node state, agent handoffs, confidence bars; this is the signature UI |
| Opportunity replay / history scrubbing | Ability to re-run what the system would have found on a past date builds trust and enables learning; not found in any open-source equivalent | High | Replay mode feeds historical data through the current agent pipeline |
| Agent disagreement score as a signal | When Buffett-persona and Ackman-persona sharply diverge, that divergence itself is metadata — the user learns which opportunities are contested | Medium | Store conviction scores per agent; surface delta as a "controversy score" |
| Regime detection / macro context injection | Agents that know whether the current market is risk-on, risk-off, or transitional make better calls; basic systems ignore this | High | Separate macro agent or pre-flight context injection into all agents |
| Insider transaction signal layer | Cluster insider buying before catalysts is one of the highest-quality legal alpha signals; not in most LLM-based systems | Medium | FMP insider endpoint; requires event-based trigger, not just periodic |
| Volume anomaly pre-screening | Filter the universe to stocks showing unusual volume (relative to 20-day avg) before running expensive LLM analysis | Low-Medium | Cheap to build; dramatically reduces API costs and improves signal density |
| Bloomberg Terminal x Palantir aesthetic | Dark, dense, data-forward UI signals seriousness and competence; most AI trading UIs are consumer-grade; the aesthetic IS part of the product | Medium | Monospace font + dark background + neon accents + grid layout; Tailwind + shadcn can get close |
| Conviction tier system (Strong / Watch / Speculative) | Helps user quickly prioritize; not just "opportunity found" but a calibrated confidence bucket | Low | Derived from committee vote unanimity + signal count + persona agreement |

---

## Agent Disagreement Mechanics

This section deserves dedicated treatment because it is both a differentiator and a design challenge.

### What good disagreement handling looks like

Based on TradingAgents research (ICML 2025) and the TradingAgents architecture:

- Each analyst agent produces a structured report (not free-form text) with a directional call: BUY / HOLD / SELL + conviction score 0-100
- Bull and bear researcher agents each receive all analyst reports and argue their case for a configurable number of rounds (`max_debate_rounds`)
- A facilitator/mediator agent reviews the full debate transcript and records the prevailing perspective
- The CIO (in this system's case) receives the committee summary, individual scores, and disagreement delta, then makes a final call
- Disagreement delta = max(conviction) - min(conviction) across personas; high delta = contested opportunity

### What to store per decision

```
opportunity_id
timestamp
ticker
persona_votes: { buffett: {call, conviction}, munger: {...}, ... }
analyst_reports: { fundamental: {...}, sentiment: {...}, technical: {...} }
debate_rounds: [ { round, bull_argument, bear_argument }, ... ]
committee_outcome: { prevailing_view, vote_tally, dissents }
cio_decision: { final_call, rationale, conviction_tier }
disagreement_delta: float
```

### Why disagreement is itself a signal

- High disagreement on a BUY: warrants caution; flag as speculative
- High disagreement with no consensus: opportunity may be too complex or data-insufficient; defer or request more data
- High disagreement with strong CIO override: log the CIO's rationale explicitly (these are learning events)
- Unanimous strong BUY: highest-conviction feed entry; escalate alert

---

## Signal Detection Patterns

Coverage of all signal types the system should understand, prioritized by impact.

### Tier 1: High signal-to-noise, include in MVP

| Signal Type | Description | Data Source | Notes |
|-------------|-------------|-------------|-------|
| Price momentum (multi-window) | 1M, 3M, 6M, 12M returns; 52-week high proximity | Polygon.io | The most validated quant factor; always include |
| Volume anomaly | Today's volume vs 20-day average; flag >2x | Polygon.io | Cheap pre-filter; reduces universe dramatically |
| Earnings surprise | Beat/miss magnitude vs analyst consensus | FMP earnings endpoint | Strong catalyst signal; combine with price reaction |
| Insider cluster buying | Multiple insiders buying within 30 days | FMP insider transactions | Legal alpha; strongest when combined with technical |
| News sentiment spike | Rapid positive/negative sentiment shift in financial news | FMP news + LLM scoring | Use LLM for nuance, not just keyword matching |

### Tier 2: Include post-MVP or as agent tools

| Signal Type | Description | Data Source | Notes |
|-------------|-------------|-------------|-------|
| RSI divergence | Price making new lows, RSI not; or vice versa | Polygon.io (calculate) | Classic technical signal; medium reliability alone |
| Short interest change | Rising short interest + price weakness = potential squeeze setup | FMP short data | Available on FMP; high asymmetry potential |
| Analyst coverage gap | Few or no analyst estimates on a quality company = institutional neglect = asymmetric potential | FMP analyst data | Core to asymmetric thesis |
| Options flow anomaly | Unusual call/put buying before news | Not in Polygon/FMP; needs separate data | Hard with current stack; flag as future |
| Revenue acceleration | Revenue growth rate increasing QoQ | FMP fundamentals | Better predictor than absolute revenue level |
| Management guidance delta | Forward guidance vs prior quarter guidance | FMP earnings transcripts | Requires NLP; medium complexity |

### Tier 3: Alternative data (future scope, not MVP)

| Signal Type | Why Valuable | Data Source |
|-------------|-------------|-------------|
| Web traffic trends | Leading indicator for consumer businesses | SimilarWeb API (paid) |
| Job posting velocity | Proxy for company growth/contraction | LinkedIn / Thinknum (expensive) |
| Satellite/geolocation data | Foot traffic, industrial activity | Expensive; not MVP |
| Credit card spend data | Consumer behavior leading indicator | Very expensive |

---

## What Comparable Systems Do Well vs Poorly

### TradingAgents (open-source, ICML 2025)

**Does well:**
- Structured bull/bear debate mechanism with configurable rounds
- Role specialization (7 distinct agent types)
- Multi-modal signal integration (fundamental + sentiment + news + technical)
- Natural language explainability
- LangGraph-based modularity; swappable LLM providers

**Does poorly:**
- No visual agent operating system — purely code/CLI
- No investor persona differentiation (all agents are generic)
- No asymmetric opportunity filter
- No proactive scanning loop; requires per-stock invocation
- No persistent opportunity feed or alert system

### AutoHedge (open-source Python library)

**Does well:**
- Clean 4-agent architecture (Director, Quant, Risk, Execution)
- Risk-first design with position sizing
- JSON-structured outputs; production-ready with FastAPI
- Rapid prototyping velocity

**Does poorly:**
- No debate/committee mechanism — single pass per agent
- No investor personas
- No UI layer at all
- Backtested returns shown in marketing material are not reproducible in real markets
- No feed, history, or alert system

### FinGPT (AI4Finance Foundation)

**Does well:**
- Strong financial sentiment analysis (87% F1 on headline classification)
- Financial statement analysis (86% benchmark score)
- Open-source with active research community
- Data pipeline infrastructure for financial NLP

**Does poorly:**
- Consistent bullish bias — degrades performance in bear markets (critical flaw)
- Poor numerical reasoning; financial QA only 28% exact match vs GPT-4's 76%
- No multi-agent architecture
- No portfolio-level or committee logic
- Primarily a model/NLP tool, not a full platform

### Perplexity Finance

**Does well:**
- Fast, accurate earnings call summaries with structured data extraction
- Real-time market data surface with heatmaps
- Accessible to non-technical users
- Good for reactive research (user asks a question)

**Does poorly:**
- Purely reactive — user must initiate every query
- No autonomous scanning or proactive discovery
- No alert system
- Limited global coverage beyond US and India
- No multi-agent reasoning; single LLM call per query

### Kavout

**Does well:**
- Depth of analysis comparable to having "an MBA analyst"
- Quantitative signal scoring (K-Score)
- More rigorous than consumer AI tools

**Does poorly:**
- Still primarily user-initiated research
- No autonomous loop
- Opaque scoring methodology (black box)
- Not open or extensible

---

## Anti-Features

Things that sound like improvements but actively harm the system. Build these only if you have a specific, validated reason.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Real-money autonomous execution | For a personal-use system, autonomous execution is catastrophic risk; a single bad signal = real capital loss; Knight Capital lost $440M in 45 minutes on a bot | Surface decisions as recommendations; require explicit human confirmation to act |
| Backtesting as a trust signal | Backtested returns are reliably 30-40% better than live results; showing them prominently creates false confidence; strategy half-life has dropped from 18 months (2020) to 11 months (2025) | Show backtested figures only with explicit caveats; invest in forward-testing infrastructure instead |
| Maximising agent count | More agents does not mean better signal; it means more API cost, more latency, more failure modes, and more noise averaging | Use the minimum agents needed: typically 3-5 specialized roles outperform 10+ generic ones |
| Real-time continuous re-scoring of the full universe | Scanning every stock every minute is expensive and unnecessary; most signals persist for hours or days | Run full universe sweep on a schedule (e.g., every 4 hours during market hours); only re-score on event triggers (volume spike, news break) |
| Per-tick LLM calls | Using Claude to analyze every price tick is cost-prohibitive and architecturally wrong; LLMs are for reasoning, not streaming data | Use LLMs only on pre-filtered candidates; use deterministic code for price/volume calculations |
| "Confidence scores" displayed as percentages | Users interpret "87% confident" as probabilistic accuracy; LLM confidence is not calibrated probability | Display as qualitative tiers: Strong / Moderate / Speculative; or use relative rankings |
| Feature parity with Bloomberg Terminal | The goal is an opinionated AI discovery tool, not a full terminal; feature bloat destroys focus and doubles build time | Prioritize the feed, agent graph, and opportunity cards; leave charting to a linked Tradingview embed |
| Complex position sizing for personal use | A personal system doesn't need Kelly criterion or factor-based allocation math; it needs clear "this is interesting, here's why" | Output conviction tier and a rough % allocation suggestion; leave actual sizing to the user |
| Training/fine-tuning custom models | Fine-tuning an LLM on financial data requires massive data, compute, and expertise; results rarely beat a well-prompted frontier model | Invest in prompt engineering and structured personas; use Claude or GPT-4 class models with rich context |

---

## Feature Dependencies

```
Volume anomaly pre-filter
    → Reduces universe to candidates (required before LLM analysis)

Candidate list
    → Feeds analyst agents (fundamental, sentiment, technical, news)

Analyst reports
    → Feed bull/bear researcher debate

Debate transcript
    → Feeds committee vote aggregation

Committee outcome + individual persona votes
    → Feeds CIO meta-agent final decision

CIO decision
    → Written to opportunity feed
    → Triggers alert (if conviction = Strong)
    → Stored in opportunity history with full audit trail

Visual agent graph
    → Reads live state from each agent node (requires event system / state store)
    → Requires the above pipeline to emit events, not just final results
```

Key constraint: the visual graph requires the pipeline to emit granular state events during processing, not just when complete. Design the pipeline with an event emitter from day one; retrofitting this is painful.

---

## MVP Recommendation

For a working personal-use platform, prioritize in this order:

### Must have for MVP (Phase 1-2)

1. Volume anomaly pre-filter (pre-screens universe cheaply)
2. Polygon.io + FMP data ingestion with error handling
3. Fundamental + sentiment + technical analyst agents (3 specialized agents minimum)
4. Committee vote with at least 2 investor personas (e.g., Buffett + Ackman as extremes)
5. Opportunity feed (list view with conviction tier, ticker, date, summary)
6. Persistent opportunity log (PostgreSQL or SQLite)
7. Telegram alert on Strong conviction opportunities

### Build next (Phase 3-4)

8. Bull/bear debate mechanism with configurable rounds
9. All 5 investor personas (Buffett, Munger, Ackman, Cohen, Dalio)
10. CIO meta-agent final decision layer
11. Visual agent graph (React Flow or similar)
12. Opportunity replay / history mode
13. Asymmetric/10x filter (analyst coverage gap + short interest + catalyst proximity)

### Defer to post-MVP

- **Insider transaction signal layer**: Worth building, but adds complexity; add in Phase 4
- **Regime detection / macro context agent**: High value, medium complexity; Phase 4+
- **Options flow signals**: Requires different data provider; future phase
- **Alternative data sources**: Expensive and complex; out of scope for personal use v1

---

## Sources

- TradingAgents paper and site (ICML 2025): https://tradingagents-ai.github.io/ | https://arxiv.org/abs/2412.20138
- AutoHedge guide (BrightCoding, Nov 2025): https://www.blog.brightcoding.dev/2025/11/26/autohedge-build-your-autonomous-ai-hedge-fund-in-minutes-2025-guide/
- BattleFin AI Alpha Signal Platform Survey: https://www.battlefin.com/the-ai-inflection-point/11-best-ai-alternative-data-analytics-platforms-for-alpha-signal
- FinGPT capabilities assessment (arxiv, 2025): https://arxiv.org/html/2507.08015v1
- Perplexity Finance review (techpoint.africa, 2025): https://techpoint.africa/guide/perplexity-finance-review/
- AI for Trading 2026 Complete Guide (LiquidityFinder): https://liquidityfinder.com/insight/technology/ai-for-trading-2025-complete-guide
- AI trading pitfalls — overfitting, implementation gap, strategy half-life (QuantInsti): https://www.quantinsti.com/articles/ai-for-trading/
- Alpha generation with predictive analytics (CYB Software): https://cybsoftware.com/how-hedge-funds-can-use-ai-to-generate-alpha-with-predictive-analytics-a-6-step-strategy/
- Hybrid AI trading system with regime-adaptive equity strategies (arxiv 2601.19504): https://arxiv.org/html/2601.19504v1
- AI alpha signal platforms for hedge funds (Permutable.ai): https://permutable.ai/best-financial-market-data-providers-for-hedge-funds/
