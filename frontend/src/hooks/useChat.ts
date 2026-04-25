import { useCallback, useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { chatRepo } from '@/api/repositories'
import type { AgentChatRequest, AgentChatStreamEvent, QueryRequest } from '@/types/chat'

/**
 * Hook: Agent Chat (sync)
 * 使用 /agent/chat 接口进行智能对话
 * 支持意图澄清、多轮对话
 */
export function useAgentChat() {
  return useMutation({
    mutationFn: (payload: AgentChatRequest) => chatRepo.chat(payload),
  })
}

/**
 * Hook: Wiki Query
 * 使用 /query 接口进行知识库查询
 * 同步返回完整答案
 */
export function useWikiQuery() {
  return useMutation({
    mutationFn: ({ question, save_analysis }: QueryRequest) =>
      chatRepo.query(question, save_analysis),
  })
}

/**
 * Hook: Agent Chat Stream
 * 使用 /agent/chat/stream SSE 接口进行流式智能对话
 */
export function useAgentChatStream() {
  const [isStreaming, setIsStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const send = useCallback(async (
    payload: AgentChatRequest,
    onEvent: (event: AgentChatStreamEvent) => void,
  ) => {
    setIsStreaming(true)
    abortRef.current = new AbortController()

    try {
      for await (const event of chatRepo.chatStream(payload, abortRef.current.signal)) {
        onEvent(event as AgentChatStreamEvent)
        if (event.type === 'done' || event.type === 'error') break
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        onEvent({ type: 'error', message: (err as Error).message })
      }
    } finally {
      setIsStreaming(false)
      abortRef.current = null
    }
  }, [])

  const cancel = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  return { send, cancel, isStreaming }
}
