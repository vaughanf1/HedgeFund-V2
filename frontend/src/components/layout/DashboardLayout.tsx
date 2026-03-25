import { PipelineGraph } from '@/components/graph/PipelineGraph'
import { OpportunityFeed } from '@/components/feed/OpportunityFeed'
import { OutputDashboard } from '@/components/output/OutputDashboard'

export function DashboardLayout() {
  return (
    <div
      style={{ height: '100dvh', display: 'grid', gridTemplateRows: 'auto 1fr', gridTemplateColumns: '1fr' }}
    >
      {/* Header bar */}
      <header className="flex items-center justify-between border-b border-zinc-800 bg-zinc-950 px-4 py-2">
        <span className="font-mono text-xs font-semibold tracking-widest text-zinc-400">
          HEDGEFUND V2 — ALPHA DISCOVERY ENGINE
        </span>
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-zinc-600" title="SSE disconnected" />
          <span className="font-mono text-[10px] text-zinc-600">DISCONNECTED</span>
        </div>
      </header>

      {/* Three-panel grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 320px 380px',
          overflow: 'hidden',
          height: '100%',
        }}
      >
        {/* Left: Pipeline Graph */}
        <div className="relative overflow-hidden border-r border-zinc-800">
          <PipelineGraph />
        </div>

        {/* Middle: Opportunity Feed */}
        <div className="overflow-hidden border-r border-zinc-800">
          <OpportunityFeed />
        </div>

        {/* Right: Output Dashboard */}
        <div className="overflow-hidden">
          <OutputDashboard />
        </div>
      </div>
    </div>
  )
}
