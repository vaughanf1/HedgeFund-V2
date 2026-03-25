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

  return (
    <>
      <Handle type="target" position={Position.Left} />
      <div
        className={cn(
          'min-w-[160px] rounded-md border bg-zinc-900 px-3 py-2 shadow-md',
          statusBorderClass(status),
          isRunning && 'animate-pulse'
        )}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-medium text-zinc-100 truncate">{label}</span>
          <Badge variant={statusBadgeVariant(status)} className="shrink-0 text-[10px] px-1.5 py-0">
            {status}
          </Badge>
        </div>
        {lastResult && (
          <p className="mt-1 text-[10px] text-zinc-500 truncate">{lastResult}</p>
        )}
      </div>
      <Handle type="source" position={Position.Right} />
    </>
  )
}

export const AgentNode = memo(AgentNodeComponent)
