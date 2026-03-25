import { ReactFlow, Background, Controls, type NodeTypes } from '@xyflow/react'
import { usePipelineStore } from '@/store/pipelineStore'
import { AgentNode } from './nodes/AgentNode'
import { GateNode } from './nodes/GateNode'
import { StageNode } from './nodes/StageNode'

// IMPORTANT: nodeTypes MUST be defined at module level, not inside the
// component render function. Defining inside render causes React Flow to
// re-register node types on every render, destroying all node instances.
const nodeTypes: NodeTypes = {
  agent: AgentNode,
  gate: GateNode,
  stage: StageNode,
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
