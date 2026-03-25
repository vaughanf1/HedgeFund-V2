// ─── Pipeline TypeScript Interfaces ─────────────────────────────────────────
// Shared types for the live feed, opportunity inspection, and pipeline graph.

export type NodeStatus = 'idle' | 'running' | 'complete' | 'error'

export interface PipelineNodeData extends Record<string, unknown> {
  label: string
  status: NodeStatus
  type: string
  lastResult?: string
}

export type FeedItemType = 'detection' | 'decision' | 'rejection'

export interface FeedItem {
  id: string
  type: FeedItemType
  ticker: string
  headline: string
  convictionScore?: number
  riskRating?: string
  finalVerdict?: string
  rejectionReason?: string
  timestamp: number
}

export interface AgentScore {
  persona: string
  verdict: string
  confidence: number
  rationale?: string
  risks?: string[]
  upsideScenario?: string
  timeHorizon?: string
}

export interface Opportunity {
  opportunityId: string
  ticker: string
  convictionScore: number
  riskRating: string
  suggestedAllocationPct: number
  finalVerdict: string
  expectedUpside?: string
  timeHorizon?: string
  keyCatalysts?: string[]
  agentScores: AgentScore[]
  cioSummary?: string
  decidedAt: string
}
