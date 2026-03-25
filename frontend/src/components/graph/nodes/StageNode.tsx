import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { cn } from '@/lib/utils'
import type { PipelineNodeData, NodeStatus } from '@/store/pipelineStore'

interface StageNodeData extends PipelineNodeData {
  lastScanTime?: string
  consensus?: string
  consensusPct?: number
}

function statusDotClass(status: NodeStatus): string {
  switch (status) {
    case 'running': return 'bg-blue-500 animate-pulse'
    case 'complete': return 'bg-emerald-500'
    case 'error': return 'bg-red-500'
    default: return 'bg-zinc-600'
  }
}

function statusBorderClass(status: NodeStatus): string {
  switch (status) {
    case 'running': return 'border-blue-500/50'
    case 'complete': return 'border-emerald-500/50'
    case 'error': return 'border-red-500/50'
    default: return 'border-zinc-700'
  }
}

function StageNodeComponent({ data, id }: NodeProps<{ data: StageNodeData }>) {
  const { label, status, lastResult, lastScanTime, consensus, consensusPct, conviction } = data as StageNodeData

  // Scanner and signal_detector have no target handle (they're sources)
  const isEntry = id === 'scanner'
  // CIO has no source handle (it's the sink)
  const isSink = id === 'cio'

  const isRunning = status === 'running'
  const isComplete = status === 'complete'

  // Contextual sub-line for specific stage nodes
  function renderSubInfo(): React.ReactNode {
    if (isRunning) {
      return <p className="mt-1 text-[10px] text-blue-400 animate-pulse">Processing...</p>
    }
    if (!isComplete) return null

    if (id === 'scanner' && lastScanTime) {
      return <p className="mt-1 text-[10px] text-zinc-400 truncate">Last scan: {lastScanTime}</p>
    }
    if (id === 'committee' && consensus) {
      const pct = consensusPct != null ? ` ${consensusPct}%` : ''
      return <p className="mt-1 text-[10px] text-zinc-400 truncate">{consensus} consensus{pct}</p>
    }
    if (id === 'cio' && lastResult) {
      const convStr = conviction != null ? ` | ${conviction} conviction` : ''
      return <p className="mt-1 text-[10px] text-zinc-400 truncate">{lastResult}{convStr}</p>
    }
    return null
  }

  return (
    <>
      {!isEntry && <Handle type="target" position={Position.Left} className="!bg-blue-500 !w-2 !h-2" />}
      <div
        className={cn(
          'min-w-[148px] rounded-md border bg-zinc-900 px-3 py-2 shadow-md',
          'transition-all duration-500 ease-in-out',
          statusBorderClass(status),
          isRunning && 'shadow-[0_0_8px_rgba(10,132,255,0.2)]'
        )}
      >
        <div className="flex items-center gap-2">
          <span className={cn('h-2 w-2 rounded-full shrink-0', statusDotClass(status))} />
          <span className="text-xs font-medium text-zinc-100 truncate">{label}</span>
        </div>
        {renderSubInfo()}
      </div>
      {!isSink && <Handle type="source" position={Position.Right} className="!bg-blue-500 !w-2 !h-2" />}
    </>
  )
}

export const StageNode = memo(StageNodeComponent)
