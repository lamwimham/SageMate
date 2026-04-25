import { apiClient } from '../client'
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
    const url = `/query/stream?question=${encodeURIComponent(question)}&save_analysis=${saveAnalysis}`
    return new EventSource(url)
  },
}
