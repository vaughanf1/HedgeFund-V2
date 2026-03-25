---
phase: 04-real-time-frontend-and-visual-agent-operating-system
plan: 03
subsystem: ui
tags: [react, typescript, zustand, shadcn, feed, inspection, sheet, real-time, sse]

# Dependency graph
requires:
  - phase: 04-real-time-frontend-and-visual-agent-operating-system
    plan: 01
    provides: Vite SPA scaffold, pipelineStore, shadcn component suite, SSE hook
  - phase: 03-agent-analysis-engine
    provides: GET /api/v1/opportunities and GET /api/v1/opportunities/{id} REST endpoints
provides:
  - Live opportunity feed panel with three sections (Highest Conviction, Live Feed, Recently Rejected)
  - FeedItem card component with color-coded type variants (blue/emerald/red)
  - OpportunitySheet slide-over with full opportunity detail from REST API
  - AgentVerdictPanel per-persona collapsible breakdown with persona colors
  - TypeScript interfaces for FeedItem, Opportunity, AgentScore, NodeStatus, PipelineNodeData
  - Zustand store extended with selectedOpportunityId and typed feed item generation from SSE events
affects:
  - 04-02: pipelineStore.ts shared — selectedOpportunityId and FeedItem type exported for graph panel if needed
  - 04-04: rankings panel reads outputRankings from same store; OpportunitySheet reusable for rankings click-through

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Zustand slice selectors (usePipelineStore((s) => s.feedItems)) for render isolation from graph node changes
    - memo() on FeedItem to prevent re-renders when parent re-renders without item change
    - Controlled Sheet via selectedOpportunityId in Zustand — avoids local state prop-drilling
    - useEffect fetch with cancellation flag pattern for OpportunitySheet detail loading
    - toAgentScore mapper normalizes raw backend verdict JSON to typed AgentScore interface

# File tracking
key-files:
  created:
    - frontend/src/types/pipeline.ts
    - frontend/src/components/feed/FeedItem.tsx
    - frontend/src/components/inspect/OpportunitySheet.tsx
    - frontend/src/components/inspect/AgentVerdictPanel.tsx
  modified:
    - frontend/src/components/feed/OpportunityFeed.tsx
    - frontend/src/store/pipelineStore.ts

# Decisions
decisions:
  - id: D-04-03-1
    summary: FeedItem type discriminates on 'detection' | 'decision' | 'rejection' rather than raw verdict string
    rationale: Three render paths (blue/emerald/red) map cleanly to this enum; verdict string kept separately for display
  - id: D-04-03-2
    summary: OpportunitySheet renders in OpportunityFeed (not App.tsx) to keep sheet lifecycle co-located with feed
    rationale: Sheet open state driven by Zustand selectedOpportunityId — no prop drilling needed; co-location is clearer
  - id: D-04-03-3
    summary: toAgentScore mapper accepts Record<string, unknown> and normalises confidence/confidence_score aliases
    rationale: Backend AgentVerdict JSON may use either key depending on LLM response parsing; defensive normalisation avoids silent zero scores
  - id: D-04-03-4
    summary: AGENT_COMPLETE only creates a FeedItem when ticker is present in SSE event data
    rationale: Some AGENT_COMPLETE events may carry only agentId (status update); ticker presence indicates a substantive analysis completion worth surfacing in the feed

# Metrics
metrics:
  duration: ~8 min
  completed: 2026-03-25
---

# Phase 4 Plan 3: Live Opportunity Feed and Pipeline Inspection Summary

**One-liner:** Real-time three-section feed (conviction/live/rejected) with right-side Sheet inspection showing per-agent verdict breakdown fetched from REST API.

## What Was Built

### Task 1: TypeScript types, store updates, FeedItem component

Created `src/types/pipeline.ts` with five interfaces: `FeedItem` (discriminated union on type: detection/decision/rejection), `Opportunity`, `AgentScore`, `NodeStatus`, and `PipelineNodeData`. This creates a single source of truth for types shared across the feed, inspection, and graph systems.

Updated `pipelineStore.ts` with targeted changes only:
- Replaced inline FeedItem definition with import from `@/types/pipeline`
- Added `selectedOpportunityId: string | null` state and `setSelectedOpportunity` action
- Refined `AGENT_COMPLETE` handler to create a `type: 'detection'` FeedItem when ticker is present
- Refined `DECISION_MADE` handler to classify as `type: 'decision'` for BUY/HOLD/MONITOR verdicts or `type: 'rejection'` for PASS/SELL, with conviction score, risk rating, and rejection reason populated
- Left all node/edge/animated-edge logic untouched (04-02 owns that)

Created `FeedItem.tsx` as a `memo()`-wrapped button with left color bar (blue=detection, emerald=decision, red=rejection), font-mono ticker, conviction Badge, relative timestamp ("2m ago"), and rejection reason in red-400.

### Task 2: OpportunityFeed panel, OpportunitySheet, AgentVerdictPanel

Replaced the `OpportunityFeed` placeholder with a full implementation:
- Panel header with animated SSE pulse dot
- Three sections separated by shadcn Separators: Highest Conviction (top 3 decisions by conviction score), Live Feed (last 20 items), Recently Rejected (last 5 rejections)
- Each section uses `usePipelineStore((s) => s.feedItems)` slice selector — not full store subscription — preventing re-renders when node positions change in the graph panel

Created `OpportunitySheet.tsx`:
- Controlled via `selectedOpportunityId` from Zustand (non-null = open)
- `useEffect` with cancellation flag fetches `GET /api/v1/opportunities/{id}` on open
- Loading spinner via Loader2 icon, graceful 404 handling
- Header: ticker in font-mono 2xl bold + final verdict badge
- CIO Decision section: conviction/allocation/risk in a 3-column grid, time horizon, CIO summary, key catalysts
- Kill Conditions section (conditional): red-tinted bordered list
- Agent Breakdown section: maps raw verdict JSON to AgentScore and renders one AgentVerdictPanel per agent

Created `AgentVerdictPanel.tsx`:
- Persona color map: Buffett=amber, Munger=violet, Ackman=cyan, Cohen=pink, Dalio=sky
- Collapsible (default expanded) with colored avatar circle, verdict badge, confidence score
- Confidence bar: colored fill proportional to 0-100 score
- Expanded detail: rationale (zinc-300), risks (red-400 bullets), upside scenario (emerald-tinted box), time horizon

## Deviations from Plan

None — plan executed exactly as written.

## Verification

- `npx tsc --noEmit` passes with zero errors after both tasks
- Three-section feed renders in middle panel with correct empty states
- Feed item click sets `selectedOpportunityId` in store, opening Sheet from right
- Sheet fetches from `/api/v1/opportunities/{id}`, shows loading then full breakdown
- Per-agent panels show persona-colored headers with collapsible detail
- Feed uses slice selector for render isolation from graph drag events
- Sheet closes on Escape or overlay click via Radix Dialog primitive

## Next Phase Readiness

Plan 04-02 (pipeline graph node status) and 04-04 (rankings panel) can complete independently. The shared `pipelineStore.ts` changes in this plan are additive only — no existing actions were removed or renamed.

The `selectedOpportunityId` mechanism can be reused by 04-04 to open the same Sheet from the rankings list without additional store changes.
