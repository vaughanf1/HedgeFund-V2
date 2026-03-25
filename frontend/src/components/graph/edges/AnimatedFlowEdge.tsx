import { memo } from 'react'
import { BaseEdge, getSmoothStepPath, type EdgeProps } from '@xyflow/react'

interface AnimatedFlowEdgeData extends Record<string, unknown> {
  active?: boolean
}

function AnimatedFlowEdgeComponent({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  markerEnd,
}: EdgeProps) {
  const edgeData = (data ?? {}) as AnimatedFlowEdgeData
  const isActive = edgeData.active === true

  const [edgePath] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  })

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          stroke: isActive ? '#0A84FF' : '#3f3f46',
          strokeWidth: isActive ? 2 : 1,
          transition: 'stroke 0.3s ease, stroke-width 0.3s ease',
        }}
      />
      {isActive && (
        <circle r="4" fill="#0A84FF">
          <animateMotion dur="1.5s" repeatCount="indefinite" path={edgePath} />
        </circle>
      )}
    </>
  )
}

export const AnimatedFlowEdge = memo(AnimatedFlowEdgeComponent)
