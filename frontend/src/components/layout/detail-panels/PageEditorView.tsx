import { useCallback, useEffect, useState } from 'react'
import CodeMirror from '@uiw/react-codemirror'
import { markdown, markdownLanguage } from '@codemirror/lang-markdown'
import { useEditorStore } from '@/stores/editor'

// ── Editor Component ───────────────────────────────────────────

interface PageEditorViewProps {
  initialContent: string
  onSave: (content: string) => Promise<void>
  onCancel: () => void
}

export function PageEditorView({ initialContent, onSave, onCancel }: PageEditorViewProps) {
  const { updateContent, isSaving, saveError, setSaving, setSaveError, saveDraft } = useEditorStore()
  const [localContent, setLocalContent] = useState(initialContent)

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
        // Only cancel if not in the middle of saving
        if (!isSaving) {
          onCancel()
        }
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [localContent, isSaving])

  const handleSave = useCallback(async () => {
    if (isSaving || !localContent.trim()) return

    setSaving(true)
    setSaveError(null)

    try {
      await onSave(localContent)
      // Success: no notification (silent principle)
    } catch (error) {
      setSaveError('保存失败，草稿已保留')
      // Auto-clear error after 3s
      setTimeout(() => setSaveError(null), 3000)
    } finally {
      setSaving(false)
    }
  }, [localContent, isSaving, onSave, setSaving, setSaveError])

  const handleChange = useCallback((value: string) => {
    setLocalContent(value)
    updateContent(value)
  }, [updateContent])

  return (
    <div className="flex flex-col h-full bg-[#1a1a2e]">
      {/* Editor Area */}
      <div className="flex-1 overflow-hidden">
        <CodeMirror
          value={localContent}
          height="100%"
          theme="dark"
          extensions={[
            markdown({ base: markdownLanguage }),
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
            autocompletion: true,
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

      {/* Save Error Banner */}
      {saveError && (
        <div className="px-4 py-2 bg-red-900/20 border-t border-red-800/30 text-red-400 text-xs animate-fade-up">
          {saveError}
        </div>
      )}
    </div>
  )
}
