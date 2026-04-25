// ============================================================
// ChatBox 类型定义 — 前端与后端 /agent/chat 接口对接
// ============================================================

// ── Agent Chat Request ──────────────────────────────────────

export interface AgentChatRequest {
  channel: 'web' | 'wechat' | 'api'
  user_id: string
  content_type: 'text' | 'image' | 'voice' | 'file' | 'url'
  text: string
  raw_data?: Record<string, unknown>
}

// ── Agent Chat Response ─────────────────────────────────────

export interface AgentChatResponse {
  reply_text: string
  reply_type: 'markdown' | 'simple'
  action_taken: 'queried' | 'ingested' | 'chatted' | 'intent_clarification' | 'saved_photo' | 'ignored' | 'clarified'
  sources?: Array<{
    slug: string
    title?: string
  }>
  citations?: Array<{
    number: number
    slug: string
    title: string
  }>
  related_pages?: Array<{
    slug: string
    title: string
    category: string
    summary: string
    updated_at: string | null
    word_count: number
  }>
  conversation_id?: string
  suggested_followups?: string[]
}

// ── Query Request / Response ────────────────────────────────

export interface QueryRequest {
  question: string
  save_analysis?: boolean
}

export interface QueryResponse {
  answer: string
  sources: string[]
  citations?: Array<{
    number: number
    slug: string
    title: string
  }>
  related_pages?: Array<{
    slug: string
    title: string
    category: string
    summary: string
    updated_at: string | null
    word_count: number
  }>
}

// ── Query Stream Events (SSE) ───────────────────────────────

export type QueryStreamEvent =
  | { type: 'sources'; sources: QueryResponse['related_pages'] }
  | { type: 'token'; token: string }
  | { type: 'done'; answer: string; references: QueryResponse['citations'] }
  | { type: 'heartbeat' }
  | { type: 'failed'; status: string; message: string }

// ── Agent Chat Stream Events (SSE) ──────────────────────────

export type AgentChatStreamEvent =
  | { type: 'status'; status: 'retrieving' | 'generating' }
  | { type: 'sources'; sources: QueryResponse['related_pages'] }
  | { type: 'token'; token: string }
  | { type: 'done'; answer: string; action_taken: AgentChatResponse['action_taken']; citations?: QueryResponse['citations']; related_pages?: QueryResponse['related_pages']; conversation_id?: string }
  | { type: 'intent_clarification'; question: string; options: IntentOption[] }
  | { type: 'error'; message: string }

// ── ChatBox Message Types (前端内部使用) ─────────────────────

export type ChatMessageRole = 'user' | 'assistant' | 'system'

export interface ChatMessage {
  id: string
  role: ChatMessageRole
  content: string                    // 文本内容（Markdown）
  contentType?: 'text' | 'intent_clarification' | 'intent_confirmation' | 'progress' | 'error'
  timestamp: number
  sources?: string[]                 // 引用的 Wiki 页面 slug
  citations?: QueryResponse['citations']
  isPending?: boolean
  options?: IntentOption[]           // 意图澄清选项
  error?: {
    code: string
    message: string
    retryable: boolean
  }
}

export interface IntentOption {
  id: string
  label: string
  description?: string
  icon?: string
  primary?: boolean
}

// ── Chat Session State ──────────────────────────────────────

export type ChatSessionState =
  | 'idle'
  | 'awaiting_intent'
  | 'awaiting_confirmation'
  | 'processing'
  | 'error'

export interface ChatSession {
  id: string
  state: ChatSessionState
  messages: ChatMessage[]
  pendingIntentData?: Record<string, unknown>
}
