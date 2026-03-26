import { memo } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { AgentBreakdown } from '@/components/output/AgentBreakdown'
import type { Opportunity } from '@/types/pipeline'

// ─── Verdict helpers ────────────────────────────────────────────────────────

type VerdictStyle = {
  badgeClass: string
  borderClass: string
}

function getVerdictStyle(verdict: string): VerdictStyle {
  switch (verdict.toUpperCase()) {
    case 'BUY':
    case 'INVEST':
      return {
        badgeClass: 'border-transparent bg-emerald-900/60 text-emerald-300',
        borderClass: 'border-l-emerald-500',
      }
    case 'SELL':
      return {
        badgeClass: 'border-transparent bg-red-900/60 text-red-300',
        borderClass: 'border-l-red-500',
      }
    case 'HOLD':
      return {
        badgeClass: 'border-transparent bg-yellow-900/60 text-yellow-300',
        borderClass: 'border-l-yellow-500',
      }
    case 'MONITOR':
      return {
        badgeClass: 'border-transparent bg-blue-900/60 text-blue-300',
        borderClass: 'border-l-blue-500',
      }
    case 'PASS':
    default:
      return {
        badgeClass: 'border-transparent bg-zinc-800 text-zinc-400',
        borderClass: 'border-l-zinc-600',
      }
  }
}

// ─── Risk badge helpers ─────────────────────────────────────────────────────

function getRiskBadgeClass(risk: string): string {
  switch (risk.toUpperCase()) {
    case 'LOW':
      return 'border-transparent bg-emerald-900/40 text-emerald-400'
    case 'MEDIUM':
      return 'border-transparent bg-yellow-900/40 text-yellow-400'
    case 'HIGH':
      return 'border-transparent bg-red-900/40 text-red-400'
    default:
      return 'border-transparent bg-zinc-800 text-zinc-500'
  }
}

// ─── Component ──────────────────────────────────────────────────────────────

interface OpportunityCardProps {
  opportunity: Opportunity
}

export const OpportunityCard = memo(function OpportunityCard({
  opportunity,
}: OpportunityCardProps) {
  const {
    ticker,
    finalVerdict,
    riskRating,
    convictionScore,
    suggestedAllocationPct,
    timeHorizon,
    expectedUpside,
    keyCatalysts,
    agentScores,
    cioSummary,
  } = opportunity

  const { badgeClass, borderClass } = getVerdictStyle(finalVerdict)
  const riskBadgeClass = getRiskBadgeClass(riskRating)

  // Display conviction as integer percentage-style (e.g. "78" not "0.78")
  const convictionDisplay =
    convictionScore > 1 ? Math.round(convictionScore) : Math.round(convictionScore * 100)

  const allocationDisplay =
    suggestedAllocationPct > 1
      ? `${suggestedAllocationPct.toFixed(1)}%`
      : `${(suggestedAllocationPct * 100).toFixed(1)}%`

  return (
    <Card
      className={`border-l-2 bg-zinc-900 ${borderClass} border-zinc-800`}
    >
      <CardContent className="space-y-3 p-4">
        {/* Header row */}
        <div className="flex items-center gap-2">
          <span className="font-mono text-lg font-bold text-white">{ticker}</span>
          <Badge className={badgeClass}>{finalVerdict}</Badge>
          <Badge className={riskBadgeClass}>{riskRating}</Badge>
        </div>

        {/* Conviction score */}
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-3xl font-bold text-blue-400">
            {convictionDisplay}
          </span>
          <span className="text-sm text-zinc-400">conviction</span>
        </div>

        {/* Key metrics row */}
        <div className="grid grid-cols-3 gap-2 text-xs text-zinc-400">
          <div>
            <div className="text-zinc-600">allocation</div>
            <div className="font-mono font-medium text-zinc-300">{allocationDisplay}</div>
          </div>
          <div>
            <div className="text-zinc-600">horizon</div>
            <div className="font-mono font-medium text-zinc-300">
              {timeHorizon ?? '—'}
            </div>
          </div>
          <div>
            <div className="text-zinc-600">upside</div>
            <div className="font-mono font-medium text-zinc-300">
              {expectedUpside != null ? `${expectedUpside}%` : '—'}
            </div>
          </div>
        </div>

        {/* Key catalysts */}
        {keyCatalysts && keyCatalysts.length > 0 && (
          <div className="space-y-0.5">
            {keyCatalysts.map((catalyst, i) => (
              <div key={i} className="flex items-start gap-1.5 text-xs text-zinc-300">
                <span className="mt-0.5 text-blue-400">*</span>
                <span>{catalyst}</span>
              </div>
            ))}
          </div>
        )}

        {/* Agent breakdown */}
        <div className="space-y-1">
          <div className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
            Agent Analysis
          </div>
          {agentScores.length > 0 ? (
            <div className="space-y-0.5">
              {agentScores.map((score) => (
                <AgentBreakdown key={score.persona} score={score} />
              ))}
            </div>
          ) : (
            <div className="text-xs text-zinc-600">Awaiting agent analysis...</div>
          )}
        </div>

        {/* CIO summary */}
        {cioSummary && (
          <div className="rounded-md bg-zinc-800 px-3 py-2">
            <span className="mr-2 font-mono text-xs font-semibold text-blue-400">CIO</span>
            <span className="text-xs text-zinc-300">{cioSummary}</span>
          </div>
        )}
      </CardContent>
    </Card>
  )
})
