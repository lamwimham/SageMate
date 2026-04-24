import { useEffect, useRef, useState, useCallback } from 'react'

export function useSSE<T>(url: string) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [connected, setConnected] = useState(false)
  const esRef = useRef<EventSource | null>(null)

  const connect = useCallback(() => {
    if (esRef.current) return
    const es = new EventSource(url)
    esRef.current = es

    es.onopen = () => setConnected(true)
    es.onmessage = (e) => {
      try {
        setData(JSON.parse(e.data))
      } catch {
        setData(e.data as unknown as T)
      }
    }
    es.onerror = () => setError(new Error('SSE error'))
  }, [url])

  const disconnect = useCallback(() => {
    esRef.current?.close()
    esRef.current = null
    setConnected(false)
  }, [])

  useEffect(() => {
    return () => {
      disconnect()
    }
  }, [disconnect])

  return { data, error, connected, connect, disconnect }
}
