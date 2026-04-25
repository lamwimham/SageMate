import { useState, useRef, useCallback, useEffect } from 'react'
import { useAgentChatStream } from '@/hooks/useChat'
import { useWikiQAStore, type ChatMessage } from '@/stores/wikiQA'
import { MarkdownRenderer } from '@/components/markdown/MarkdownRenderer'
import { cn } from '@/lib/utils'
import { Link } from '@tanstack/react-router'
import type { AgentChatStreamEvent, IntentOption } from '@/types/chat'

// ── Intent Clarification Card ─────────────────────────────────

function IntentClarificationCard({
  question,
  options,
  onSelect,
}: {
  question: string
  options: IntentOption[]
  onSelect: (optionId: string) => void
}) {
  return (
    <div className="max-w-[92%] rounded-2xl rounded-tl-md bg-bg-elevated/60 border border-border-subtle px-4 py-3">
      <p className="text-sm text-text-primary mb-3">{question}</p>
      <div className="space-y-2">
        {options.map((opt) => (
          <button
            key={opt.id}
            onClick={() => onSelect(opt.id)}
            className={cn(
              'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition',
              opt.primary
                ? 'bg-accent-neural/10 border border-accent-neural/20 hover:bg-accent-neural/15'
                : 'bg-bg-hover/50 hover:bg-bg-hover'
            )}
          >
            <span className="text-lg">{opt.icon || '•'}</span>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-text-primary">{opt.label}</div>
              {opt.description && (
                <div className="text-xs text-text-muted truncate">{opt.description}</div>
              )}
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Citation Links ─────────────────────────────────────────────

function CitationLinks({ citations }: { citations?: Array<{ number: number; slug: string; title: string }> }) {
  if (!citations || citations.length === 0) return null

  return (
    <div className="mt-1.5 ml-1 flex flex-wrap gap-1">
      {citations.map((c) => (
        <Link
          key={c.number}
          to="/wiki/$slug"
          params={{ slug: c.slug }}
          className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[12px] text-text-muted hover:text-accent-neural hover:bg-accent-neural/5 transition"
          title={c.title}
        >
          <span className="font-mono text-accent-neural/70">[{c.number}]</span>
          <span className="truncate max-w-[80px]">{c.title}</span>
        </Link>
      ))}
    </div>
  )
}

// ── Related Pages ──────────────────────────────────────────────

function RelatedPages({ pages }: { pages?: Array<{ slug: string; title: string; category: string; summary: string }> }) {
  if (!pages || pages.length === 0) return null

  return (
    <div className="mt-2 ml-1">
      <div className="text-[12px] text-text-muted mb-1">相关页面</div>
      <div className="space-y-1">
        {pages.slice(0, 3).map((p) => (
          <Link
            key={p.slug}
            to="/wiki/$slug"
            params={{ slug: p.slug }}
            className="block px-2 py-1.5 rounded-lg bg-bg-elevated/40 border border-border-subtle/50 hover:border-accent-neural/20 hover:bg-accent-neural/5 transition"
          >
            <div className="text-[12px] font-medium text-text-primary truncate">{p.title}</div>
            {p.summary && (
              <div className="text-[12px] text-text-muted mt-0.5 line-clamp-1">{p.summary}</div>
            )}
          </Link>
        ))}
      </div>
    </div>
  )
}

// ── Message Bubble ──────────────────────────────────────────

function MessageBubble({ message, onIntentSelect, streamStatus }: { message: ChatMessage; onIntentSelect?: (id: string) => void; streamStatus?: 'idle' | 'retrieving' | 'generating' }) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end animate-fade-up">
        <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-accent-neural/10 px-4 py-2.5 border border-accent-neural/10">
          <p className="text-sm text-text-primary whitespace-pre-wrap">{message.content}</p>
        </div>
      </div>
    )
  }

  // Assistant message
  const statusText = streamStatus === 'retrieving'
    ? '正在检索知识库...'
    : streamStatus === 'generating'
      ? '正在生成回答...'
      : 'AI 正在思考...'

  return (
    <div className="animate-fade-up">
      {message.isPending ? (
        <div className="flex items-center gap-2 py-3 text-text-muted">
          <div className="w-4 h-4 border-2 border-accent-neural border-t-transparent rounded-full animate-spin" />
          <span className="text-xs">{statusText}</span>
        </div>
      ) : message.contentType === 'intent_clarification' && message.options ? (
        <IntentClarificationCard
          question={message.content}
          options={message.options}
          onSelect={onIntentSelect || (() => {})}
        />
      ) : (
        <>
          <div className="max-w-[92%] rounded-2xl rounded-tl-sm bg-bg-elevated/50 border border-border-subtle/60 px-4 py-3">
            <div className="markdown-body text-sm text-text-primary">
              <MarkdownRenderer content={message.content} />
            </div>
          </div>
          <CitationLinks citations={message.citations} />
          <RelatedPages pages={message.related_pages} />
        </>
      )}
    </div>
  )
}

// ── Voice Recognition Hook ──────────────────────────────────

function useSpeechRecognition() {
  const [isListening, setIsListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  const recognitionRef = useRef<any>(null)

  const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
  const isSupported = !!SpeechRecognition

  const startListening = () => {
    if (!isSupported) return
    const recognition = new SpeechRecognition()
    recognition.lang = 'zh-CN'
    recognition.interimResults = true
    recognition.continuous = false
    recognition.onresult = (event: any) => {
      let text = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        text += event.results[i][0].transcript
      }
      setTranscript(text)
    }
    recognition.onend = () => setIsListening(false)
    recognition.onerror = () => setIsListening(false)
    recognition.start()
    recognitionRef.current = recognition
    setIsListening(true)
  }

  const stopListening = () => {
    recognitionRef.current?.stop()
    setIsListening(false)
  }

  return { isListening, transcript, isSupported, startListening, stopListening, setTranscript }
}

// ── Main Chat Panel ─────────────────────────────────────────

export function WikiChatPanel() {
  const { messages, addMessage, updateLastPending, appendToLastAssistant, clearMessages, conversationId, setConversationId } = useWikiQAStore()
  const [input, setInput] = useState('')
  const [streamStatus, setStreamStatus] = useState<'idle' | 'retrieving' | 'generating'>('idle')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const chatStream = useAgentChatStream()
  const voice = useSpeechRecognition()

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Handle streaming events
  const handleStreamEvent = useCallback(
    (event: AgentChatStreamEvent) => {
      switch (event.type) {
        case 'status':
          setStreamStatus(event.status)
          break
        case 'token':
          appendToLastAssistant(event.token)
          break
        case 'sources':
          updateLastPending({ related_pages: event.sources })
          break
        case 'done':
          setStreamStatus('idle')
          if (event.conversation_id) {
            setConversationId(event.conversation_id)
          }
          updateLastPending({
            content: event.answer,
            citations: event.citations,
            related_pages: event.related_pages,
            isPending: false,
          })
          break
        case 'intent_clarification':
          setStreamStatus('idle')
          updateLastPending({
            content: event.question,
            contentType: 'intent_clarification',
            options: event.options,
            isPending: false,
          })
          break
        case 'error':
          setStreamStatus('idle')
          updateLastPending({
            content: `出错: ${event.message}`,
            isPending: false,
          })
          break
      }
    },
    [updateLastPending, appendToLastAssistant, setConversationId]
  )

  // Handle intent option selection from clarification card
  const handleIntentSelect = useCallback(
    (optionId: string) => {
      const selectedOption = messages
        .flatMap((m) => m.options || [])
        .find((o) => o.id === optionId)
      const label = selectedOption?.label || optionId

      addMessage({
        id: crypto.randomUUID(),
        role: 'user',
        content: label,
        timestamp: Date.now(),
      })

      const assistantId = crypto.randomUUID()
      addMessage({
        id: assistantId,
        role: 'assistant',
        content: '',
        timestamp: Date.now(),
        isPending: true,
      })

      chatStream.send(
        {
          channel: 'web',
          user_id: conversationId,
          content_type: 'text',
          text: optionId,
        },
        handleStreamEvent
      )
    },
    [messages, addMessage, chatStream, conversationId, handleStreamEvent]
  )

  const handleSend = async () => {
    const text = input.trim()
    if (!text || chatStream.isStreaming) return

    addMessage({
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      timestamp: Date.now(),
    })
    setInput('')

    const assistantId = crypto.randomUUID()
    addMessage({
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      isPending: true,
    })

    await chatStream.send(
      {
        channel: 'web',
        user_id: conversationId,
        content_type: 'text',
        text,
      },
      handleStreamEvent
    )
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border-subtle flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 text-accent-neural">
            <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z" />
            <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z" />
          </svg>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted">智能问答</h3>
        </div>
        {messages.length > 0 && (
          <button
            onClick={clearMessages}
            className="text-[12px] text-text-muted hover:text-text-primary transition"
          >
            清空对话
          </button>
        )}
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center text-text-muted">
            <div className="w-16 h-16 mb-4 rounded-2xl bg-accent-neural/5 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="w-8 h-8 text-accent-neural/60">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            </div>
            <p className="text-sm font-medium text-text-secondary">基于知识库的智能问答</p>
            <p className="text-xs mt-1.5 text-text-muted">试试问："我们项目用了什么架构？"</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            onIntentSelect={handleIntentSelect}
            streamStatus={chatStream.isStreaming && i === messages.length - 1 && msg.role === 'assistant' ? streamStatus : 'idle'}
          />
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="px-3 pb-3 pt-2 border-t border-border-subtle shrink-0">
        <div className="flex items-end gap-2">
          {/* Voice Button */}
          {voice.isSupported && (
            <button
              onClick={voice.isListening ? voice.stopListening : voice.startListening}
              className={cn(
                'shrink-0 w-9 h-9 rounded-full flex items-center justify-center transition',
                voice.isListening
                  ? 'bg-accent-danger/15 text-accent-danger animate-pulse'
                  : 'bg-bg-elevated text-text-muted hover:text-text-primary hover:bg-bg-hover'
              )}
              title={voice.isListening ? '停止录音' : '语音输入'}
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="23" />
                <line x1="8" y1="23" x2="16" y2="23" />
              </svg>
            </button>
          )}

          {/* Text Input */}
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={voice.isListening ? '正在聆听...' : input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={voice.isListening}
              placeholder={voice.isListening ? '正在聆听...' : '输入问题... (Enter 发送)'}
              className="input text-xs py-2 pr-10 resize-none max-h-[120px]"
              rows={1}
            />
            {/* Send Button */}
            <button
              onClick={handleSend}
              disabled={chatStream.isStreaming || !input.trim() || voice.isListening}
              className="absolute right-2 bottom-1.5 p-1 rounded-md text-text-muted hover:text-accent-neural disabled:opacity-30 disabled:cursor-not-allowed transition"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
