// ============================================================
// AI Assistant Hook — 连接 /agent/chat 进行 AI 辅助
// ============================================================

import { useState, useCallback } from 'react'

export type AIAction =
  | 'suggest_links'     // 建议关联 Wiki 页面
  | 'explain'           // 解释选中的文字
  | 'expand'            // 扩写
  | 'condense'          // 精简
  | 'summarize'         // 生成摘要

interface AISuggestion {
  originalText: string
  suggestedText: string
  action: AIAction
  accepted: boolean
}

interface UseAIAgentReturn {
  isLoading: boolean
  error: string | null
  suggestions: AISuggestion[]
  execute: (action: AIAction, selectedText: string, context: string) => Promise<void>
  acceptSuggestion: (index: number) => void
  dismissSuggestion: (index: number) => void
  clearSuggestions: () => void
}

const ACTION_PROMPTS: Record<AIAction, string> = {
  suggest_links: (
    '请分析以下文本，推荐应该关联的 Wiki 页面（以 [[wikilink]] 格式返回）。' +
    '只返回修改后的文本，不要解释。如果已有 wikilink，保留它们。' +
    '只添加你觉得确实需要的新链接。'
  ),
  explain: (
    '请用简单易懂的中文解释以下文本的含义，保持简洁。' +
    '直接输出解释，不要说"这段文字的意思是"。'
  ),
  expand: (
    '请扩写以下内容，增加更多细节和背景信息，保持原文风格。' +
    '输出扩写后的完整内容。'
  ),
  condense: (
    '请精简以下内容，保留核心信息，去除冗余。' +
    '输出精简后的完整内容。'
  ),
  summarize: (
    '请为以下内容生成一段简洁的摘要（1-2句话）。' +
    '只输出摘要，不要解释。'
  ),
}

export function useAIAgent(): UseAIAgentReturn {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [suggestions, setSuggestions] = useState<AISuggestion[]>([])

  const execute = useCallback(async (action: AIAction, selectedText: string, context: string) => {
    setIsLoading(true)
    setError(null)

    try {
      const prompt = `${ACTION_PROMPTS[action]}\n\n## 当前页面内容：\n${context}\n\n## 选中的文本：\n${selectedText}`

      const response = await fetch('/api/v1/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          channel: 'web',
          user_id: 'editor-ai-assistant',
          content_type: 'text',
          text: prompt,
        }),
      })

      if (!response.ok) {
        throw new Error(`AI 请求失败: ${response.status}`)
      }

      const data = await response.json()
      const replyText = data.reply_text || ''

      setSuggestions((prev) => [
        ...prev,
        {
          originalText: selectedText,
          suggestedText: replyText,
          action,
          accepted: false,
        },
      ])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'AI 处理失败')
    } finally {
      setIsLoading(false)
    }
  }, [])

  const acceptSuggestion = useCallback((index: number) => {
    setSuggestions((prev) =>
      prev.map((s, i) => (i === index ? { ...s, accepted: true } : s))
    )
  }, [])

  const dismissSuggestion = useCallback((index: number) => {
    setSuggestions((prev) => prev.filter((_, i) => i !== index))
  }, [])

  const clearSuggestions = useCallback(() => {
    setSuggestions([])
  }, [])

  return {
    isLoading,
    error,
    suggestions,
    execute,
    acceptSuggestion,
    dismissSuggestion,
    clearSuggestions,
  }
}
