import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import type { PipelineNodeData, NodeStatus } from '@/store/pipelineStore'

interface GateNodeData extends PipelineNodeData {
  passCount?: number
  totalCount?: number
}

function statusBorderClass(status: NodeStatus): string {
  switch (status) {
    case 'running': return 'border-yellow-500'
    case 'complete': return 'border-emerald-500'
    case 'error': return 'border-red-500'
    default: return 'border-amber-600'
  }
}

function statusDotClass(status: NodeStatus): string {
  switch (status) {
    case 'running': return 'bg-yellow-500 animate-pulse'
    case 'complete': return 'bg-emerald-500'
    case 'error': return 'bg-red-500'
    default: return 'bg-amber-600'
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

// Simple inline filter SVG icon
function FilterIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="currentColor"
      className={className}
      aria-hidden="true"
    >
      <path d="M1.5 2h13l-5 6v5l-3-1.5V8L1.5 2z" />
    </svg>
  )
}

function GateNodeComponent({ data }: NodeProps<{ data: GateNodeData }>) {
  const { label, status, passCount, totalCount } = data as GateNodeData
  const isRunning = status === 'running'
  const isComplete = status === 'complete'

  return (
    <>
      <Handle type="target" position={Position.Left} className="!bg-blue-500 !w-2 !h-2" />
      <div
        className={cn(
          'min-w-[160px] rounded-md border-2 bg-zinc-900 px-3 py-2 shadow-md',
          'transition-all duration-500 ease-in-out',
          statusBorderClass(status),
          isRunning && 'shadow-[0_0_12px_rgba(234,179,8,0.25)]'
        )}
        style={{ clipPath: 'polygon(8px 0%, calc(100% - 8px) 0%, 100% 8px, 100% calc(100% - 8px), calc(100% - 8px) 100%, 8px 100%, 0% calc(100% - 8px), 0% 8px)' }}
      >
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 min-w-0">
            <span className={cn('h-2 w-2 rounded-full shrink-0', statusDotClass(status))} />
            <FilterIcon className="h-3 w-3 text-amber-500 shrink-0" />
            <span className="text-xs font-medium text-zinc-100 truncate">{label}</span>
          </div>
          <Badge variant={statusBadgeVariant(status)} className="shrink-0 text-[10px] px-1.5 py-0">
            {status}
          </Badge>
        </div>
        {isRunning && (
          <p className="mt-1 text-[10px] text-yellow-400 animate-pulse">Filtering...</p>
        )}
        {isComplete && passCount != null && totalCount != null && (
          <p className="mt-1 text-[10px] text-zinc-400">
            {passCount} passed / {totalCount} total
          </p>
        )}
      </div>
      <Handle type="source" position={Position.Right} className="!bg-blue-500 !w-2 !h-2" />
    </>
  )
}

export const GateNode = memo(GateNodeComponent)
