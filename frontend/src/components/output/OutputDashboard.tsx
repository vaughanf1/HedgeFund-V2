import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { usePipelineStore } from '@/store/pipelineStore'
import { useOpportunities } from '@/hooks/useOpportunities'
import { OpportunityCard } from '@/components/output/OpportunityCard'

const API_BASE = '/api/v1/opportunities'

export function OutputDashboard() {
  // Slice selector — only re-renders when outputRankings changes, not on graph
  // node/edge changes (preventing cross-panel cascade re-renders)
  const outputRankings = usePipelineStore((s) => s.outputRankings)

  // Hydrate store from REST API exactly once on mount;
  // subsequent updates arrive via SSE → handleSSEEvent → DECISION_MADE
  useOpportunities(API_BASE)

  return (
    <div className="flex h-full flex-col">
      {/* Panel header */}
      <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
        <h2 className="font-mono text-xs font-semibold uppercase tracking-widest text-zinc-400">
          Top Opportunities
        </h2>
        <Badge className="border-transparent bg-zinc-800 font-mono text-xs text-zinc-300">
          {outputRankings.length} active
        </Badge>
      </div>

      {/* Card list */}
      <ScrollArea className="flex-1">
        {outputRankings.length === 0 ? (
          /* Empty state */
          <div className="flex h-48 flex-col items-center justify-center gap-2">
            <svg
              className="h-8 w-8 text-zinc-700"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
              />
            </svg>
            <p className="text-xs text-zinc-500">No opportunities analyzed yet</p>
          </div>
        ) : (
          <div className="space-y-3 p-4">
            {outputRankings.map((opportunity) => (
              <OpportunityCard
                key={opportunity.opportunityId}
                opportunity={opportunity}
              />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  )
}
