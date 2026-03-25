import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import type { PipelineNodeData, NodeStatus } from '@/store/pipelineStore'

function statusBorderClass(status: NodeStatus): string {
  switch (status) {
    case 'running': return 'border-blue-500'
    case 'complete': return 'border-emerald-500'
    case 'error': return 'border-red-500'
    default: return 'border-zinc-700'
  }
}

function statusDotClass(status: NodeStatus): string {
  switch (status) {
    case 'running': return 'bg-blue-500 animate-pulse'
    case 'complete': return 'bg-emerald-500'
    case 'error': return 'bg-red-500'
    default: return 'bg-zinc-500'
  }
}

function statusBadgeVariant(status: NodeStatus): 'default' | 'running' | 'success' | 'destructive' {
  switch (status) {
    case 'running': return 'running'
    case 'complete': return 'success'
    case 'error': return 'destructive'
    default: return 'default'
  }
}

function AgentNodeComponent({ data }: NodeProps<{ data: PipelineNodeData }>) {
  const { label, status, lastResult } = data as PipelineNodeData
  const isRunning = status === 'running'
  const isComplete = status === 'complete'

  return (
    <>
      <Handle type="target" position={Position.Left} className="!bg-blue-500 !w-2 !h-2" />
      <div
        className={cn(
          'min-w-[160px] rounded-md border bg-zinc-900 px-3 py-2 shadow-md',
          'transition-all duration-500 ease-in-out',
          statusBorderClass(status),
          isRunning && 'shadow-[0_0_12px_rgba(10,132,255,0.3)]'
        )}
      >
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 min-w-0">
            <span className={cn('h-2 w-2 rounded-full shrink-0', statusDotClass(status))} />
            <span className="text-xs font-medium text-zinc-100 truncate">{label}</span>
          </div>
          <Badge variant={statusBadgeVariant(status)} className="shrink-0 text-[10px] px-1.5 py-0">
            {status}
          </Badge>
        </div>
        {isRunning && (
          <p className="mt-1 text-[10px] text-blue-400 animate-pulse">Analyzing...</p>
        )}
        {isComplete && lastResult && (
          <p className="mt-1 text-[10px] text-zinc-400 truncate">{lastResult}</p>
        )}
      </div>
      <Handle type="source" position={Position.Right} className="!bg-blue-500 !w-2 !h-2" />
    </>
  )
}

export const AgentNode = memo(AgentNodeComponent)
