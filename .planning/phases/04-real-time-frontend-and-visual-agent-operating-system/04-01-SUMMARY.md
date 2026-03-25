---
phase: 04-real-time-frontend-and-visual-agent-operating-system
plan: 01
subsystem: ui
tags: [vite, react, typescript, tailwind, xyflow, react-flow, zustand, dagre, shadcn, sse, bloomberg]

# Dependency graph
requires:
  - phase: 03-agent-analysis-engine
    provides: SSE /api/v1/events/stream endpoint with pipeline:events Redis channel;
              opportunities API at /api/v1/opportunities
provides:
  - Vite SPA scaffold with React 19 + TypeScript + Tailwind v4
  - Three-panel Bloomberg dark dashboard at localhost:5173
  - React Flow 10-node pipeline graph with dagre LR layout
  - Zustand store holding nodes, edges, feedItems, outputRankings
  - SSE EventSource hook connecting to /api/v1/events/stream
  - Custom node types (AgentNode, GateNode, StageNode) with status-driven styling
  - shadcn/ui component suite (card, badge, scroll-area, separator, sheet)
affects:
  - 04-02 (animated edges, real-time node state updates)
  - 04-03 (OpportunityFeed panel — full implementation)
  - 04-04 (OutputDashboard panel — full implementation)

# Tech tracking
tech-stack:
  added:
    - "@xyflow/react ^12"
    - "zustand ^5"
    - "@dagrejs/dagre ^1"
    - "tailwindcss v4 + @tailwindcss/vite"
    - "shadcn/ui (New York style, Zinc base)"
    - "class-variance-authority, clsx, tailwind-merge"
    - "lucide-react"
    - "Inter + JetBrains Mono (Google Fonts)"
  patterns:
    - "nodeTypes defined at module level (not inside render) to avoid React Flow re-registration"
    - "dagre layout computed once at store module load, not per render"
    - "Zustand slice selectors — components subscribe only to needed state slices"
    - "SSE hook creates single EventSource, closes on unmount, logs onerror without rethrowing"

key-files:
  created:
    - frontend/package.json
    - frontend/vite.config.ts
    - frontend/tsconfig.app.json
    - frontend/src/index.css
    - frontend/src/lib/dagre.ts
    - frontend/src/store/pipelineStore.ts
    - frontend/src/hooks/usePipelineSSE.ts
    - frontend/src/components/layout/DashboardLayout.tsx
    - frontend/src/components/graph/PipelineGraph.tsx
    - frontend/src/components/graph/nodes/AgentNode.tsx
    - frontend/src/components/graph/nodes/GateNode.tsx
    - frontend/src/components/graph/nodes/StageNode.tsx
    - frontend/src/components/feed/OpportunityFeed.tsx
    - frontend/src/components/output/OutputDashboard.tsx
    - frontend/src/components/ui/{card,badge,scroll-area,separator,sheet}.tsx
  modified:
    - .gitignore (added node_modules, frontend/dist, frontend/.vite entries)

key-decisions:
  - "04-01-D1: shadcn/ui components created manually (not via npx shadcn init) — avoids interactive CLI in non-interactive execution context; identical output"
  - "04-01-D2: @radix-ui/react-dialog used for Sheet (no @radix-ui/react-sheet package exists) — shadcn Sheet is a Dialog variant"
  - "04-01-D3: nodeTypes object defined at PipelineGraph module level — React Flow anti-pattern prevention; prevents node re-registration on every render"
  - "04-01-D4: dagre layout runs once at pipelineStore.ts module load — avoids re-layout on every state update"
  - "04-01-D5: StageNode suppresses target Handle for scanner and source Handle for cio — entry/sink nodes in pipeline topology"

patterns-established:
  - "Bloomberg dark: body bg #0a0a0b, zinc-900 nodes, zinc-700/800 borders, #0A84FF primary"
  - "SSE event shape: {event: 'pipeline', data: JSON.stringify({event: 'AGENT_STARTED', data: {...}})}"
  - "Node status transitions: idle -> running -> complete | error, driven by handleSSEEvent"

# Metrics
duration: 5min
completed: 2026-03-25
---

# Phase 4 Plan 1: Frontend Scaffold Summary

**Vite + React Flow SPA with 10-node Bloomberg dark pipeline graph, Zustand SSE-driven store, and three-panel dashboard layout at localhost:5173**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-25T22:40:30Z
- **Completed:** 2026-03-25T22:45:41Z
- **Tasks:** 2/2
- **Files modified:** 29

## Accomplishments

- Complete Vite SPA scaffold from zero with all dependencies installed and TypeScript passing clean
- React Flow pipeline graph showing all 10 nodes (scanner -> signal_detector -> quality_gate -> 5 agents -> committee -> cio) in dagre LR layout with Bloomberg dark aesthetics
- Zustand store wired to SSE hook that parses the backend's `event: pipeline` / inner JSON event shape and dispatches status updates to pipeline nodes

## Task Commits

1. **Task 1: Scaffold Vite SPA with Tailwind v4, shadcn/ui, Bloomberg dark theme** — `ad6b5b1` (feat)
2. **Task 2: Zustand store, SSE hook, dagre layout, React Flow pipeline graph, three-panel layout** — `06328a9` (feat)

**Plan metadata:** committed with docs(04-01) commit after SUMMARY

## Files Created/Modified

- `frontend/package.json` — Vite + React + xyflow + zustand + dagre + shadcn deps
- `frontend/vite.config.ts` — @tailwindcss/vite plugin, @/ alias, /api proxy
- `frontend/src/index.css` — Bloomberg dark CSS variables, .bloomberg-flow React Flow overrides
- `frontend/src/lib/dagre.ts` — getLayoutedElements() with LR direction, NODE_WIDTH=172
- `frontend/src/store/pipelineStore.ts` — full pipeline store with 10 nodes + SSE event dispatcher
- `frontend/src/hooks/usePipelineSSE.ts` — EventSource listening for 'pipeline' named SSE events
- `frontend/src/components/layout/DashboardLayout.tsx` — CSS grid 1fr/320px/380px, 100dvh
- `frontend/src/components/graph/PipelineGraph.tsx` — nodeTypes at module level, colorMode=dark
- `frontend/src/components/graph/nodes/AgentNode.tsx` — status-driven border, animate-pulse on running
- `frontend/src/components/graph/nodes/GateNode.tsx` — amber border, ShieldCheck icon, diamond corners
- `frontend/src/components/graph/nodes/StageNode.tsx` — status dot, no handles for entry/sink nodes
- `frontend/src/components/ui/{card,badge,scroll-area,separator,sheet}.tsx` — shadcn UI primitives

## Decisions Made

- **D1:** shadcn/ui components created manually rather than via `npx shadcn init` to avoid interactive CLI issues in automated execution. Output is identical.
- **D2:** Sheet component backed by `@radix-ui/react-dialog` (no standalone `@radix-ui/react-sheet` package exists — confirmed by npm 404).
- **D3:** `nodeTypes` object defined at PipelineGraph module level (not inside the component). This is the primary React Flow anti-pattern that causes all node instances to remount on every render.
- **D4:** dagre layout runs once at `pipelineStore.ts` module load and results stored as `initialNodes`. Subsequent state updates (status changes) use `applyNodeChanges` which preserves computed positions.
- **D5:** `StageNode` suppresses its target Handle when `id === 'scanner'` and source Handle when `id === 'cio'` to reflect the entry/sink topology accurately.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] @radix-ui/react-sheet does not exist as an npm package**

- **Found during:** Task 1 (dependency installation)
- **Issue:** package.json listed `@radix-ui/react-sheet@^1.1.6` which returns npm 404 — shadcn's Sheet is built on `@radix-ui/react-dialog`
- **Fix:** Replaced with `@radix-ui/react-dialog@^1.1.6` in package.json; implemented Sheet component wrapping Dialog primitives (exact pattern shadcn generates)
- **Files modified:** frontend/package.json, frontend/src/components/ui/sheet.tsx
- **Verification:** `npm install` succeeded with 0 errors; sheet.tsx compiles with no TS errors
- **Committed in:** ad6b5b1 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Required fix; Sheet is correctly implemented using the underlying Dialog primitive exactly as shadcn generates it. No scope change.

## Issues Encountered

None beyond the npm package name deviation above.

## Next Phase Readiness

- Foundation complete: Vite dev server starts at localhost:5173, TypeScript clean, all dependencies installed
- React Flow graph renders 10 pipeline nodes with dagre LR layout
- Zustand store ready to receive live SSE state updates from Phase 3 backend
- 04-02 can immediately add animated edges and real-time node status transitions
- 04-03 can implement full OpportunityFeed (ScrollArea panel, feedItems from store)
- 04-04 can implement full OutputDashboard (opportunity rankings, conviction scores)

---
*Phase: 04-real-time-frontend-and-visual-agent-operating-system*
*Completed: 2026-03-25*
