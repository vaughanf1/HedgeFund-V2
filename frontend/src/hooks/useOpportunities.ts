import { useEffect } from 'react'
import type { Opportunity, AgentScore } from '@/types/pipeline'
import { usePipelineStore } from '@/store/pipelineStore'

// ─── API response shapes ────────────────────────────────────────────────────

interface ApiOpportunitySummary {
  opportunity_id: string
  conviction_score: number
  suggested_allocation_pct: number
  final_verdict: string
  risk_rating: string
  decided_at: string
}

interface ApiVerdict {
  persona?: string
  verdict?: string
  confidence?: number
  confidence_score?: number
  rationale?: string
  time_horizon?: string
  upside_scenario?: string
}

interface ApiDecision {
  ticker?: string
  final_verdict?: string
  conviction_score?: number
  suggested_allocation_pct?: number
  risk_rating?: string
  decided_at?: string
  summary?: string
  key_catalysts?: string[]
  time_horizon?: string
  expected_upside?: number
  rejection_reason?: string
}

interface ApiOpportunityDetail {
  opportunity_id: string
  decision: ApiDecision
  verdicts: ApiVerdict[]
}

// ─── Mapping helpers ────────────────────────────────────────────────────────

function mapAgentScore(v: ApiVerdict): AgentScore {
  return {
    persona: v.persona ?? '',
    verdict: v.verdict ?? '',
    confidence: Number(v.confidence ?? v.confidence_score ?? 0),
    rationale: v.rationale,
    timeHorizon: v.time_horizon,
    upsideScenario: v.upside_scenario,
  }
}

function mapToOpportunity(
  summary: ApiOpportunitySummary,
  detail: ApiOpportunityDetail
): Opportunity {
  const d = detail.decision
  return {
    opportunityId: summary.opportunity_id,
    ticker: d.ticker ?? summary.opportunity_id,
    convictionScore: summary.conviction_score,
    suggestedAllocationPct: summary.suggested_allocation_pct,
    finalVerdict: summary.final_verdict,
    riskRating: summary.risk_rating,
    decidedAt: summary.decided_at,
    agentScores: detail.verdicts.map(mapAgentScore),
    cioSummary: d.summary,
    keyCatalysts: d.key_catalysts,
    timeHorizon: d.time_horizon,
    expectedUpside: d.expected_upside,
  }
}

// ─── Stand-alone async fetch (not a store action) ───────────────────────────

export async function fetchOpportunityDetail(
  baseUrl: string,
  id: string
): Promise<ApiOpportunityDetail> {
  const res = await fetch(`${baseUrl}/${id}`)
  if (!res.ok) {
    throw new Error(`fetchOpportunityDetail: ${res.status} for id=${id}`)
  }
  return res.json() as Promise<ApiOpportunityDetail>
}

// ─── Hook ───────────────────────────────────────────────────────────────────

/**
 * Fetches the top 10 opportunities from the REST API on mount and hydrates
 * the Zustand output rankings. Subsequent updates arrive via SSE.
 *
 * Call this exactly once — in OutputDashboard or App.
 */
export function useOpportunities(baseUrl: string) {
  const setOutputRankings = usePipelineStore((s) => s.setOutputRankings)

  useEffect(() => {
    let cancelled = false

    async function hydrate() {
      try {
        const summaryRes = await fetch(`${baseUrl}?limit=10`)
        if (!summaryRes.ok) {
          console.warn(
            `[useOpportunities] GET ${baseUrl}?limit=10 returned ${summaryRes.status} — backend may not be running`
          )
          return
        }

        const summaries = (await summaryRes.json()) as ApiOpportunitySummary[]
        if (cancelled) return

        const details = await Promise.allSettled(
          summaries.map((s) => fetchOpportunityDetail(baseUrl, s.opportunity_id))
        )
        if (cancelled) return

        const opportunities: Opportunity[] = []
        details.forEach((result, i) => {
          if (result.status === 'fulfilled') {
            opportunities.push(mapToOpportunity(summaries[i], result.value))
          } else {
            console.warn('[useOpportunities] Failed to fetch detail:', result.reason)
          }
        })

        setOutputRankings(opportunities)
      } catch (err) {
        console.warn('[useOpportunities] Hydration failed (backend may be offline):', err)
      }
    }

    void hydrate()
    return () => {
      cancelled = true
    }
  }, [baseUrl, setOutputRankings])
}
