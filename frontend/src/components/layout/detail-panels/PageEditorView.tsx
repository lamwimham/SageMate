import { useCallback, useEffect, useState } from 'react'
import CodeMirror from '@uiw/react-codemirror'
import { markdown, markdownLanguage } from '@codemirror/lang-markdown'
import { EditorView } from '@codemirror/view'
import { useEditorStore } from '@/stores/editor'
import { useWikiPagesStore } from '@/stores/wikiPages'
import { wikilinkAutocomplete, wikilinkHighlight } from './wikilink-autocomplete'
import { MetadataBar, PageMetadata } from './MetadataBar'
import { AISidebar } from './AISidebar'
import { createAutoPairExtension } from './autopair'
import { livePreviewPlugin } from './live-preview'
import { autoLineBreak } from './auto-line-break'

// ── Editor Component ───────────────────────────────────────────

interface PageEditorViewProps {
  initialContent: string
  initialMetadata: PageMetadata
  onSave: (content: string, metadata?: Partial<PageMetadata>) => Promise<void>
  onCancel: () => void
  pageSlug?: string
}

export function PageEditorView({ initialContent, initialMetadata, onSave, onCancel, pageSlug }: PageEditorViewProps) {
  const { updateContent, content: storeContent, pageSlug: storeSlug, setPageSlug, isSaving, saveError, setSaving, setSaveError, saveDraft } = useEditorStore()
  const { pages, fetchPages } = useWikiPagesStore()
  // Restore from store only if it belongs to this page
  const initial = storeContent && storeSlug === pageSlug ? storeContent : initialContent
  const [localContent, setLocalContent] = useState(initial)
  const [metadata, setMetadata] = useState<PageMetadata>(initialMetadata)
  const [isAISidebarOpen, setIsAISidebarOpen] = useState(false)
  const [selectedText, setSelectedText] = useState('')
  const [hasChanges, setHasChanges] = useState(false)
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null)

  // Pre-fetch wiki pages for autocomplete
  useEffect(() => {
    fetchPages()
  }, [fetchPages])

  // Initialize content
  useEffect(() => {
    setLocalContent(initialContent)
    setHasChanges(false)
    setLastSavedAt(null)
  }, [initialContent])

  // Register page slug in store on mount, so content can be restored across tab switches
  useEffect(() => {
    if (pageSlug && storeSlug !== pageSlug) {
      setPageSlug(pageSlug)
    }
  }, [pageSlug, storeSlug, setPageSlug])

  // Auto-save draft every 30s
  useEffect(() => {
    const interval = setInterval(() => {
      if (localContent && localContent !== initialContent) {
        saveDraft()
      }
    }, 30000)
    return () => clearInterval(interval)
  }, [localContent, initialContent, saveDraft])

  // Keyboard shortcut: Cmd+S / Ctrl+S to save
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault()
        handleSave()
      }
      if (e.key === 'Escape') {
        if (!isSaving) {
          if (isAISidebarOpen) {
            setIsAISidebarOpen(false)
          } else {
            onCancel()
          }
        }
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [localContent, metadata, isSaving, isAISidebarOpen, onCancel])

  const handleSave = useCallback(async () => {
    if (isSaving || !localContent.trim()) return

    setSaving(true)
    setSaveError(null)

    try {
      await onSave(localContent, metadata)
      setLastSavedAt(new Date())
      setHasChanges(false)
    } catch (error) {
      setSaveError('保存失败，草稿已保留')
      setTimeout(() => setSaveError(null), 3000)
    } finally {
      setSaving(false)
    }
  }, [localContent, metadata, isSaving, onSave, setSaving, setSaveError])

  const handleChange = useCallback((value: string) => {
    setLocalContent(value)
    updateContent(value)
    setHasChanges(true)
  }, [updateContent])

  const handleMetadataChange = useCallback((partial: Partial<PageMetadata>) => {
    setMetadata((prev) => ({ ...prev, ...partial }))
  }, [])

  const handleAcceptSuggestion = useCallback((originalText: string, suggestedText: string) => {
    setLocalContent((prev) => {
      const updated = prev.replace(originalText, suggestedText)
      updateContent(updated)
      return updated
    })
  }, [updateContent])

  // Build completion items from wiki pages
  const completionPages = pages.map((p) => ({
    slug: p.slug,
    title: p.title,
    category: p.category,
    summary: p.summary,
    isLinked: localContent.includes(`[[${p.slug}]]`),
  }))

  // Editor footer status text
  const renderStatusText = () => {
    if (isSaving) return <span className="editor-footer__save-status editor-footer__save-status--saving">保存中...</span>
    if (saveError) return <span className="editor-footer__save-status editor-footer__save-status--error">{saveError}</span>
    if (lastSavedAt) {
      const t = lastSavedAt.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
      return <span className="editor-footer__save-status editor-footer__save-status--saved">已保存 {t}</span>
    }
    if (hasChanges) return <span className="editor-footer__save-status">未保存</span>
    return null
  }

  return (
    <div className="flex flex-col h-full bg-bg-deep relative">
      {/* Metadata Bar — 可折叠属性面板 */}
      <MetadataBar
        metadata={metadata}
        onChange={handleMetadataChange}
        categories={['entity', 'concept', 'analysis', 'source', 'note']}
      />

      {/* Editor Area */}
      <div className="flex-1 overflow-hidden cm-editor-themed">
        <CodeMirror
          value={localContent}
          height="100%"
          theme="dark"
          extensions={[
            markdown({ base: markdownLanguage }),
            EditorView.lineWrapping,
            wikilinkAutocomplete(completionPages),
            wikilinkHighlight(),
            createAutoPairExtension(),
            livePreviewPlugin,
            autoLineBreak,
          ]}
          onChange={handleChange}
          className="text-sm"
          basicSetup={{
            lineNumbers: false,
            foldGutter: false,
            dropCursor: false,
            allowMultipleSelections: false,
            indentOnInput: true,
            bracketMatching: true,
            closeBrackets: true,
            autocompletion: false,
            rectangularSelection: false,
            crosshairCursor: false,
            highlightActiveLine: false,
            highlightActiveLineGutter: false,
            highlightSelectionMatches: false,
            syntaxHighlighting: true,
            tabSize: 2,
          }}
        />
      </div>

      {/* Editor Footer */}
      <div className="editor-footer">
        <span>{localContent.length} 字符 · {localContent.split(/\n+/).filter(Boolean).length} 行</span>
        <div className="flex items-center gap-3">
          {renderStatusText()}
        </div>
      </div>

      {/* AI Floating Button — above footer */}
      <button
        onClick={() => {
          const selection = window.getSelection()
          const text = selection?.toString().trim() || ''
          setSelectedText(text)
          setIsAISidebarOpen(true)
        }}
        className="absolute bottom-10 right-4 w-10 h-10 rounded-full bg-[#2a2a4a] border border-border-subtle flex items-center justify-center text-base hover:bg-[#3b3b6b] hover:border-accent-neural/30 transition shadow-lg z-30"
        title="AI 助手"
      >
        ✨
      </button>

      {/* AI Sidebar */}
      <AISidebar
        isOpen={isAISidebarOpen}
        onClose={() => setIsAISidebarOpen(false)}
        selectedText={selectedText}
        fullContent={localContent}
        onAcceptSuggestion={handleAcceptSuggestion}
      />
    </div>
  )
}
