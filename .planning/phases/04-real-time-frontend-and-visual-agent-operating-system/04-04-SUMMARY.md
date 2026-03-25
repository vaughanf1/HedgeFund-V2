---
phase: 04-real-time-frontend-and-visual-agent-operating-system
plan: "04"
subsystem: ui
tags: [react, zustand, typescript, tailwind, shadcn]

requires:
  - phase: 04-01
    provides: Vite SPA scaffold, Zustand pipelineStore, three-panel dashboard layout
  - phase: 03-04
    provides: SSE pipeline event stream, REST /api/v1/opportunities endpoints

provides:
  - Ranked opportunity cards in right panel sorted by conviction score
  - useOpportunities hook fetching REST API on mount
  - AgentBreakdown persona-colored component with confidence bars
  - OpportunityCard with conviction score, verdict/risk badges, agent breakdowns, CIO summary
  - OutputDashboard subscribing via Zustand slice selector

affects:
  - Any future phase modifying pipelineStore or output panel

tech-stack:
  added: []
  patterns:
    - "Zustand slice selector for output panel isolation — usePipelineStore((s) => s.outputRankings)"
    - "sortAndCap helper at store level — sort outputRankings by convictionScore desc, cap at 10"
    - "useOpportunities called once in OutputDashboard (not App.tsx) — REST hydration, SSE handles updates"
    - "DECISION_MADE SSE handler builds full Opportunity with agentScores and upserts to outputRankings"

key-files:
  created:
    - frontend/src/hooks/useOpportunities.ts
    - frontend/src/components/output/AgentBreakdown.tsx
    - frontend/src/components/output/OpportunityCard.tsx
  modified:
    - frontend/src/store/pipelineStore.ts
    - frontend/src/components/output/OutputDashboard.tsx

key-decisions:
  - "D-04-04-1: Opportunity imported from @/types/pipeline (not redefined in store) — 04-03 already created types/pipeline.ts with full Opportunity type including agentScores, cioSummary, keyCatalysts"
  - "D-04-04-2: fetchOpportunityDetail exported as standalone async function (not store action) — Zustand store actions must be sync; hook calls this and then calls setOutputRankings"
  - "D-04-04-3: useOpportunities placed in OutputDashboard, not App.tsx — colocation of REST hydration with the panel that displays it; App.tsx only manages SSE lifecycle"
  - "D-04-04-4: convictionScore display normalized in OpportunityCard — backend may return 0-100 int or 0.0-1.0 float; display uses >1 check to show correct integer percentage"

patterns-established:
  - "Slice selector pattern: usePipelineStore((s) => s.outputRankings) prevents cross-panel re-renders when graph nodes change"
  - "sortAndCap: pure sort+slice helper keeps outputRankings always in correct order, called by setOutputRankings and DECISION_MADE handler"

duration: 5min
completed: 2026-03-25
---

# Phase 4 Plan 4: Output Dashboard Summary

**Ranked opportunity cards with conviction scores, per-agent breakdown bars, and CIO summaries, hydrated from REST API and updating live via SSE DECISION_MADE events**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-25T22:49:00Z
- **Completed:** 2026-03-25T22:53:39Z
- **Tasks:** 2/2
- **Files modified:** 5

## Accomplishments

- Right panel now shows top 5-10 opportunities sorted by conviction score, updating in real time
- Each OpportunityCard renders ticker, BUY/SELL/HOLD/MONITOR/PASS badge, risk badge, large conviction number, allocation/horizon/upside metrics, catalysts, 5-agent breakdown rows with persona-colored confidence bars, and CIO summary
- DECISION_MADE SSE handler enhanced to build a full Opportunity object (with agentScores) and upsert it into outputRankings with sort+cap-10
- Slice selector prevents right-panel re-renders when pipeline graph nodes are dragged
- TypeScript compiles with zero errors

## Task Commits

1. **Task 1: useOpportunities hook, store hydration, AgentBreakdown component** - `4798f5e` (feat)
2. **Task 2: OpportunityCard and OutputDashboard panel** - `b89a200` (feat)

**Plan metadata:** (below)

## Files Created/Modified

- `frontend/src/hooks/useOpportunities.ts` - Fetches /api/v1/opportunities?limit=10 + per-opportunity detail on mount; exports `fetchOpportunityDetail` helper
- `frontend/src/components/output/AgentBreakdown.tsx` - Compact row with persona dot (amber/violet/cyan/pink/sky), confidence bar (red/yellow/emerald), score, and verdict
- `frontend/src/components/output/OpportunityCard.tsx` - Full opportunity card with all metrics; left border accent by verdict color; memo-wrapped
- `frontend/src/components/output/OutputDashboard.tsx` - Replaces placeholder; slice selector, useOpportunities hook, ScrollArea, empty state
- `frontend/src/store/pipelineStore.ts` - Imports Opportunity from @/types/pipeline; sortAndCap helper; setOutputRankings sorts+caps; DECISION_MADE builds+upserts Opportunity

## Decisions Made

- D-04-04-1: Opportunity imported from @/types/pipeline — 04-03 already created a complete types file
- D-04-04-2: fetchOpportunityDetail is a standalone async function, not a store action — Zustand store actions must be synchronous
- D-04-04-3: useOpportunities placed in OutputDashboard — colocation keeps REST hydration near the panel that displays it
- D-04-04-4: convictionScore display normalization — backend returns 0-100 int; OpportunityCard shows as-is if >1, else multiplies by 100

## Deviations from Plan

None — plan executed exactly as written. types/pipeline.ts was already present from the parallel 04-03 plan, which matched the expected interface.

## Issues Encountered

- Formatter/linter was modifying pipelineStore.ts between reads and write attempts. Resolved by writing the full file in a single bash heredoc operation to avoid race conditions.

## Next Phase Readiness

- Phase 4 output dashboard complete — all four panels now functional (pipeline graph, activity feed, inspection sheet, ranked opportunities)
- Backend SSE stream feeds all three active panels in real time
- REST API hydrates output rankings on mount
- Phase 4 fully delivered; system is end-to-end from market scanner to ranked opportunity display

---
*Phase: 04-real-time-frontend-and-visual-agent-operating-system*
*Completed: 2026-03-25*
