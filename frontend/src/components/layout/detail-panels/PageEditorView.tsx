import { useCallback, useEffect, useState, useMemo, useRef } from 'react'
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

// ── Frontmatter Helpers ────────────────────────────────────────

/** Extract YAML frontmatter and body from content. */
function parseFrontmatter(content: string): { frontmatter: string; body: string } {
  const match = content.match(/^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/)
  if (!match) return { frontmatter: '', body: content }
  return { frontmatter: match[1], body: match[2] }
}

/** Reconstruct full content with frontmatter from metadata + body. */
function buildContent(metadata: PageMetadata, body: string): string {
  const fm = [
    `---`,
    `title: "${metadata.title}"`,
    `category: ${metadata.category}`,
    `tags: ${JSON.stringify(metadata.tags || [])}`,
    `outbound_links: []`,
    `sources: ${JSON.stringify(metadata.sources || [])}`,
    `---`,
  ].join('\n')
  const cleanBody = body.replace(/^(\n)*/, '')
  return fm + '\n\n' + cleanBody
}

// ── Editor Component ───────────────────────────────────────────

interface PageEditorViewProps {
  initialContent: string
  initialMetadata: PageMetadata
  onSave: (content: string, metadata?: Partial<PageMetadata>) => Promise<void>
  onCancel: () => void
  pageSlug?: string
  /** When true, hide the metadata bar (used when editing existing pages). */
  hideMetadata?: boolean
  /** Callback invoked whenever editor content changes. */
  onContentChange?: (bodyContent: string) => void
}

export function PageEditorView({ initialContent, initialMetadata, onSave, onCancel, pageSlug, hideMetadata, onContentChange }: PageEditorViewProps) {
  const { updateContent, pageSlug: storeSlug, setPageSlug, isSaving, saveError, setSaving, setSaveError, saveDraft } = useEditorStore()
  const { pages, fetchPages } = useWikiPagesStore()

  // Parse frontmatter on mount — only show body content in editor
  const parsed = useMemo(() => parseFrontmatter(initialContent), [initialContent])
  const [bodyContent, setBodyContent] = useState(parsed.body)
  const [metadata, setMetadata] = useState<PageMetadata>(initialMetadata)
  const [isAISidebarOpen, setIsAISidebarOpen] = useState(false)
  const [selectedText, setSelectedText] = useState('')
  const [hasChanges, setHasChanges] = useState(false)
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null)
  const saveErrorTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (saveErrorTimerRef.current) clearTimeout(saveErrorTimerRef.current)
    }
  }, [])

  // Pre-fetch wiki pages for autocomplete
  useEffect(() => {
    fetchPages()
  }, [fetchPages])

  // Initialize content
  useEffect(() => {
    const p = parseFrontmatter(initialContent)
    setBodyContent(p.body)
    setHasChanges(false)
    setLastSavedAt(null)
  }, [initialContent])

  // Sync metadata when initialMetadata changes
  useEffect(() => {
    setMetadata(initialMetadata)
  }, [initialMetadata])

  // Register page slug in store on mount, so content can be restored across tab switches
  useEffect(() => {
    if (pageSlug && storeSlug !== pageSlug) {
      setPageSlug(pageSlug)
    }
  }, [pageSlug, storeSlug, setPageSlug])

  // Auto-save draft every 30s
  useEffect(() => {
    const interval = setInterval(() => {
      if (bodyContent && bodyContent !== parsed.body) {
        saveDraft()
      }
    }, 30000)
    return () => clearInterval(interval)
  }, [bodyContent, parsed.body, saveDraft])

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
  }, [bodyContent, metadata, isSaving, isAISidebarOpen, onCancel])

  const handleSave = useCallback(async () => {
    if (isSaving || !bodyContent.trim()) return

    setSaving(true)
    setSaveError(null)

    // Reconstruct full content with frontmatter
    const fullContent = buildContent(metadata, bodyContent)

    try {
      await onSave(fullContent, metadata)
      setLastSavedAt(new Date())
      setHasChanges(false)
    } catch (error) {
      setSaveError('保存失败，草稿已保留')
      if (saveErrorTimerRef.current) clearTimeout(saveErrorTimerRef.current)
      saveErrorTimerRef.current = setTimeout(() => setSaveError(null), 3000)
    } finally {
      setSaving(false)
    }
  }, [bodyContent, metadata, isSaving, onSave, setSaving, setSaveError])

  const handleChange = useCallback((value: string) => {
    setBodyContent(value)
    updateContent(value)
    setHasChanges(true)
    onContentChange?.(value)
  }, [updateContent, onContentChange])

  const handleMetadataChange = useCallback((partial: Partial<PageMetadata>) => {
    setMetadata((prev) => ({ ...prev, ...partial }))
  }, [])

  const handleAcceptSuggestion = useCallback((originalText: string, suggestedText: string) => {
    setBodyContent((prev) => {
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
    isLinked: bodyContent.includes(`[[${p.slug}]]`),
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
      {/* Metadata Bar — 可折叠属性面板 (hidden when editing existing pages) */}
      {!hideMetadata && (
        <MetadataBar
          metadata={metadata}
          onChange={handleMetadataChange}
          categories={['entity', 'concept', 'analysis', 'source', 'note']}
        />
      )}

      {/* Editor Area */}
      <div className="flex-1 overflow-hidden cm-editor-themed">
        <CodeMirror
          value={bodyContent}
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
        <span>{bodyContent.length} 字符 · {bodyContent.split(/\n+/).filter(Boolean).length} 行</span>
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
        className="absolute bottom-10 right-4 w-10 h-10 rounded-full bg-[#2a2a4a] border border-border-subtle flex items-center justify-center hover:bg-[#3b3b6b] hover:border-accent-neural/30 transition shadow-lg z-30"
        title="AI 助手"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5 text-accent-neural">
          <path d="M12 2L9.5 8.5 2 9.5 7.5 14 6 22 12 18.5 18 22 16.5 14 22 9.5 14.5 8.5z" />
        </svg>
      </button>

      {/* AI Sidebar */}
      <AISidebar
        isOpen={isAISidebarOpen}
        onClose={() => setIsAISidebarOpen(false)}
        selectedText={selectedText}
        fullContent={bodyContent}
        onAcceptSuggestion={handleAcceptSuggestion}
      />
    </div>
  )
}
