import { memo } from 'react'
import type { AgentScore } from '@/types/pipeline'

// ─── Persona config ─────────────────────────────────────────────────────────

const PERSONA_CONFIG: Record<
  string,
  { displayName: string; dotClass: string }
> = {
  buffett: { displayName: 'Warren Buffett', dotClass: 'bg-amber-400' },
  munger: { displayName: 'Charlie Munger', dotClass: 'bg-violet-400' },
  ackman: { displayName: 'Bill Ackman', dotClass: 'bg-cyan-400' },
  cohen: { displayName: 'Steve Cohen', dotClass: 'bg-pink-400' },
  dalio: { displayName: 'Ray Dalio', dotClass: 'bg-sky-400' },
}

function getPersonaConfig(persona: string) {
  const key = persona.toLowerCase()
  return (
    PERSONA_CONFIG[key] ?? {
      displayName: persona.charAt(0).toUpperCase() + persona.slice(1),
      dotClass: 'bg-zinc-400',
    }
  )
}

// ─── Confidence bar color ───────────────────────────────────────────────────

function confidenceBarClass(confidence: number): string {
  if (confidence > 70) return 'bg-emerald-500'
  if (confidence >= 40) return 'bg-yellow-500'
  return 'bg-red-500'
}

// ─── Verdict badge color ────────────────────────────────────────────────────

function verdictTextClass(verdict: string): string {
  switch (verdict.toUpperCase()) {
    case 'BUY':
      return 'text-emerald-400'
    case 'SELL':
      return 'text-red-400'
    case 'HOLD':
      return 'text-yellow-400'
    default:
      return 'text-zinc-500'
  }
}

// ─── Component ──────────────────────────────────────────────────────────────

interface AgentBreakdownProps {
  score: AgentScore
}

export const AgentBreakdown = memo(function AgentBreakdown({
  score,
}: AgentBreakdownProps) {
  const { displayName, dotClass } = getPersonaConfig(score.persona)
  const barWidth = Math.max(0, Math.min(100, score.confidence))
  const barColor = confidenceBarClass(score.confidence)
  const verdictColor = verdictTextClass(score.verdict)

  return (
    <div
      className="flex items-center gap-2 py-0.5"
      title={score.rationale ?? `${displayName}: ${score.verdict} (${score.confidence})`}
    >
      {/* Persona dot */}
      <span className={`h-1.5 w-1.5 flex-shrink-0 rounded-full ${dotClass}`} />

      {/* Name */}
      <span className="w-28 flex-shrink-0 truncate font-mono text-xs text-zinc-300">
        {displayName}
      </span>

      {/* Confidence bar */}
      <div className="h-1 flex-1 rounded-full bg-zinc-800">
        <div
          className={`h-1 rounded-full transition-all ${barColor}`}
          style={{ width: `${barWidth}%` }}
        />
      </div>

      {/* Score */}
      <span className="w-6 flex-shrink-0 text-right font-mono text-xs text-zinc-400">
        {score.confidence}
      </span>

      {/* Verdict */}
      <span className={`w-10 flex-shrink-0 text-right font-mono text-xs font-semibold ${verdictColor}`}>
        {score.verdict.toUpperCase()}
      </span>
    </div>
  )
})
