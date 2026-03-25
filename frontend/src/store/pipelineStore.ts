import { create } from 'zustand'
import {
  type Node,
  type Edge,
  type NodeChange,
  applyNodeChanges,
} from '@xyflow/react'
import { getLayoutedElements } from '@/lib/dagre'

// ─── Types ─────────────────────────────────────────────────────────────────

export type NodeStatus = 'idle' | 'running' | 'complete' | 'error'

export interface PipelineNodeData extends Record<string, unknown> {
  label: string
  status: NodeStatus
  lastResult?: string
  conviction?: number
}

export interface FeedItem {
  id: string
  ticker: string
  verdict: string
  conviction: number
  allocation: number
  riskRating: string
  decidedAt: string
}

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
  { id: 'e-scanner-signal', source: 'scanner', target: 'signal_detector' },
  { id: 'e-signal-gate', source: 'signal_detector', target: 'quality_gate' },
  { id: 'e-gate-buffett', source: 'quality_gate', target: 'buffett' },
  { id: 'e-gate-munger', source: 'quality_gate', target: 'munger' },
  { id: 'e-gate-ackman', source: 'quality_gate', target: 'ackman' },
  { id: 'e-gate-cohen', source: 'quality_gate', target: 'cohen' },
  { id: 'e-gate-dalio', source: 'quality_gate', target: 'dalio' },
  { id: 'e-buffett-committee', source: 'buffett', target: 'committee' },
  { id: 'e-munger-committee', source: 'munger', target: 'committee' },
  { id: 'e-ackman-committee', source: 'ackman', target: 'committee' },
  { id: 'e-cohen-committee', source: 'cohen', target: 'committee' },
  { id: 'e-dalio-committee', source: 'dalio', target: 'committee' },
  { id: 'e-committee-cio', source: 'committee', target: 'cio' },
]

// Compute layout once at module load (not inside render)
const { nodes: initialNodes, edges: initialEdges } = getLayoutedElements(rawNodes, rawEdges, 'LR')

// ─── Store ──────────────────────────────────────────────────────────────────

interface PipelineState {
  nodes: PipelineNode[]
  edges: Edge[]
  feedItems: FeedItem[]
  outputRankings: Opportunity[]
}

interface PipelineActions {
  onNodesChange: (changes: NodeChange<PipelineNode>[]) => void
  updateNodeStatus: (nodeId: string, status: NodeStatus, data?: Partial<PipelineNodeData>) => void
  addFeedItem: (item: FeedItem) => void
  setOutputRankings: (rankings: Opportunity[]) => void
  handleSSEEvent: (eventType: string, data: Record<string, unknown>) => void
}

type PipelineStore = PipelineState & PipelineActions

export const usePipelineStore = create<PipelineStore>((set, get) => ({
  nodes: initialNodes,
  edges: initialEdges,
  feedItems: [],
  outputRankings: [],

  onNodesChange: (changes) => {
    set((state) => ({
      nodes: applyNodeChanges(changes, state.nodes),
    }))
  },

  updateNodeStatus: (nodeId, status, extra) => {
    set((state) => ({
      nodes: state.nodes.map((n) =>
        n.id === nodeId
          ? { ...n, data: { ...n.data, status, ...extra } }
          : n
      ),
    }))
  },

  addFeedItem: (item) => {
    set((state) => ({
      feedItems: [item, ...state.feedItems].slice(0, 100),
    }))
  },

  setOutputRankings: (rankings) => {
    set({ outputRankings: rankings })
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
        if (agentId) {
          updateNodeStatus(agentId, 'complete', {
            lastResult: verdict ? String(verdict) : undefined,
          })
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
        if (decision) {
          const item: FeedItem = {
            id: (data['opportunity_id'] as string) ?? crypto.randomUUID(),
            ticker: (data['ticker'] as string) ?? 'UNKNOWN',
            verdict: (decision['final_verdict'] as string) ?? 'UNKNOWN',
            conviction: Number(decision['conviction_score'] ?? 0),
            allocation: Number(decision['suggested_allocation_pct'] ?? 0),
            riskRating: (decision['risk_rating'] as string) ?? 'UNKNOWN',
            decidedAt: (decision['decided_at'] as string) ?? new Date().toISOString(),
          }
          addFeedItem(item)
        }
        break
      }
      default:
        break
    }
  },
}))
