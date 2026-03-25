import { usePipelineSSE } from '@/hooks/usePipelineSSE'
import { DashboardLayout } from '@/components/layout/DashboardLayout'

function App() {
  usePipelineSSE('/api/v1/events/stream')

  return <DashboardLayout />
}

export default App
