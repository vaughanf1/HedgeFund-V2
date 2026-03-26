import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { usePipelineStore } from '@/store/pipelineStore'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { AgentVerdictPanel } from '@/components/inspect/AgentVerdictPanel'
import type { AgentScore } from '@/types/pipeline'

// ─── API response types ──────────────────────────────────────────────────────

interface OpportunityDetail {
  opportunity_id: string
  decision: Record<string, unknown>
  verdicts: Record<string, unknown>[]
}

// ─── Verdict badge variant ───────────────────────────────────────────────────

function verdictBadgeVariant(verdict: string): 'success' | 'destructive' | 'warning' | 'running' | 'default' {
  switch (verdict.toUpperCase()) {
    case 'BUY':
    case 'INVEST':  return 'success'
    case 'SELL':
    case 'PASS':    return 'destructive'
    case 'HOLD':    return 'warning'
    case 'MONITOR': return 'running'
    default:        return 'default'
  }
}

// ─── Risk rating badge ───────────────────────────────────────────────────────

function riskBadgeVariant(risk: string): 'success' | 'destructive' | 'warning' | 'default' {
  switch (risk.toUpperCase()) {
    case 'LOW':    return 'success'
    case 'HIGH':   return 'destructive'
    case 'MEDIUM': return 'warning'
    default:       return 'default'
  }
}

// ─── Map raw verdict dict to AgentScore ─────────────────────────────────────

function toAgentScore(raw: Record<string, unknown>): AgentScore {
  return {
    persona: (raw['persona'] as string | undefined) ?? 'Unknown',
    verdict: (raw['verdict'] as string | undefined) ?? 'UNKNOWN',
    confidence: Number(raw['confidence'] ?? raw['confidence_score'] ?? 0),
    rationale: (raw['rationale'] as string | undefined) ?? (raw['reasoning'] as string | undefined),
    risks: Array.isArray(raw['risks']) ? (raw['risks'] as string[]) : undefined,
    upsideScenario: (raw['upside_scenario'] as string | undefined),
    timeHorizon: (raw['time_horizon'] as string | undefined),
  }
}

// ─── OpportunitySheet ────────────────────────────────────────────────────────

export function OpportunitySheet() {
  const selectedOpportunityId = usePipelineStore((s) => s.selectedOpportunityId)
  const setSelectedOpportunity = usePipelineStore((s) => s.setSelectedOpportunity)

  const [detail, setDetail] = useState<OpportunityDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [notFound, setNotFound] = useState(false)

  const isOpen = selectedOpportunityId !== null

  useEffect(() => {
    if (!selectedOpportunityId) {
      setDetail(null)
      setNotFound(false)
      return
    }

    let cancelled = false
    setLoading(true)
    setNotFound(false)
    setDetail(null)

    fetch(`/api/v1/opportunities/${selectedOpportunityId}`)
      .then(async (res) => {
        if (res.status === 404) {
          if (!cancelled) setNotFound(true)
          return
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const json = await res.json() as OpportunityDetail
        if (!cancelled) setDetail(json)
      })
      .catch(() => {
        if (!cancelled) setNotFound(true)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [selectedOpportunityId])

  // Derived values from decision blob
  const decision = detail?.decision ?? {}
  // Extract ticker from decision or from compound opportunity_id (ticker:detected_at)
  const rawId = selectedOpportunityId ?? ''
  const extractedTicker = rawId.includes(':') ? rawId.split(':', 1)[0] : rawId
  const ticker = (decision['ticker'] as string | undefined) ?? (extractedTicker || '—')
  const finalVerdict = (decision['final_verdict'] as string | undefined) ?? '—'
  const convictionScore = Number(decision['conviction_score'] ?? 0)
  const allocationPct = Number(decision['suggested_allocation_pct'] ?? 0)
  const riskRating = (decision['risk_rating'] as string | undefined) ?? 'UNKNOWN'
  const timeHorizon = (decision['time_horizon'] as string | undefined)
  const keyCatalysts = Array.isArray(decision['key_catalysts'])
    ? (decision['key_catalysts'] as string[])
    : undefined
  const killConditions = Array.isArray(decision['kill_conditions'])
    ? (decision['kill_conditions'] as string[])
    : undefined
  const cioSummary = (decision['cio_summary'] as string | undefined) ?? (decision['summary'] as string | undefined)

  const agentScores: AgentScore[] = (detail?.verdicts ?? []).map(toAgentScore)

  return (
    <Sheet
      open={isOpen}
      onOpenChange={(open) => { if (!open) setSelectedOpportunity(null) }}
    >
      <SheetContent side="right" className="flex w-full flex-col p-0 sm:max-w-lg">
        {/* Header */}
        <SheetHeader className="shrink-0 border-b border-zinc-800 px-6 py-4">
          <div className="flex items-center gap-3">
            <SheetTitle className="font-mono text-2xl font-bold text-zinc-100">
              {ticker}
            </SheetTitle>
            {finalVerdict !== '—' && (
              <Badge variant={verdictBadgeVariant(finalVerdict)} className="text-sm">
                {finalVerdict}
              </Badge>
            )}
          </div>
          <SheetDescription>
            Opportunity analysis breakdown
          </SheetDescription>
        </SheetHeader>

        {/* Body */}
        <ScrollArea className="flex-1">
          <div className="px-6 py-4 space-y-6">
            {loading && (
              <div className="flex h-40 items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-zinc-500" />
              </div>
            )}

            {notFound && !loading && (
              <div className="flex h-40 items-center justify-center">
                <p className="text-sm text-zinc-500">Opportunity not found.</p>
              </div>
            )}

            {detail && !loading && (
              <>
                {/* ── CIO Decision ─────────────────────────────────── */}
                <section>
                  <p className="mb-3 font-mono text-[10px] uppercase tracking-widest text-zinc-500">
                    CIO Decision
                  </p>

                  <div className="grid grid-cols-3 gap-3">
                    <div className="rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-3 text-center">
                      <p className="font-mono text-2xl font-bold text-zinc-100">{convictionScore}</p>
                      <p className="mt-0.5 text-[10px] text-zinc-500 uppercase tracking-wider">Conviction</p>
                    </div>
                    <div className="rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-3 text-center">
                      <p className="font-mono text-2xl font-bold text-zinc-100">{allocationPct.toFixed(1)}%</p>
                      <p className="mt-0.5 text-[10px] text-zinc-500 uppercase tracking-wider">Allocation</p>
                    </div>
                    <div className="rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-3 text-center">
                      <Badge variant={riskBadgeVariant(riskRating)} className="text-xs">
                        {riskRating}
                      </Badge>
                      <p className="mt-1 text-[10px] text-zinc-500 uppercase tracking-wider">Risk</p>
                    </div>
                  </div>

                  {timeHorizon && (
                    <div className="mt-3 flex items-center gap-2">
                      <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">Horizon</span>
                      <span className="text-xs text-zinc-300">{timeHorizon}</span>
                    </div>
                  )}

                  {cioSummary && (
                    <p className="mt-3 text-xs text-zinc-300 leading-relaxed">{cioSummary}</p>
                  )}

                  {keyCatalysts && keyCatalysts.length > 0 && (
                    <div className="mt-3">
                      <p className="mb-1.5 font-mono text-[10px] uppercase tracking-wider text-zinc-500">Key Catalysts</p>
                      <ul className="space-y-1">
                        {keyCatalysts.map((catalyst, i) => (
                          <li key={i} className="flex gap-1.5 text-xs text-zinc-300">
                            <span className="mt-0.5 shrink-0 text-emerald-500">•</span>
                            <span>{catalyst}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </section>

                {killConditions && killConditions.length > 0 && (
                  <>
                    <Separator />
                    <section>
                      <p className="mb-3 font-mono text-[10px] uppercase tracking-widest text-zinc-500">Kill Conditions</p>
                      <div className="rounded-lg border border-red-900/50 bg-red-950/20 px-4 py-3">
                        <ul className="space-y-1.5">
                          {killConditions.map((condition, i) => (
                            <li key={i} className="flex gap-1.5 text-xs text-red-400">
                              <span className="mt-0.5 shrink-0">⚠</span>
                              <span>{condition}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    </section>
                  </>
                )}

                {agentScores.length > 0 && (
                  <>
                    <Separator />
                    <section>
                      <p className="mb-3 font-mono text-[10px] uppercase tracking-widest text-zinc-500">
                        Agent Breakdown
                      </p>
                      <div className="space-y-2">
                        {agentScores.map((agent) => (
                          <AgentVerdictPanel key={agent.persona} agent={agent} />
                        ))}
                      </div>
                    </section>
                  </>
                )}
              </>
            )}
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  )
}
