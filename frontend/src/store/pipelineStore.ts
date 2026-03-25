import { create } from 'zustand'
import {
  type Node,
  type Edge,
  type NodeChange,
  applyNodeChanges,
} from '@xyflow/react'
import { getLayoutedElements } from '@/lib/dagre'
import type { FeedItem } from '@/types/pipeline'

// ─── Types ─────────────────────────────────────────────────────────────────

export type NodeStatus = 'idle' | 'running' | 'complete' | 'error'

export interface PipelineNodeData extends Record<string, unknown> {
  label: string
  status: NodeStatus
  lastResult?: string
  conviction?: number
}

// Re-export FeedItem from types for convenience
export type { FeedItem }

export interface Opportunity {
  opportunityId: string
  convictionScore: number
  suggestedAllocationPct: number
  finalVerdict: string
  riskRating: string
  decidedAt: string
}

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

  setOutputRankings: (rankings) => {
    set({ outputRankings: rankings })
  },

  setSelectedOpportunity: (id) => {
    set({ selectedOpportunityId: id })
  },

  handleSSEEvent: (eventType, data) => {
    const { updateNodeStatus, addFeedItem } = get()

    switch (eventType) {
      case 'AGENT_STARTED': {
        const agentId = data['agent_id'] as string | undefined
        if (agentId) updateNodeStatus(agentId, 'running')
        break
      }
      case 'AGENT_COMPLETE': {
        const agentId = data['agent_id'] as string | undefined
        const verdict = data['verdict'] as string | undefined
        const ticker = data['ticker'] as string | undefined
        const persona = data['persona'] as string | undefined
        if (agentId) {
          updateNodeStatus(agentId, 'complete', {
            lastResult: verdict ? String(verdict) : undefined,
          })
        }
        if (ticker) {
          const detectionItem: FeedItem = {
            id: `${agentId ?? 'agent'}-${ticker}-${Date.now()}`,
            type: 'detection',
            ticker,
            headline: `${persona ?? agentId ?? 'Agent'} completed analysis`,
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
        updateNodeStatus('cio', 'complete')
        const decision = data['decision'] as Record<string, unknown> | undefined
        const ticker = (data['ticker'] as string) ?? 'UNKNOWN'
        const opportunityId = (data['opportunity_id'] as string) ?? crypto.randomUUID()
        if (decision) {
          const finalVerdict = (decision['final_verdict'] as string) ?? 'UNKNOWN'
          const convictionScore = Number(decision['conviction_score'] ?? 0)
          const riskRating = (decision['risk_rating'] as string) ?? 'UNKNOWN'
          const isApproval = new Set(['BUY', 'HOLD', 'MONITOR']).has(finalVerdict)
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
              : (decision['rejection_reason'] as string | undefined) ?? finalVerdict,
            timestamp: Date.now(),
          }
          addFeedItem(decisionItem)
        }
        break
      }
      default:
        break
    }
  },
}))
