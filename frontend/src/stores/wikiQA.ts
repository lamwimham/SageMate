import { create } from 'zustand'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string                    // 文本内容（Markdown）
  contentType?: 'text' | 'intent_clarification' | 'intent_confirmation' | 'progress' | 'error'
  timestamp: number
  sources?: string[]                 // 引用的 Wiki 页面 slug
  citations?: Array<{ number: number; slug: string; title: string }>
  related_pages?: Array<{ slug: string; title: string; category: string; summary: string }>
  isPending?: boolean
  options?: Array<{ id: string; label: string; description?: string; icon?: string; primary?: boolean }>
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
  updateLastPending: (partial: Partial<ChatMessage>) => void
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
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  updateLastPending: (partial) =>
    set((s) => ({
      messages: s.messages.map((m, i) =>
        i === s.messages.length - 1 && m.isPending ? { ...m, ...partial } : m
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
