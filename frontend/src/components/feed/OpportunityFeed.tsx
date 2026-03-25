import { ScrollArea } from '@/components/ui/scroll-area'

export function OpportunityFeed() {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-zinc-800 px-4 py-3">
        <h2 className="font-mono text-xs font-semibold uppercase tracking-widest text-zinc-400">
          Live Feed
        </h2>
      </div>
      <ScrollArea className="flex-1">
        <div className="flex h-32 items-center justify-center">
          <p className="text-xs text-zinc-600">Waiting for events…</p>
        </div>
      </ScrollArea>
    </div>
  )
}
