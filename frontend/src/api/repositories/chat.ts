import { apiClient, API_BASE } from '../client'
import type {
  AgentChatRequest,
  AgentChatResponse,
  QueryResponse,
} from '@/types/chat'

export const chatRepo = {
  /**
   * POST /agent/chat
   * 统一智能入口 — 支持意图路由、多轮对话、意图澄清
   */
  chat: (payload: AgentChatRequest) =>
    apiClient.post<AgentChatResponse>('/api/v1/agent/chat', payload),

  /**
   * POST /query
   * 标准查询 — 同步返回完整答案
   */
  query: (question: string, saveAnalysis = false) =>
    apiClient.post<QueryResponse>('/api/v1/query', { question, save_analysis: saveAnalysis }),

  /**
   * POST /query/stream
   * 流式查询 — SSE 逐字返回
   * 返回 EventSource 实例，前端需自行监听 onmessage
   */
  queryStream: (question: string, saveAnalysis = false): EventSource => {
    const url = `${API_BASE}/api/v1/query/stream?question=${encodeURIComponent(question)}&save_analysis=${saveAnalysis}`
    return new EventSource(url)
  },

  /**
   * POST /agent/chat/stream
   * 流式智能对话 — fetch-based SSE
   * Returns an async generator that yields parsed SSE events.
   */
  async *chatStream(payload: AgentChatRequest, signal?: AbortSignal) {
    const url = `${API_BASE}/api/v1/agent/chat/stream`

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal,
    })

    if (!response.ok) {
      throw new Error(`SSE request failed: ${response.status}`)
    }

    const reader = response.body?.getReader()
    if (!reader) throw new Error('No response body')

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') return
          try {
            yield JSON.parse(data)
          } catch {
            // ignore malformed lines
          }
        }
      }
    }
  },
}
