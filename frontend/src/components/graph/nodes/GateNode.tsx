import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { ShieldCheck } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import type { PipelineNodeData, NodeStatus } from '@/store/pipelineStore'

function statusBorderClass(status: NodeStatus): string {
  switch (status) {
    case 'running': return 'border-blue-500'
    case 'complete': return 'border-emerald-500'
    case 'error': return 'border-red-500'
    default: return 'border-amber-600'
  }
}

function statusBadgeVariant(status: NodeStatus): 'default' | 'running' | 'success' | 'destructive' | 'warning' {
  switch (status) {
    case 'running': return 'running'
    case 'complete': return 'success'
    case 'error': return 'destructive'
    default: return 'warning'
  }
}

function GateNodeComponent({ data }: NodeProps<{ data: PipelineNodeData }>) {
  const { label, status } = data as PipelineNodeData
  const isRunning = status === 'running'

  return (
    <>
      <Handle type="target" position={Position.Left} />
      <div
        className={cn(
          'min-w-[160px] rounded-md border-2 bg-zinc-900 px-3 py-2 shadow-md',
          statusBorderClass(status),
          isRunning && 'animate-pulse'
        )}
        style={{ clipPath: 'polygon(8px 0%, calc(100% - 8px) 0%, 100% 8px, 100% calc(100% - 8px), calc(100% - 8px) 100%, 8px 100%, 0% calc(100% - 8px), 0% 8px)' }}
      >
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5">
            <ShieldCheck className="h-3 w-3 text-amber-500 shrink-0" />
            <span className="text-xs font-medium text-zinc-100 truncate">{label}</span>
          </div>
          <Badge variant={statusBadgeVariant(status)} className="shrink-0 text-[10px] px-1.5 py-0">
            {status}
          </Badge>
        </div>
      </div>
      <Handle type="source" position={Position.Right} />
    </>
  )
}

export const GateNode = memo(GateNodeComponent)
