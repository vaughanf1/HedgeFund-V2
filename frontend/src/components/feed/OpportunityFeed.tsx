import { usePipelineStore } from '@/store/pipelineStore'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { FeedItem } from '@/components/feed/FeedItem'
import { OpportunitySheet } from '@/components/inspect/OpportunitySheet'
import type { FeedItem as FeedItemType } from '@/types/pipeline'

// ─── Section header ──────────────────────────────────────────────────────────

function SectionHeader({ title, className }: { title: string; className?: string }) {
  return (
    <div className={`px-3 pt-3 pb-1 ${className ?? ''}`}>
      <span className="font-mono text-[10px] font-semibold uppercase tracking-widest text-zinc-500">
        {title}
      </span>
    </div>
  )
}

// ─── OpportunityFeed ─────────────────────────────────────────────────────────

export function OpportunityFeed() {
  // Slice selectors — each selector subscribes only to its slice to prevent
  // re-renders when unrelated store state (e.g. node positions) changes.
  const feedItems = usePipelineStore((s) => s.feedItems)

  // Derived sections
  const highestConviction: FeedItemType[] = feedItems
    .filter((i) => i.type === 'decision' && i.convictionScore !== undefined)
    .sort((a, b) => (b.convictionScore ?? 0) - (a.convictionScore ?? 0))
    .slice(0, 3)

  const recentActivity: FeedItemType[] = feedItems.slice(0, 20)

  const recentlyRejected: FeedItemType[] = feedItems
    .filter((i) => i.type === 'rejection')
    .slice(0, 5)

  return (
    <>
      {/* The Sheet is rendered here so it stays mounted outside the scroll area */}
      <OpportunitySheet />

      <div className="flex h-full flex-col overflow-hidden">
        {/* Panel header */}
        <div className="flex shrink-0 items-center gap-2 border-b border-zinc-800 px-4 py-3">
          {/* SSE pulse dot */}
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
          </span>
          <h2 className="font-mono text-xs font-semibold uppercase tracking-widest text-zinc-400">
            Opportunity Feed
          </h2>
        </div>

        <ScrollArea className="flex-1">
          <div className="pb-4">
            {/* ── Highest Conviction ────────────────────────────────────── */}
            <SectionHeader title="Highest Conviction" />
            {highestConviction.length === 0 ? (
              <div className="px-3 py-2">
                <p className="text-xs text-zinc-600">No approved opportunities yet</p>
              </div>
            ) : (
              <div className="flex flex-col gap-1.5 px-3 pb-1">
                {highestConviction.map((item) => (
                  <FeedItem key={item.id} item={item} />
                ))}
              </div>
            )}

            <Separator className="my-2" />

            {/* ── Live Feed ────────────────────────────────────────────── */}
            <SectionHeader title="Live Feed" />
            {recentActivity.length === 0 ? (
              <div className="flex h-24 items-center justify-center px-3">
                <p className="text-xs text-zinc-600">Waiting for events…</p>
              </div>
            ) : (
              <div className="flex flex-col gap-1.5 px-3 pb-1">
                {recentActivity.map((item) => (
                  <FeedItem key={item.id} item={item} />
                ))}
              </div>
            )}

            <Separator className="my-2" />

            {/* ── Recently Rejected ────────────────────────────────────── */}
            <SectionHeader title="Rejected" className="text-red-400" />
            {recentlyRejected.length === 0 ? (
              <div className="px-3 py-2">
                <p className="text-xs text-zinc-600">None</p>
              </div>
            ) : (
              <div className="flex flex-col gap-1.5 px-3">
                {recentlyRejected.map((item) => (
                  <FeedItem key={item.id} item={item} />
                ))}
              </div>
            )}
          </div>
        </ScrollArea>
      </div>
    </>
  )
}
