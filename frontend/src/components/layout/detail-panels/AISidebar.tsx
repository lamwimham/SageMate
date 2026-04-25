// ============================================================
// AISidebar — AI 知识助手侧边栏
// ============================================================

import { useState, useCallback, useEffect, useRef } from 'react'
import { useAIAgent, type AIAction } from '@/hooks/useAIAgent'
import { cn } from '@/lib/utils'

interface AISidebarProps {
  isOpen: boolean
  onClose: () => void
  selectedText: string
  fullContent: string
  onAcceptSuggestion: (originalText: string, suggestedText: string) => void
}

const ACTIONS: { id: AIAction; label: string; icon: string; description: string }[] = [
  { id: 'suggest_links', label: '建议关联', icon: '🔗', description: '推荐相关 Wiki 页面' },
  { id: 'explain', label: '解释', icon: '💡', description: '用简单语言解释' },
  { id: 'expand', label: '扩写', icon: '📝', description: '增加细节和背景' },
  { id: 'condense', label: '精简', icon: '✂️', description: '保留核心信息' },
  { id: 'summarize', label: '生成摘要', icon: '📊', description: '1-2 句话摘要' },
]

export function AISidebar({ isOpen, onClose, selectedText, fullContent, onAcceptSuggestion }: AISidebarProps) {
  const { isLoading, error, suggestions, execute, acceptSuggestion, dismissSuggestion } = useAIAgent()
  const [localError, setLocalError] = useState<string | null>(null)
  const sidebarRef = useRef<HTMLDivElement>(null)

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  // Handle click outside
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (isOpen && sidebarRef.current && !sidebarRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [isOpen, onClose])

  const handleAction = useCallback(
    async (action: AIAction) => {
      const text = selectedText || fullContent
      if (!text.trim()) {
        setLocalError('请先选择一段文字')
        setTimeout(() => setLocalError(null), 3000)
        return
      }

      // Extract context: 500 chars before and after selection
      const selectionIndex = fullContent.indexOf(selectedText)
      const contextStart = Math.max(0, selectionIndex - 500)
      const contextEnd = Math.min(fullContent.length, selectionIndex + selectedText.length + 500)
      const context = fullContent.slice(contextStart, contextEnd)

      await execute(action, text, context)
    },
    [selectedText, fullContent, execute]
  )

  const handleAccept = useCallback(
    (index: number) => {
      const suggestion = suggestions[index]
      if (suggestion && suggestion.action === 'suggest_links') {
        // For link suggestions, replace in editor
        onAcceptSuggestion(suggestion.originalText, suggestion.suggestedText)
      }
      acceptSuggestion(index)
      // Auto-dismiss accepted suggestions after 1s
      setTimeout(() => dismissSuggestion(index), 1000)
    },
    [suggestions, acceptSuggestion, dismissSuggestion, onAcceptSuggestion]
  )

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div className="fixed inset-0 bg-black/20 z-40 transition-opacity duration-200" />
      )}

      {/* Sidebar */}
      <div
        ref={sidebarRef}
        className={cn(
          'fixed right-0 top-0 bottom-0 w-80 bg-[#16162a] border-l border-border-subtle z-50',
          'transform transition-transform duration-200 ease-out',
          isOpen ? 'translate-x-0' : 'translate-x-full'
        )}
      >
        {/* Header */}
        <div className="px-4 py-3 border-b border-border-subtle flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm">✨</span>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted">AI 助手</h3>
          </div>
          <button
            onClick={onClose}
            className="text-text-muted hover:text-text-primary transition p-1"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Selected Text Preview */}
          {selectedText && (
            <div>
              <div className="text-[12px] uppercase tracking-wider text-text-muted mb-1.5">选中的文字</div>
              <div className="text-xs text-text-secondary bg-[#1a1a2e] rounded-lg p-2.5 border border-border-subtle line-clamp-3">
                {selectedText}
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div>
            <div className="text-[12px] uppercase tracking-wider text-text-muted mb-2">操作</div>
            <div className="space-y-1.5">
              {ACTIONS.map((action) => (
                <button
                  key={action.id}
                  onClick={() => handleAction(action.id)}
                  disabled={isLoading}
                  className={cn(
                    'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition',
                    isLoading
                      ? 'opacity-50 cursor-not-allowed'
                      : 'hover:bg-bg-hover/50'
                  )}
                >
                  <span className="text-base">{action.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-text-primary">{action.label}</div>
                    <div className="text-[12px] text-text-muted">{action.description}</div>
                  </div>
                  {isLoading && (
                    <div className="w-3 h-3 border border-accent-neural border-t-transparent rounded-full animate-spin" />
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Error */}
          {(error || localError) && (
            <div className="text-xs text-red-400 bg-red-900/10 rounded-lg p-2.5 border border-red-800/20">
              {error || localError}
            </div>
          )}

          {/* Suggestions */}
          {suggestions.length > 0 && (
            <div>
              <div className="text-[12px] uppercase tracking-wider text-text-muted mb-2">建议</div>
              <div className="space-y-3">
                {suggestions.map((s, index) => (
                  <SuggestionCard
                    key={index}
                    suggestion={s}
                    onAccept={() => handleAccept(index)}
                    onDismiss={() => dismissSuggestion(index)}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  )
}

// ── Suggestion Card ─────────────────────────────────────────────

function SuggestionCard({
  suggestion,
  onAccept,
  onDismiss,
}: {
  suggestion: { originalText: string; suggestedText: string; action: AIAction; accepted: boolean }
  onAccept: () => void
  onDismiss: () => void
}) {
  if (suggestion.accepted) {
    return (
      <div className="text-xs text-text-muted bg-bg-elevated/30 rounded-lg p-2.5 border border-border-subtle/50">
        ✅ 已接受建议
      </div>
    )
  }

  return (
    <div className="bg-[#1a1a2e] rounded-lg border border-border-subtle overflow-hidden">
      {/* Original */}
      <div className="px-3 py-2 border-b border-border-subtle/50">
        <div className="text-[12px] text-text-muted mb-1">原文</div>
        <div className="text-xs text-text-secondary line-clamp-2">{suggestion.originalText}</div>
      </div>
      {/* Suggestion */}
      <div className="px-3 py-2">
        <div className="text-[12px] text-accent-neural mb-1">建议</div>
        <div className="text-xs text-text-primary line-clamp-4">{suggestion.suggestedText}</div>
      </div>
      {/* Actions */}
      <div className="px-3 py-2 border-t border-border-subtle/50 flex items-center gap-2">
        <button
          onClick={onAccept}
          className="text-[12px] px-2.5 py-1 rounded bg-accent-neural/10 text-accent-neural hover:bg-accent-neural/20 transition"
        >
          接受
        </button>
        <button
          onClick={onDismiss}
          className="text-[12px] px-2.5 py-1 rounded text-text-muted hover:text-text-primary transition"
        >
          忽略
        </button>
      </div>
    </div>
  )
}
