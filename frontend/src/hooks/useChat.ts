import { useMutation } from '@tanstack/react-query'
import { chatRepo } from '@/api/repositories'
import type { AgentChatRequest, QueryRequest } from '@/types/chat'

/**
 * Hook: Agent Chat
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
