import { create } from 'zustand'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string                    // 文本内容（Markdown）
  contentType?: 'text' | 'intent_clarification' | 'intent_confirmation' | 'progress' | 'error' | 'contextual_suggestion'
  timestamp: number
  sources?: string[]                 // 引用的 Wiki 页面 slug
  citations?: Array<{ number: number; slug: string; title: string }>
  related_pages?: Array<{ slug: string; title: string; category: string; summary: string }>
  isPending?: boolean
  options?: Array<{ id: string; label: string; description?: string; icon?: string; primary?: boolean }>
  thinking?: string                  // LLM 思考过程（reasoning content）
  error?: {
    code: string
    message: string
    retryable: boolean
  }
}

interface WikiQAState {
  messages: ChatMessage[]
  conversationId: string
  addMessage: (msg: ChatMessage) => void
  updateMessage: (id: string, partial: Partial<ChatMessage>) => void
  appendToMessage: (id: string, text: string) => void
  updateLastPending: (partial: Partial<ChatMessage>) => void
  appendToLastAssistant: (text: string) => void
  appendThinkingToLastAssistant: (text: string) => void
  clearMessages: () => void
  setConversationId: (id: string) => void
  /** Legacy compatibility */
  question: string
  answer: string | null
  sources: string[]
  isPending: boolean
  setQuestion: (q: string) => void
  setAnswer: (a: string | null) => void
  setSources: (s: string[]) => void
  setIsPending: (p: boolean) => void
  clear: () => void
}

export const useWikiQAStore = create<WikiQAState>((set) => ({
  // New chat-style messages
  messages: [],
  conversationId: `web_${typeof crypto !== 'undefined' ? crypto.randomUUID() : 'local'}`,
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg].slice(-100) })),
  updateMessage: (id, partial) =>
    set((s) => ({
      messages: s.messages.map((m) => (m.id === id ? { ...m, ...partial } : m)),
    })),
  appendToMessage: (id, text) =>
    set((s) => ({
      messages: s.messages.map((m) => (m.id === id ? { ...m, content: m.content + text } : m)),
    })),
  updateLastPending: (partial) =>
    set((s) => ({
      messages: s.messages.map((m, i) =>
        i === s.messages.length - 1 && m.isPending ? { ...m, ...partial } : m
      ),
    })),
  /** Append text to the last assistant message (for streaming) */
  appendToLastAssistant: (text: string) =>
    set((s) => ({
      messages: s.messages.map((m, i) =>
        i === s.messages.length - 1 && m.role === 'assistant'
          ? { ...m, content: m.content + text }
          : m
      ),
    })),
  /** Append thinking text to the last assistant message */
  appendThinkingToLastAssistant: (text: string) =>
    set((s) => ({
      messages: s.messages.map((m, i) =>
        i === s.messages.length - 1 && m.role === 'assistant'
          ? { ...m, thinking: (m.thinking || '') + text }
          : m
      ),
    })),
  clearMessages: () => set({ messages: [], conversationId: `web_${typeof crypto !== 'undefined' ? crypto.randomUUID() : 'local'}` }),
  setConversationId: (id) => set({ conversationId: id }),

  // Legacy compatibility (kept for any code still using the old interface)
  question: '',
  answer: null,
  sources: [],
  isPending: false,
  setQuestion: (q) => set({ question: q }),
  setAnswer: (a) => set({ answer: a }),
  setSources: (s) => set({ sources: s }),
  setIsPending: (p) => set({ isPending: p }),
  clear: () => set({ question: '', answer: null, sources: [], isPending: false, messages: [] }),
}))
