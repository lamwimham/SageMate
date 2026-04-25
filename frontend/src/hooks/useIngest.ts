import { useState, useEffect, useCallback, useRef } from 'react'
import { useMutation } from '@tanstack/react-query'
import { ingestRepo } from '@/api/repositories'
import type { IngestResult, IngestTaskState } from '@/types'

export function useIngestText() {
  return useMutation<IngestResult, Error, { text: string; title: string; auto_compile: boolean }>({
    mutationFn: ({ text, title, auto_compile }) =>
      ingestRepo.ingestText(text, title, { auto_compile }),
  })
}

export function useIngestFile() {
  return useMutation<IngestResult, Error, { file: File; auto_compile: boolean }>({
    mutationFn: ({ file, auto_compile }) =>
      ingestRepo.ingestFile(file, { auto_compile }),
  })
}

export function useIngestUrl() {
  return useMutation<IngestResult, Error, { url: string; auto_compile: boolean }>({
    mutationFn: ({ url, auto_compile }) =>
      ingestRepo.ingestUrl(url, { auto_compile }),
  })
}

const INGEST_STEPS = [
  { key: 'queued', label: '提交任务', desc: '等待调度...' },
  { key: 'parsing', label: '解析内容', desc: '提取文本...' },
  { key: 'reading_context', label: '读取上下文', desc: '加载知识库...' },
  { key: 'calling_llm', label: 'LLM 分析中', desc: '大模型推理...' },
  { key: 'writing_pages', label: '生成 Wiki', desc: '写入文件...' },
  { key: 'updating_index', label: '更新索引', desc: '同步检索...' },
  { key: 'completed', label: '完成', desc: '编译成功' },
]

export function useIngestProgress(taskId: string | null) {
  const [state, setState] = useState<IngestTaskState | null>(null)
  const [connected, setConnected] = useState(false)
  const esRef = useRef<EventSource | null>(null)
  const taskIdRef = useRef(taskId)
  taskIdRef.current = taskId

  const connect = useCallback(() => {
    const currentTaskId = taskIdRef.current
    if (!currentTaskId || esRef.current) return
    const es = new EventSource(`/api/v1/ingest/progress/${currentTaskId}`)
    esRef.current = es
    setConnected(true)

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.type === 'heartbeat') return
        setState(data)
        if (data.status === 'completed' || data.status === 'failed') {
          es.close()
          esRef.current = null
          setConnected(false)
        }
      } catch {
        // ignore parse errors
      }
    }

    es.onerror = () => {
      es.close()
      esRef.current = null
      setConnected(false)
    }
  }, [])

  const disconnect = useCallback(() => {
    esRef.current?.close()
    esRef.current = null
    setConnected(false)
  }, [])

  // Auto-connect when taskId becomes available; disconnect on unmount or taskId change.
  useEffect(() => {
    if (taskId) {
      connect()
    }
    return () => {
      disconnect()
    }
  }, [taskId, connect, disconnect])

  const stepIndex = INGEST_STEPS.findIndex((s) => s.key === state?.status)
  const currentStep = stepIndex >= 0 ? stepIndex : 0
  const pct = state ? Math.min(100, Math.round((currentStep / (INGEST_STEPS.length - 1)) * 100)) : 0

  return { state, connected, connect, disconnect, steps: INGEST_STEPS, pct, currentStep }
}
