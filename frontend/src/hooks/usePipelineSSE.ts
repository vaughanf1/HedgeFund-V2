import { useEffect } from 'react'
import { create } from 'zustand'
import { usePipelineStore } from '@/store/pipelineStore'

// ─── SSE connection state ─────────────────────────────────────────────────

export type SSEStatus = 'connecting' | 'connected' | 'disconnected'

interface SSEState {
  status: SSEStatus
  setStatus: (status: SSEStatus) => void
}

export const useSSEStore = create<SSEState>((set) => ({
  status: 'disconnected',
  setStatus: (status) => set({ status }),
}))

/**
 * Connect to the backend SSE stream and dispatch pipeline events to the
 * Zustand store.
 *
 * The backend sends events as:
 *   event: pipeline
 *   data: {"event": "AGENT_STARTED", "data": {...}}
 *
 * The browser EventSource API handles reconnect automatically on error.
 */
export function usePipelineSSE(url: string) {
  const handleSSEEvent = usePipelineStore((s) => s.handleSSEEvent)
  const setStatus = useSSEStore((s) => s.setStatus)

  useEffect(() => {
    setStatus('connecting')
    const es = new EventSource(url)

    es.onopen = () => {
      setStatus('connected')
    }

    es.addEventListener('pipeline', (e: MessageEvent) => {
      try {
        const parsed = JSON.parse(e.data) as {
          event: string
          data: Record<string, unknown>
        }
        handleSSEEvent(parsed.event, parsed.data)
      } catch (err) {
        console.warn('[SSE] Failed to parse pipeline event:', err)
      }
    })

    es.onerror = () => {
      setStatus('disconnected')
      // Browser EventSource will auto-reconnect — log warning only
      console.warn('[SSE] Connection error, browser will auto-reconnect…')
    }

    return () => {
      es.close()
      setStatus('disconnected')
    }
  }, [url, handleSSEEvent, setStatus])
}
