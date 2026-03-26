import { create } from 'zustand'
import {
  type Node,
  type Edge,
  type NodeChange,
  applyNodeChanges,
} from '@xyflow/react'
import { getLayoutedElements } from '@/lib/dagre'
import type { FeedItem, Opportunity } from '@/types/pipeline'

// ─── Types ─────────────────────────────────────────────────────────────────

export type NodeStatus = 'idle' | 'running' | 'complete' | 'error'

export interface PipelineNodeData extends Record<string, unknown> {
  label: string
  status: NodeStatus
  lastResult?: string
  conviction?: number
}

// Re-export shared types for convenience
export type { FeedItem, Opportunity }

type PipelineNode = Node<PipelineNodeData>

// ─── Initial pipeline topology ─────────────────────────────────────────────

const rawNodes: PipelineNode[] = [
  { id: 'scanner', type: 'stage', position: { x: 0, y: 0 }, data: { label: 'Market Scanner', status: 'idle' } },
  { id: 'signal_detector', type: 'stage', position: { x: 0, y: 0 }, data: { label: 'Signal Detector', status: 'idle' } },
  { id: 'quality_gate', type: 'gate', position: { x: 0, y: 0 }, data: { label: 'Quality Gate', status: 'idle' } },
  { id: 'buffett', type: 'agent', position: { x: 0, y: 0 }, data: { label: 'Warren Buffett', status: 'idle' } },
  { id: 'munger', type: 'agent', position: { x: 0, y: 0 }, data: { label: 'Charlie Munger', status: 'idle' } },
  { id: 'ackman', type: 'agent', position: { x: 0, y: 0 }, data: { label: 'Bill Ackman', status: 'idle' } },
  { id: 'cohen', type: 'agent', position: { x: 0, y: 0 }, data: { label: 'Steve Cohen', status: 'idle' } },
  { id: 'dalio', type: 'agent', position: { x: 0, y: 0 }, data: { label: 'Ray Dalio', status: 'idle' } },
  { id: 'committee', type: 'stage', position: { x: 0, y: 0 }, data: { label: 'Committee', status: 'idle' } },
  { id: 'cio', type: 'stage', position: { x: 0, y: 0 }, data: { label: 'CIO', status: 'idle' } },
]

const rawEdges: Edge[] = [
  { id: 'e-scanner-signal', type: 'animated', source: 'scanner', target: 'signal_detector', data: { active: false } },
  { id: 'e-signal-gate', type: 'animated', source: 'signal_detector', target: 'quality_gate', data: { active: false } },
  { id: 'e-gate-buffett', type: 'animated', source: 'quality_gate', target: 'buffett', data: { active: false } },
  { id: 'e-gate-munger', type: 'animated', source: 'quality_gate', target: 'munger', data: { active: false } },
  { id: 'e-gate-ackman', type: 'animated', source: 'quality_gate', target: 'ackman', data: { active: false } },
  { id: 'e-gate-cohen', type: 'animated', source: 'quality_gate', target: 'cohen', data: { active: false } },
  { id: 'e-gate-dalio', type: 'animated', source: 'quality_gate', target: 'dalio', data: { active: false } },
  { id: 'e-buffett-committee', type: 'animated', source: 'buffett', target: 'committee', data: { active: false } },
  { id: 'e-munger-committee', type: 'animated', source: 'munger', target: 'committee', data: { active: false } },
  { id: 'e-ackman-committee', type: 'animated', source: 'ackman', target: 'committee', data: { active: false } },
  { id: 'e-cohen-committee', type: 'animated', source: 'cohen', target: 'committee', data: { active: false } },
  { id: 'e-dalio-committee', type: 'animated', source: 'dalio', target: 'committee', data: { active: false } },
  { id: 'e-committee-cio', type: 'animated', source: 'committee', target: 'cio', data: { active: false } },
]

// Compute layout once at module load (not inside render)
const { nodes: initialNodes, edges: initialEdges } = getLayoutedElements(rawNodes, rawEdges, 'LR')

// ─── Helpers ────────────────────────────────────────────────────────────────

/** Sort opportunities by convictionScore descending, cap at 10 */
function sortAndCap(rankings: Opportunity[]): Opportunity[] {
  return [...rankings]
    .sort((a, b) => b.convictionScore - a.convictionScore)
    .slice(0, 10)
}

// ─── Store ──────────────────────────────────────────────────────────────────

interface PipelineState {
  nodes: PipelineNode[]
  edges: Edge[]
  feedItems: FeedItem[]
  outputRankings: Opportunity[]
  selectedOpportunityId: string | null
}

interface PipelineActions {
  onNodesChange: (changes: NodeChange<PipelineNode>[]) => void
  updateNodeStatus: (nodeId: string, status: NodeStatus, data?: Partial<PipelineNodeData>) => void
  addFeedItem: (item: FeedItem) => void
  setOutputRankings: (rankings: Opportunity[]) => void
  handleSSEEvent: (eventType: string, data: Record<string, unknown>) => void
  setSelectedOpportunity: (id: string | null) => void
}

type PipelineStore = PipelineState & PipelineActions

export const usePipelineStore = create<PipelineStore>((set, get) => ({
  nodes: initialNodes,
  edges: initialEdges,
  feedItems: [],
  outputRankings: [],
  selectedOpportunityId: null,

  onNodesChange: (changes) => {
    set((state) => ({
      nodes: applyNodeChanges(changes, state.nodes),
    }))
  },

  updateNodeStatus: (nodeId, status, extra) => {
    set((state) => {
      const isRunning = status === 'running'
      return {
        nodes: state.nodes.map((n) =>
          n.id === nodeId
            ? { ...n, data: { ...n.data, status, ...extra } }
            : n
        ),
        edges: state.edges.map((e) =>
          e.source === nodeId
            ? { ...e, data: { ...e.data, active: isRunning } }
            : e
        ),
      }
    })
  },

  addFeedItem: (item) => {
    set((state) => ({
      feedItems: [item, ...state.feedItems].slice(0, 100),
    }))
  },

  /** Replace output rankings; sorts by convictionScore desc, caps at 10 */
  setOutputRankings: (rankings) => {
    set({ outputRankings: sortAndCap(rankings) })
  },

  setSelectedOpportunity: (id) => {
    set({ selectedOpportunityId: id })
  },

  handleSSEEvent: (eventType, data) => {
    const { updateNodeStatus, addFeedItem } = get()

    switch (eventType) {
      case 'AGENT_STARTED': {
        // Backend sends: { persona, opportunity_id, ticker }
        const persona = data['persona'] as string | undefined
        if (persona) updateNodeStatus(persona, 'running')
        break
      }
      case 'AGENT_COMPLETE': {
        // Backend sends: { persona, opportunity_id, ticker, verdict, confidence }
        const persona = data['persona'] as string | undefined
        const verdict = data['verdict'] as string | undefined
        const ticker = data['ticker'] as string | undefined
        const opportunityId = data['opportunity_id'] as string | undefined
        if (persona) {
          updateNodeStatus(persona, 'complete', {
            lastResult: verdict ? String(verdict) : undefined,
          })
        }
        if (ticker) {
          const detectionItem: FeedItem = {
            id: `${persona ?? 'agent'}-${ticker}-${Date.now()}`,
            type: 'detection',
            ticker,
            headline: `${persona ?? 'Agent'} completed analysis — ${verdict ?? ''}`,
            convictionScore: data['confidence'] != null ? Number(data['confidence']) : undefined,
            timestamp: Date.now(),
          }
          addFeedItem(detectionItem)
        }
        break
      }
      case 'COMMITTEE_COMPLETE': {
        updateNodeStatus('committee', 'complete')
        break
      }
      case 'DECISION_MADE': {
        // Backend sends: { opportunity_id, ticker, decision: {...}, verdicts: [...] }
        updateNodeStatus('cio', 'complete')
        const decision = data['decision'] as Record<string, unknown> | undefined
        const ticker = (data['ticker'] as string) ?? 'UNKNOWN'
        const opportunityId = (data['opportunity_id'] as string) ?? crypto.randomUUID()

        if (decision) {
          const finalVerdict = (decision['final_verdict'] as string) ?? 'UNKNOWN'
          const convictionScore = Number(decision['conviction_score'] ?? 0)
          const riskRating = (decision['risk_rating'] as string) ?? 'UNKNOWN'
          // Map backend INVEST/MONITOR/PASS to display-friendly values
          const isApproval = new Set(['INVEST', 'MONITOR', 'BUY', 'HOLD']).has(finalVerdict)

          // Build FeedItem for the activity feed
          const decisionItem: FeedItem = {
            id: opportunityId,
            type: isApproval ? 'decision' : 'rejection',
            ticker,
            headline: isApproval
              ? `${finalVerdict} — conviction ${convictionScore}`
              : `Rejected: ${finalVerdict}`,
            convictionScore: isApproval ? convictionScore : undefined,
            riskRating,
            finalVerdict,
            rejectionReason: isApproval
              ? undefined
              : finalVerdict,
            timestamp: Date.now(),
          }
          addFeedItem(decisionItem)

          // Build Opportunity and insert/replace in outputRankings
          const rawVerdicts = data['verdicts'] as Array<Record<string, unknown>> | undefined
          const agentScores = (rawVerdicts ?? []).map((v) => ({
            persona: (v['persona'] as string) ?? '',
            verdict: (v['verdict'] as string) ?? '',
            confidence: Number(v['confidence'] ?? v['confidence_score'] ?? 0),
            rationale: v['rationale'] as string | undefined,
          }))

          const opportunity: Opportunity = {
            opportunityId,
            ticker,
            convictionScore,
            suggestedAllocationPct: Number(decision['suggested_allocation_pct'] ?? 0),
            finalVerdict,
            riskRating,
            decidedAt: new Date().toISOString(),
            agentScores,
            keyCatalysts: decision['key_catalysts'] as string[] | undefined,
            timeHorizon: decision['time_horizon'] as string | undefined,
          }

          // Insert or replace existing opportunity, then re-sort and cap at 10
          set((state) => {
            const filtered = state.outputRankings.filter(
              (o) => o.opportunityId !== opportunityId
            )
            return { outputRankings: sortAndCap([opportunity, ...filtered]) }
          })
        }
        break
      }
      default:
        break
    }
  },
}))
