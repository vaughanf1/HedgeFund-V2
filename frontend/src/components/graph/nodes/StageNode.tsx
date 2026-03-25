import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { cn } from '@/lib/utils'
import type { PipelineNodeData, NodeStatus } from '@/store/pipelineStore'

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

function StageNodeComponent({ data, id }: NodeProps<{ data: PipelineNodeData }>) {
  const { label, status } = data as PipelineNodeData

  // Scanner and signal_detector have no target handle (they're sources)
  const isEntry = id === 'scanner'
  // CIO has no source handle (it's the sink)
  const isSink = id === 'cio'

  return (
    <>
      {!isEntry && <Handle type="target" position={Position.Left} />}
      <div
        className={cn(
          'min-w-[148px] rounded-md border bg-zinc-900 px-3 py-2 shadow-md',
          statusBorderClass(status)
        )}
      >
        <div className="flex items-center gap-2">
          <span className={cn('h-2 w-2 rounded-full shrink-0', statusDotClass(status))} />
          <span className="text-xs font-medium text-zinc-100 truncate">{label}</span>
        </div>
      </div>
      {!isSink && <Handle type="source" position={Position.Right} />}
    </>
  )
}

export const StageNode = memo(StageNodeComponent)
