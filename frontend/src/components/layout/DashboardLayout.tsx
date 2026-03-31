import { PipelineGraph } from '@/components/graph/PipelineGraph'
import { OpportunityFeed } from '@/components/feed/OpportunityFeed'
import { OutputDashboard } from '@/components/output/OutputDashboard'
import { useSSEStore, type SSEStatus } from '@/hooks/usePipelineSSE'

const STATUS_DISPLAY: Record<SSEStatus, { dot: string; text: string; label: string }> = {
  connected:    { dot: 'bg-emerald-500 animate-pulse', text: 'text-emerald-500', label: 'CONNECTED' },
  connecting:   { dot: 'bg-yellow-500 animate-pulse',  text: 'text-yellow-500',  label: 'CONNECTING' },
  disconnected: { dot: 'bg-zinc-600',                  text: 'text-zinc-600',     label: 'DISCONNECTED' },
}

export function DashboardLayout() {
  const sseStatus = useSSEStore((s) => s.status)
  const { dot, text, label } = STATUS_DISPLAY[sseStatus]

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
          <span className={`h-2 w-2 rounded-full ${dot}`} title={`SSE ${label.toLowerCase()}`} />
          <span className={`font-mono text-[10px] ${text}`}>{label}</span>
        </div>
      </header>

      {/* Three-panel grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1fr) 320px 380px',
          overflow: 'hidden',
          height: '100%',
        }}
      >
        {/* Left: Pipeline Graph — needs explicit w/h for React Flow */}
        <div className="relative border-r border-zinc-800" style={{ width: '100%', height: '100%' }}>
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
