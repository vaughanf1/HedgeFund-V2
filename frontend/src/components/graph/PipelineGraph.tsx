import { ReactFlow, Background, Controls, type NodeTypes, type EdgeTypes } from '@xyflow/react'
import { usePipelineStore } from '@/store/pipelineStore'
import { AgentNode } from './nodes/AgentNode'
import { GateNode } from './nodes/GateNode'
import { StageNode } from './nodes/StageNode'
import { AnimatedFlowEdge } from './edges/AnimatedFlowEdge'

// IMPORTANT: nodeTypes and edgeTypes MUST be defined at module level, not
// inside the component render function. Defining inside render causes React
// Flow to re-register types on every render, destroying all node/edge instances.
const nodeTypes: NodeTypes = {
  agent: AgentNode,
  gate: GateNode,
  stage: StageNode,
}

const edgeTypes: EdgeTypes = {
  animated: AnimatedFlowEdge,
}

export function PipelineGraph() {
  const nodes = usePipelineStore((s) => s.nodes)
  const edges = usePipelineStore((s) => s.edges)
  const onNodesChange = usePipelineStore((s) => s.onNodesChange)

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      colorMode="dark"
      fitView
      fitViewOptions={{ padding: 0.2 }}
      className="bloomberg-flow"
      proOptions={{ hideAttribution: true }}
    >
      <Background color="#27272a" gap={24} />
      <Controls />
    </ReactFlow>
  )
}
