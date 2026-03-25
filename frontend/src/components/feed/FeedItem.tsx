import { memo } from 'react'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { usePipelineStore } from '@/store/pipelineStore'
import type { FeedItem as FeedItemType } from '@/types/pipeline'

// ─── Relative timestamp helper ──────────────────────────────────────────────

function relativeTime(timestamp: number): string {
  const diffMs = Date.now() - timestamp
  const diffSec = Math.floor(diffMs / 1000)
  if (diffSec < 60) return `${diffSec}s ago`
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  return `${diffHr}h ago`
}

// ─── Color bar variants ─────────────────────────────────────────────────────

const colorBarClass: Record<FeedItemType['type'], string> = {
  detection: 'bg-blue-500',
  decision: 'bg-emerald-500',
  rejection: 'bg-red-500',
}

// ─── Component ──────────────────────────────────────────────────────────────

interface FeedItemProps {
  item: FeedItemType
}

export const FeedItem = memo(function FeedItem({ item }: FeedItemProps) {
  const setSelectedOpportunity = usePipelineStore((s) => s.setSelectedOpportunity)

  return (
    <button
      type="button"
      className="group w-full cursor-pointer text-left"
      onClick={() => setSelectedOpportunity(item.id)}
    >
      <div className="relative flex items-stretch overflow-hidden rounded-md border border-zinc-800 bg-zinc-900 transition-colors hover:border-zinc-700 hover:bg-zinc-800/60">
        {/* Left color bar */}
        <div
          className={cn(
            'w-1 shrink-0 rounded-l-md',
            colorBarClass[item.type]
          )}
        />

        {/* Content */}
        <div className="flex flex-1 flex-col gap-0.5 px-3 py-2">
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono text-sm font-bold text-zinc-100">
              {item.ticker}
            </span>
            <div className="flex items-center gap-1.5">
              {item.convictionScore !== undefined && (
                <Badge variant="running" className="px-1.5 py-0 text-xs">
                  {item.convictionScore}
                </Badge>
              )}
              <span className="text-xs text-zinc-600">{relativeTime(item.timestamp)}</span>
            </div>
          </div>

          <p className="text-xs text-zinc-400 leading-snug">{item.headline}</p>

          {item.type === 'rejection' && item.rejectionReason && (
            <p className="text-xs text-red-400 leading-snug">{item.rejectionReason}</p>
          )}
        </div>
      </div>
    </button>
  )
})
