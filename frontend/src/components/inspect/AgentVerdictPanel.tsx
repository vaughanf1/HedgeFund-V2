import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import type { AgentScore } from '@/types/pipeline'

// ─── Persona colour map ──────────────────────────────────────────────────────

const PERSONA_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  buffett: { bg: 'bg-amber-500', text: 'text-amber-500', border: 'border-amber-800' },
  munger:  { bg: 'bg-violet-500', text: 'text-violet-500', border: 'border-violet-800' },
  ackman:  { bg: 'bg-cyan-500', text: 'text-cyan-500', border: 'border-cyan-800' },
  cohen:   { bg: 'bg-pink-500', text: 'text-pink-500', border: 'border-pink-800' },
  dalio:   { bg: 'bg-sky-500', text: 'text-sky-500', border: 'border-sky-800' },
}

function getPersonaColor(persona: string) {
  const key = persona.toLowerCase()
  return (
    PERSONA_COLORS[key] ??
    { bg: 'bg-zinc-500', text: 'text-zinc-400', border: 'border-zinc-700' }
  )
}

// ─── Verdict badge variant ───────────────────────────────────────────────────

function verdictBadgeVariant(verdict: string): 'success' | 'destructive' | 'warning' | 'running' | 'default' {
  switch (verdict.toUpperCase()) {
    case 'BUY':     return 'success'
    case 'SELL':
    case 'PASS':    return 'destructive'
    case 'HOLD':    return 'warning'
    case 'MONITOR': return 'running'
    default:        return 'default'
  }
}

// ─── Confidence bar ──────────────────────────────────────────────────────────

function ConfidenceBar({ value, colorClass }: { value: number; colorClass: string }) {
  const pct = Math.max(0, Math.min(100, value))
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-zinc-800">
        <div
          className={cn('h-full rounded-full transition-all', colorClass)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-8 text-right font-mono text-xs text-zinc-400">{pct}</span>
    </div>
  )
}

// ─── AgentVerdictPanel ───────────────────────────────────────────────────────

interface AgentVerdictPanelProps {
  agent: AgentScore
}

export function AgentVerdictPanel({ agent }: AgentVerdictPanelProps) {
  const [expanded, setExpanded] = useState(true)
  const colors = getPersonaColor(agent.persona)

  return (
    <Card className="border-zinc-800 bg-zinc-900 overflow-hidden">
      {/* Header row */}
      <button
        type="button"
        className="flex w-full items-center gap-3 px-4 py-3 hover:bg-zinc-800/40 transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        {/* Persona avatar circle */}
        <div
          className={cn(
            'flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold text-zinc-900',
            colors.bg
          )}
        >
          {agent.persona.charAt(0).toUpperCase()}
        </div>

        {/* Name + verdict */}
        <div className="flex flex-1 items-center gap-2 min-w-0">
          <span className={cn('font-semibold text-sm truncate', colors.text)}>
            {agent.persona}
          </span>
          <Badge variant={verdictBadgeVariant(agent.verdict)} className="shrink-0">
            {agent.verdict}
          </Badge>
        </div>

        {/* Confidence + chevron */}
        <div className="flex items-center gap-2 shrink-0">
          <span className="font-mono text-xs text-zinc-500">{agent.confidence}</span>
          {expanded
            ? <ChevronDown className="h-3.5 w-3.5 text-zinc-500" />
            : <ChevronRight className="h-3.5 w-3.5 text-zinc-500" />
          }
        </div>
      </button>

      {/* Confidence bar */}
      <div className="px-4 pb-2">
        <ConfidenceBar value={agent.confidence} colorClass={colors.bg} />
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-zinc-800 px-4 py-3 space-y-3">
          {agent.rationale && (
            <p className="text-xs text-zinc-300 leading-relaxed">{agent.rationale}</p>
          )}

          {agent.risks && agent.risks.length > 0 && (
            <div>
              <p className="mb-1 font-mono text-[10px] uppercase tracking-wider text-zinc-500">Risks</p>
              <ul className="space-y-1">
                {agent.risks.map((risk, i) => (
                  <li key={i} className="flex gap-1.5 text-xs text-red-400">
                    <span className="mt-0.5 shrink-0">•</span>
                    <span>{risk}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {agent.upsideScenario && (
            <div className="rounded-md bg-emerald-950/40 border border-emerald-900/50 px-3 py-2">
              <p className="mb-0.5 font-mono text-[10px] uppercase tracking-wider text-emerald-600">Upside</p>
              <p className="text-xs text-emerald-300">{agent.upsideScenario}</p>
            </div>
          )}

          {agent.timeHorizon && (
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">Horizon</span>
              <span className="text-xs text-zinc-300">{agent.timeHorizon}</span>
            </div>
          )}
        </div>
      )}
    </Card>
  )
}
