# Phase 4: Real-Time Frontend and Visual Agent Operating System - Research

**Researched:** 2026-03-25
**Domain:** React Flow graph UI, SSE event-driven state, Bloomberg dark dashboard aesthetic
**Confidence:** HIGH (core stack verified via official docs and Context7-equivalent sources)

## Summary

Phase 4 builds a Bloomberg-style dark dashboard with three main surfaces: a React Flow graph showing the live agent pipeline, a live opportunity feed driven by SSE, and a ranked output panel with full breakdowns. All data flows from the existing Phase 3 SSE endpoint into a centralized Zustand store, which drives both the React Flow graph and the feed/output panels without polling.

The standard approach is: browser `EventSource` connects to the FastAPI SSE endpoint → events parsed and dispatched to a Zustand store → store updates drive React Flow node `data` updates (via `useNodesState` or direct store mutation) and feed/output list state. React Flow v12 (package: `@xyflow/react`) provides the graph canvas with built-in `colorMode="dark"` support and CSS variable overrides for the Bloomberg palette. `@dagrejs/dagre` calculates the static pipeline layout once at boot. shadcn/ui components (Card, Badge, Table, ScrollArea) compose the feed and output panels, all styled with Tailwind v4 OKLCH dark tokens.

FastAPI now has native SSE via `from fastapi.sse import EventSourceResponse` (added in v0.135.0). The Phase 3 endpoint already exists using this pattern. The browser `EventSource` API auto-reconnects natively; no external reconnection library is required for this use case.

**Primary recommendation:** Use `@xyflow/react` v12 with Zustand as the single source of truth for pipeline state; drive all UI surfaces (graph nodes, feed, output panel) from one store updated by a single `useEffect`-managed `EventSource` connection.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@xyflow/react` | 12.10.x | Pipeline graph canvas — nodes, edges, layout | Official React Flow v12 package; built-in dark mode, custom nodes, animated edges |
| `zustand` | 5.x | Single source of truth for SSE-driven pipeline state | React Flow recommends Zustand internally; v5 uses `useSyncExternalStore` for performant updates |
| `@dagrejs/dagre` | 3.x | Static pipeline graph layout (left-to-right) | Actively maintained scoped package; official React Flow dagre example uses it |
| `@xyflow/react` CSS | (bundled) | Required base styles for React Flow | Must import `@xyflow/react/dist/style.css` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `shadcn/ui` | latest | Card, Badge, Table, ScrollArea, Separator components | Feed panel, output dashboard, detail views |
| `tailwindcss` | 4.x | Utility styling with OKLCH dark tokens | All layout and color; already in stack |
| `tw-animate-css` | latest | CSS animations (replaces tailwindcss-animate in v4) | Node state transition animations, feed item fade-in |
| Browser `EventSource` | native | SSE client with auto-reconnect | Built-in, no npm package needed for basic SSE |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Native `EventSource` | `@microsoft/fetch-event-source` | Fetch-based SSE supports POST and custom headers; only needed if auth headers required on the SSE connection — not needed here since the endpoint is same-origin and no POST body is required |
| `@dagrejs/dagre` | `elkjs` | ELK is more configurable and async but adds complexity; dagre is synchronous and sufficient for a fixed 10-node pipeline |
| Zustand | React Context + useReducer | Context re-renders all consumers on every event; Zustand uses selective subscriptions — essential for high-frequency SSE events |

### Installation

```bash
npm install @xyflow/react zustand @dagrejs/dagre
```

shadcn/ui and Tailwind v4 are assumed already installed from Phase 1.

Add required shadcn components:
```bash
npx shadcn@latest add card badge table scroll-area separator
```

---

## Architecture Patterns

### Recommended Project Structure

```
src/
├── store/
│   └── pipelineStore.ts       # Zustand store — nodes state, feed items, output rankings
├── hooks/
│   └── usePipelineSSE.ts      # Single EventSource connection, dispatches to store
├── components/
│   ├── graph/
│   │   ├── PipelineGraph.tsx  # <ReactFlow> wrapper with dagre-laid-out nodes
│   │   ├── nodes/
│   │   │   ├── AgentNode.tsx  # Custom node — shows agent name, status, last event
│   │   │   └── GateNode.tsx   # Quality gate node variant
│   │   └── edges/
│   │       └── AnimatedEdge.tsx  # Edge with SVG animateMotion dot for active flow
│   ├── feed/
│   │   ├── OpportunityFeed.tsx   # Live feed — new detections, trending, rejected
│   │   └── FeedItem.tsx
│   ├── output/
│   │   ├── OutputDashboard.tsx   # Ranked top 5-10 opportunities
│   │   ├── OpportunityCard.tsx   # Conviction, risk, upside, per-agent breakdown
│   │   └── AgentBreakdown.tsx    # Per-agent score + reasoning rows
│   └── layout/
│       └── DashboardLayout.tsx   # Three-panel layout: graph | feed | output
└── lib/
    └── dagre.ts                  # getLayoutedElements() utility
```

### Pattern 1: Centralized Zustand Store for Pipeline State

**What:** One Zustand store holds React Flow node/edge state AND feed items AND output rankings. SSE events mutate the store; React Flow and panel components each subscribe to their slice.

**When to use:** Always — prevents prop drilling and avoids context re-render cascade from high-frequency SSE events.

**Example:**
```typescript
// Source: React Flow state management docs + Zustand v5 pattern
import { create } from 'zustand';
import { Node, Edge, applyNodeChanges, NodeChange } from '@xyflow/react';

interface PipelineState {
  nodes: Node[];
  edges: Edge[];
  feedItems: FeedItem[];
  outputRankings: Opportunity[];
  // React Flow required handler
  onNodesChange: (changes: NodeChange[]) => void;
  // SSE event handlers
  handleAgentStarted: (agentId: string) => void;
  handleAgentComplete: (agentId: string, data: AgentResult) => void;
  handleDecisionMade: (opportunity: Opportunity) => void;
}

export const usePipelineStore = create<PipelineState>((set, get) => ({
  nodes: initialNodes,   // dagre-layouted static pipeline nodes
  edges: initialEdges,
  feedItems: [],
  outputRankings: [],

  onNodesChange: (changes) =>
    set({ nodes: applyNodeChanges(changes, get().nodes) }),

  handleAgentStarted: (agentId) =>
    set({
      nodes: get().nodes.map((n) =>
        n.id === agentId
          ? { ...n, data: { ...n.data, status: 'running' } }
          : n
      ),
    }),

  handleAgentComplete: (agentId, result) =>
    set({
      nodes: get().nodes.map((n) =>
        n.id === agentId
          ? { ...n, data: { ...n.data, status: 'complete', result } }
          : n
      ),
    }),

  handleDecisionMade: (opportunity) =>
    set({
      outputRankings: [opportunity, ...get().outputRankings]
        .sort((a, b) => b.convictionScore - a.convictionScore)
        .slice(0, 10),
      feedItems: [
        { type: 'decision', opportunity, timestamp: Date.now() },
        ...get().feedItems,
      ].slice(0, 100),
    }),
}));
```

### Pattern 2: Single SSE Hook — One Connection, All Events

**What:** One `useEffect` creates the `EventSource`, routes named event types to store actions, and closes on unmount. Mounted at the top of the dashboard component tree.

**When to use:** Always — multiple `EventSource` instances to the same URL is wasteful and causes duplicate state updates.

**Example:**
```typescript
// Source: FastAPI SSE docs + browser EventSource API
export function usePipelineSSE(url: string) {
  const store = usePipelineStore();

  useEffect(() => {
    const es = new EventSource(url);

    es.addEventListener('AGENT_STARTED', (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      store.handleAgentStarted(data.agent_id);
    });

    es.addEventListener('AGENT_COMPLETE', (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      store.handleAgentComplete(data.agent_id, data);
    });

    es.addEventListener('DECISION_MADE', (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      store.handleDecisionMade(data);
    });

    es.onerror = () => {
      // EventSource reconnects automatically — no manual retry needed
      // onerror fires on reconnect attempt, not just fatal errors
    };

    return () => es.close();
  }, [url]);
}
```

**Key:** The browser `EventSource` API reconnects automatically when the connection drops. The `retry` field in SSE messages controls the reconnect delay (default ~3s). No additional reconnection library is needed.

### Pattern 3: Custom Agent Node with Status-Driven Appearance

**What:** Custom React Flow node component that receives `data.status` and renders a visually distinct state (idle, running, complete, error). Define `nodeTypes` **outside** the component tree or memoize with `useMemo`.

**When to use:** All agent pipeline nodes — scanner, signal detector, quality gate, five agents, committee, CIO.

**Example:**
```typescript
// Source: React Flow custom node docs + common errors docs
import { NodeProps, Handle, Position } from '@xyflow/react';
import { memo } from 'react';

type AgentNodeData = {
  label: string;
  status: 'idle' | 'running' | 'complete' | 'error';
  lastResult?: string;
};

export const AgentNode = memo(({ data, isConnectable }: NodeProps<AgentNodeData>) => {
  const statusClasses = {
    idle:     'border-zinc-700 bg-zinc-900',
    running:  'border-blue-500 bg-blue-950 animate-pulse',
    complete: 'border-emerald-500 bg-emerald-950',
    error:    'border-red-500 bg-red-950',
  };

  return (
    <div className={`rounded-lg border px-4 py-2 min-w-[140px] ${statusClasses[data.status]}`}>
      <Handle type="target" position={Position.Left} isConnectable={isConnectable} />
      <p className="text-xs font-mono text-zinc-400 uppercase tracking-wider">Agent</p>
      <p className="text-sm font-semibold text-white">{data.label}</p>
      {data.lastResult && (
        <p className="text-xs text-zinc-400 mt-1 truncate">{data.lastResult}</p>
      )}
      <Handle type="source" position={Position.Right} isConnectable={isConnectable} />
    </div>
  );
});

// CRITICAL: Define nodeTypes outside component render or with useMemo
// Defining inline causes React Flow to re-register types every render
const nodeTypes = { agent: AgentNode, gate: GateNode };
```

### Pattern 4: Dagre Static Layout for Pipeline Graph

**What:** Run dagre once at module load to calculate left-to-right positions for the 10-node pipeline. The layout is static (fixed pipeline topology), so no dynamic re-layout is needed.

**When to use:** Initial node setup. Don't re-run dagre on every SSE event — positions never change, only node `data` changes.

**Example:**
```typescript
// Source: React Flow dagre example docs
import dagre from '@dagrejs/dagre';
import { Node, Edge, Position } from '@xyflow/react';

const NODE_WIDTH = 172;
const NODE_HEIGHT = 56;

export function getLayoutedElements(nodes: Node[], edges: Edge[], direction = 'LR') {
  const graph = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  graph.setGraph({ rankdir: direction, ranksep: 80, nodesep: 40 });

  nodes.forEach((n) => graph.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT }));
  edges.forEach((e) => graph.setEdge(e.source, e.target));

  dagre.layout(graph);

  return {
    nodes: nodes.map((n) => {
      const pos = graph.node(n.id);
      return {
        ...n,
        position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      };
    }),
    edges,
  };
}
```

### Pattern 5: Animated Edge for Active Data Flow

**What:** Use `<animateMotion>` SVG element on a dot that travels along the edge path to show active data flow direction. Toggle animation only when the source node status is `'running'`.

**Example:**
```typescript
// Source: React Flow animating-edges docs
import { BaseEdge, EdgeProps, getSmoothStepPath } from '@xyflow/react';

export function AnimatedFlowEdge({ id, sourceX, sourceY, targetX, targetY,
  sourcePosition, targetPosition, data }: EdgeProps) {

  const [edgePath] = getSmoothStepPath({ sourceX, sourceY, sourcePosition,
    targetX, targetY, targetPosition });

  return (
    <>
      <BaseEdge id={id} path={edgePath} style={{ stroke: '#3f3f46' }} />
      {data?.active && (
        <circle r="4" fill="#0A84FF">
          <animateMotion dur="1.5s" repeatCount="indefinite" path={edgePath} />
        </circle>
      )}
    </>
  );
}
```

### Pattern 6: React Flow Dark Mode Configuration

**What:** Pass `colorMode="dark"` to `<ReactFlow>` and override CSS variables on the `.react-flow` selector for the Bloomberg palette.

**Example:**
```typescript
// Source: React Flow theming docs
<ReactFlow
  nodes={nodes}
  edges={edges}
  nodeTypes={nodeTypes}
  edgeTypes={edgeTypes}
  onNodesChange={onNodesChange}
  colorMode="dark"
  fitView
  fitViewOptions={{ padding: 0.2 }}
  className="bloomberg-flow"
/>
```

```css
/* globals.css — Override React Flow CSS variables for Bloomberg dark theme */
.bloomberg-flow {
  --xy-background-color-default: #0a0a0b;
  --xy-node-background-color-default: #18181b;
  --xy-node-border-default: 1px solid #3f3f46;
  --xy-edge-stroke-default: #3f3f46;
  --xy-edge-stroke-selected-default: #0A84FF;
  --xy-handle-background-color-default: #0A84FF;
}
```

### Anti-Patterns to Avoid

- **Defining `nodeTypes`/`edgeTypes` inline inside render:** Causes React Flow to re-register node types every render, leading to flash/remounting. Define them outside the component or use `useMemo`.
- **Accessing `nodes` array directly in panel components:** Every node position change (from drag, pan, zoom) triggers re-render of anything subscribed to `nodes`. Use `useNodesData(id)` for targeted subscriptions.
- **Using `ReactFlowProvider` inside the same component as `useReactFlow`:** The provider must wrap the component from *outside*. Inner usage fails with a Zustand context error.
- **Re-running dagre layout on every SSE event:** Pipeline topology is fixed. Only node `data` needs to change on SSE events, not positions.
- **Multiple `EventSource` instances to same URL:** Creates duplicate events and multiplies state updates. One hook, one connection.
- **Calling `updateNodeInternals` unnecessarily:** Only needed when handle *positions* change programmatically. Not needed for data/status changes.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Graph layout (node positions) | Manual x/y coordinate math | `@dagrejs/dagre` with `getLayoutedElements()` | Edge routing, rank direction, spacing algorithms are non-trivial |
| SSE reconnection logic | Manual `setTimeout` retry loop | Browser native `EventSource` (auto-reconnects) | Built-in exponential backoff, `Last-Event-ID` header handling, `retry:` field respect |
| Dark mode theming | Manual CSS class toggling | `colorMode="dark"` prop + CSS variable overrides on `.react-flow` | React Flow v12 manages class application and variable scoping |
| Data feed scrollable list | Custom infinite scroll | shadcn/ui `ScrollArea` | Handles cross-browser scrollbar styling, keyboard nav |
| Agent status badge | Custom pill component | shadcn/ui `Badge` with Tailwind variant classes | Accessible, consistent with design system |
| Ranked table | Custom table | shadcn/ui `Table` + `TableRow`/`TableCell` | Responsive, accessible, dark-mode-aware |

**Key insight:** React Flow handles the hardest parts of graph UIs (node measurement, edge routing, zoom/pan, selection). The integration work is purely data-flow: SSE → Zustand → node `data` prop updates.

---

## Common Pitfalls

### Pitfall 1: `nodeTypes` Object Recreated on Render

**What goes wrong:** Custom nodes flash/remount; React Flow logs warnings about node type changes.
**Why it happens:** `const nodeTypes = { agent: AgentNode }` defined inside a component body creates a new object reference on every render.
**How to avoid:** Define `nodeTypes` and `edgeTypes` as module-level constants (outside any component), or use `useMemo` if they must be dynamic.
**Warning signs:** Nodes visually reset their state; console shows "node type changed" warnings.

### Pitfall 2: Subscribing to Full `nodes` Array in Panel Components

**What goes wrong:** Feed panel and output panel re-render on every pixel of node drag/pan.
**Why it happens:** React Flow mutates node positions constantly during interaction; anything subscribed to `nodes` re-renders.
**How to avoid:** Use Zustand slice selectors to subscribe only to `feedItems` or `outputRankings` — not the full `nodes`. Use `useNodesData(nodeId)` inside node components instead of reading from store.
**Warning signs:** Dashboard feels sluggish when dragging the graph.

### Pitfall 3: `ReactFlowProvider` Placement

**What goes wrong:** `useReactFlow()` throws "seems like you have not used zustand provider as an ancestor".
**Why it happens:** `ReactFlowProvider` is placed inside the same component that calls `useReactFlow`.
**How to avoid:** Wrap the `ReactFlow` component with `ReactFlowProvider` from a *parent* component. Or use the `<ReactFlow>` component directly (it includes its own provider) and call hooks only in child components.
**Warning signs:** Runtime error on hook call, not on render.

### Pitfall 4: SSE `onerror` Treated as Fatal

**What goes wrong:** Reconnection logic fires on every reconnect attempt, creating cascading re-connections or state resets.
**Why it happens:** `EventSource.onerror` fires on *every* reconnect attempt, not just permanent failures. `readyState` cycling between `CONNECTING` and `OPEN` is normal.
**How to avoid:** In `onerror`, check `es.readyState`. Only treat as fatal if `readyState === EventSource.CLOSED`. Let the browser handle reconnects.
**Warning signs:** Multiple simultaneous `EventSource` connections visible in browser DevTools.

### Pitfall 5: Missing `@xyflow/react/dist/style.css` Import

**What goes wrong:** Nodes render without backgrounds, handles don't appear, edge routing is broken.
**Why it happens:** The CSS import is mandatory but easy to miss when migrating from older React Flow (`reactflow` → `@xyflow/react`).
**How to avoid:** Add `import '@xyflow/react/dist/style.css';` in `main.tsx` or the root layout.
**Warning signs:** Blank canvas or nodes with missing styling despite correct component code.

### Pitfall 6: Tailwind v4 Animation Library Changed

**What goes wrong:** `tailwindcss-animate` animations break silently in Tailwind v4 projects.
**Why it happens:** `tailwindcss-animate` is deprecated in Tailwind v4; it has been replaced by `tw-animate-css`.
**How to avoid:** Use `tw-animate-css` (installed by default in new shadcn/ui + Tailwind v4 projects). Check `globals.css` for `@import "tw-animate-css"`.
**Warning signs:** `animate-pulse`, `animate-spin` work (they're Tailwind core), but custom `animate-in`/`animate-out` classes from shadcn don't.

### Pitfall 7: Stale SSE State on Page Visibility Change

**What goes wrong:** After tab is backgrounded and foregrounded, node states show as running when they've long completed.
**Why it happens:** Browser throttles background tabs; SSE events may be batched or dropped. The store shows the last-received state, not current server state.
**How to avoid:** On SSE reconnect (detect via `es.onopen` after an `onerror`), fetch current pipeline state from a REST endpoint to reset store, then continue streaming incremental SSE events.
**Warning signs:** Dashboard shows stale "running" status after backgrounding.

---

## Code Examples

Verified patterns from official sources:

### FastAPI Native SSE — Named Events (Phase 3 pattern, already exists)

```python
# Source: FastAPI SSE docs (v0.135.0+)
from fastapi.sse import EventSourceResponse, ServerSentEvent

@app.get("/pipeline/stream", response_class=EventSourceResponse)
async def pipeline_stream():
    async def generator():
        async for message in redis_pubsub.listen():
            event_data = json.loads(message['data'])
            yield ServerSentEvent(
                data=event_data,
                event=event_data['event_type'],  # AGENT_STARTED, AGENT_COMPLETE, etc.
                id=event_data.get('event_id'),
                retry=3000,
            )
    return EventSourceResponse(generator())
```

### React Flow — Full Controlled Flow Setup

```typescript
// Source: React Flow learn/quickstart docs
import { ReactFlow, Background, Controls, MiniMap } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { usePipelineStore } from '../store/pipelineStore';
import { nodeTypes, edgeTypes } from './nodeTypes'; // module-level constant

export function PipelineGraph() {
  const nodes = usePipelineStore((s) => s.nodes);
  const edges = usePipelineStore((s) => s.edges);
  const onNodesChange = usePipelineStore((s) => s.onNodesChange);

  return (
    <div className="w-full h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        colorMode="dark"
        fitView
        className="bloomberg-flow"
      >
        <Background color="#27272a" gap={24} />
        <Controls className="!bg-zinc-900 !border-zinc-700" />
      </ReactFlow>
    </div>
  );
}
```

### Zustand Selector for Feed Panel (No Re-render from Graph Events)

```typescript
// Source: Zustand selective subscription pattern
// Only re-renders when feedItems changes — not when nodes change
const feedItems = usePipelineStore((s) => s.feedItems);
```

### shadcn/ui Opportunity Card Pattern

```typescript
// Source: shadcn/ui Card + Badge docs
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export function OpportunityCard({ opportunity }: { opportunity: Opportunity }) {
  const riskColor = {
    LOW: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    MEDIUM: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    HIGH: 'bg-red-500/10 text-red-400 border-red-500/20',
  }[opportunity.riskRating];

  return (
    <Card className="bg-zinc-900 border-zinc-800">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <span className="font-mono text-sm font-bold text-white">{opportunity.ticker}</span>
          <Badge className={riskColor}>{opportunity.riskRating}</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-bold text-blue-400">
          {(opportunity.convictionScore * 100).toFixed(0)}
          <span className="text-sm text-zinc-400 font-normal ml-1">conviction</span>
        </p>
        {/* Per-agent breakdown */}
        {opportunity.agentScores.map((a) => (
          <div key={a.agentId} className="flex justify-between text-xs text-zinc-400 mt-1">
            <span>{a.agentName}</span>
            <span className="font-mono">{a.score.toFixed(2)}</span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `reactflow` npm package | `@xyflow/react` npm package | React Flow v12 (July 2024) | Must use new package name; old package still works but is deprecated |
| Manual dark mode CSS classes | `colorMode="dark"` prop + CSS variable overrides | React Flow v12 (July 2024) | Built-in dark mode; no manual class toggling |
| `tailwindcss-animate` | `tw-animate-css` | Tailwind v4 (2025) | Required migration for animation utilities |
| HSL CSS variables in shadcn/ui | OKLCH CSS variables | shadcn/ui Tailwind v4 update (early 2026) | More vibrant colors; non-breaking but new `globals.css` format |
| Manual SSE reconnection | Browser native `EventSource` auto-reconnect | Always | `retry:` field controls delay; `Last-Event-ID` for resumption |
| `fastapi-sse` third-party library | `from fastapi.sse import EventSourceResponse` | FastAPI v0.135.0 (2025) | Native SSE; no external package needed |

**Deprecated/outdated:**
- `reactflow` package: Superseded by `@xyflow/react`. Both work but use the new name.
- `tailwindcss-animate`: Replaced by `tw-animate-css` in Tailwind v4 projects.
- `dagre` (unscoped): Last published 6 years ago. Use `@dagrejs/dagre` (actively maintained, v3.x).

---

## Open Questions

1. **SSE authentication / CORS**
   - What we know: Phase 3 endpoint already exists; SSE is same-origin in dev
   - What's unclear: Whether the production SSE endpoint requires auth headers (EventSource can't send custom headers natively)
   - Recommendation: If auth headers are needed in production, switch the SSE hook to `@microsoft/fetch-event-source` which supports `fetch`-style headers. For now, assume same-origin with no auth header requirement.

2. **Opportunity detail inspection (VIS-02, VIS-03) — modal vs. panel**
   - What we know: Requirements say "inspectable via detail views without leaving the dashboard"
   - What's unclear: Whether this should be a slide-over panel, a modal dialog, or an inline expansion
   - Recommendation: Use shadcn/ui `Sheet` (slide-over) component — it preserves dashboard context and works well for dense data without losing the live graph view.

3. **React Flow canvas height in three-panel layout**
   - What we know: React Flow requires explicit width/height on parent element
   - What's unclear: Exact CSS layout strategy for the three-panel dashboard (graph | feed | output) at different viewport sizes
   - Recommendation: Use CSS Grid with `100dvh` for the outer container and explicit `height: 100%` on the graph panel div. Test on 1440px+ screens primarily (Bloomberg aesthetic implies wide monitor).

4. **Volume of SSE events causing re-render pressure**
   - What we know: Pipeline emits AGENT_STARTED + AGENT_COMPLETE per agent (potentially 5+ agents per opportunity, multiple concurrent opportunities)
   - What's unclear: Whether Zustand's batching is sufficient or if `unstable_batchedUpdates` / React 18 auto-batching needs explicit opt-in
   - Recommendation: React 18 auto-batches all state updates including those from event handlers, so this should not require manual intervention. Monitor with React DevTools Profiler in 04-02.

---

## Sources

### Primary (HIGH confidence)
- `https://reactflow.dev/learn` — package name `@xyflow/react`, installation, core API
- `https://reactflow.dev/api-reference/react-flow` — ReactFlow component props (nodeTypes, edgeTypes, colorMode, onNodesChange)
- `https://reactflow.dev/learn/advanced-use/state-management` — Zustand integration pattern, immutable node updates
- `https://reactflow.dev/learn/advanced-use/performance` — memoization requirements for nodeTypes/edgeTypes
- `https://reactflow.dev/learn/troubleshooting/common-errors` — ReactFlowProvider placement, nodeTypes recreation pitfall
- `https://reactflow.dev/examples/nodes/custom-node` — NodeProps type, Handle component, data passing
- `https://reactflow.dev/examples/edges/animating-edges` — animateMotion SVG pattern for animated edges
- `https://reactflow.dev/examples/layout/dagre` — `@dagrejs/dagre` package, getLayoutedElements pattern
- `https://reactflow.dev/learn/customization/theming` — CSS variable names (`--xy-node-background-color-default`, etc.)
- `https://reactflow.dev/whats-new` — v12.10.1 current version (Feb 2025), React 19 + Tailwind CSS 4 UI component update (Oct 2024/2025)
- `https://reactflow.dev/api-reference/hooks/use-nodes-data` — `useNodesData` hook for targeted node subscriptions
- `https://fastapi.tiangolo.com/tutorial/server-sent-events/` — native SSE via `from fastapi.sse import EventSourceResponse`, ServerSentEvent with named events
- `https://ui.shadcn.com/docs/tailwind-v4` — Tailwind v4 support in shadcn/ui, tw-animate-css migration
- `https://ui.shadcn.com/docs/theming` — OKLCH CSS variable structure for dark mode

### Secondary (MEDIUM confidence)
- `https://www.npmjs.com/package/@dagrejs/dagre` — v3.x, actively maintained, 187 dependents (verified against React Flow docs recommendation)
- WebSearch: Zustand v5 confirmed as current stable release with `useSyncExternalStore`
- WebSearch: shadcn/ui Tailwind v4 support confirmed production-ready as of early 2026

### Tertiary (LOW confidence)
- WebSearch: Tailwind v4 OKLCH dark mode color values — cited from search summaries, verified against `ui.shadcn.com/docs/theming`
- WebSearch: Bloomberg/Palantir dark dashboard design patterns — aesthetic guidance only, no authoritative source

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — verified via official React Flow docs, FastAPI docs, npm, shadcn/ui docs
- Architecture: HIGH — patterns sourced from official React Flow state management and performance guides
- Pitfalls: HIGH — sourced directly from React Flow troubleshooting and common errors docs
- Bloomberg aesthetic CSS values: MEDIUM — based on design system conventions; no official Bloomberg CSS spec exists

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (React Flow and shadcn/ui are actively maintained; check for patch releases before planning 04-02+)
