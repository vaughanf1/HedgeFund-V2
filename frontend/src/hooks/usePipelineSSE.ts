import { useEffect } from 'react'
import { usePipelineStore } from '@/store/pipelineStore'

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

  useEffect(() => {
    const es = new EventSource(url)

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
      // Browser EventSource will auto-reconnect — log warning only
      console.warn('[SSE] Connection error, browser will auto-reconnect…')
    }

    return () => {
      es.close()
    }
  }, [url, handleSSEEvent])
}
