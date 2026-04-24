import { useCallback, useEffect, useState } from 'react'
import CodeMirror from '@uiw/react-codemirror'
import { markdown, markdownLanguage } from '@codemirror/lang-markdown'
import { useEditorStore } from '@/stores/editor'
import { useWikiPagesStore } from '@/stores/wikiPages'
import { wikilinkAutocomplete, wikilinkHighlight } from './wikilink-autocomplete'
import { MetadataBar, PageMetadata } from './MetadataBar'
import { AISidebar } from './AISidebar'

// ── Editor Component ───────────────────────────────────────────

interface PageEditorViewProps {
  initialContent: string
  initialMetadata: PageMetadata
  onSave: (content: string, metadata?: Partial<PageMetadata>) => Promise<void>
  onCancel: () => void
}

export function PageEditorView({ initialContent, initialMetadata, onSave, onCancel }: PageEditorViewProps) {
  const { updateContent, isSaving, saveError, setSaving, setSaveError, saveDraft } = useEditorStore()
  const { pages, fetchPages } = useWikiPagesStore()
  const [localContent, setLocalContent] = useState(initialContent)
  const [metadata, setMetadata] = useState<PageMetadata>(initialMetadata)
  const [isAISidebarOpen, setIsAISidebarOpen] = useState(false)
  const [selectedText, setSelectedText] = useState('')

  // Pre-fetch wiki pages for autocomplete
  useEffect(() => {
    fetchPages()
  }, [fetchPages])

  // Initialize content
  useEffect(() => {
    setLocalContent(initialContent)
  }, [initialContent])

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
  }, [updateContent])

  const handleMetadataChange = useCallback((partial: Partial<PageMetadata>) => {
    setMetadata((prev) => ({ ...prev, ...partial }))
  }, [])

  const handleAcceptSuggestion = useCallback((originalText: string, suggestedText: string) => {
    setLocalContent((prev) => prev.replace(originalText, suggestedText))
    updateContent(localContent.replace(originalText, suggestedText))
  }, [localContent, updateContent])

  // Build completion items from wiki pages
  const completionPages = pages.map((p) => ({
    slug: p.slug,
    title: p.title,
    category: p.category,
    summary: p.summary,
    isLinked: localContent.includes(`[[${p.slug}]]`),
  }))

  return (
    <div className="flex flex-col h-full bg-[#1a1a2e] relative">
      {/* Metadata Bar */}
      <MetadataBar
        metadata={metadata}
        onChange={handleMetadataChange}
        categories={['entity', 'concept', 'analysis', 'source']}
      />

      {/* Editor Area */}
      <div className="flex-1 overflow-hidden">
        <CodeMirror
          value={localContent}
          height="100%"
          theme="dark"
          extensions={[
            markdown({ base: markdownLanguage }),
            wikilinkAutocomplete(completionPages),
            wikilinkHighlight(),
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

      {/* AI Floating Button */}
      <button
        onClick={() => {
          // Capture current text selection from the editor area
          const selection = window.getSelection()
          const text = selection?.toString().trim() || ''
          setSelectedText(text)
          setIsAISidebarOpen(true)
        }}
        className="absolute bottom-4 right-4 w-10 h-10 rounded-full bg-[#2a2a4a] border border-border-subtle flex items-center justify-center text-base hover:bg-[#3b3b6b] hover:border-accent-neural/30 transition shadow-lg z-30"
        title="AI 助手"
      >
        ✨
      </button>

      {/* Save Error Banner */}
      {saveError && (
        <div className="px-4 py-2 bg-red-900/20 border-t border-red-800/30 text-red-400 text-xs animate-fade-up">
          {saveError}
        </div>
      )}

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
