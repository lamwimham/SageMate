import { useState, useCallback, useEffect, useRef } from 'react'
import CodeMirror from '@uiw/react-codemirror'
import { markdown, markdownLanguage } from '@codemirror/lang-markdown'
import { EditorView } from '@codemirror/view'
import { useWikiPagesStore } from '@/stores/wikiPages'
import { useWikiTabsStore } from '@/stores/wikiTabs'
import { wikilinkAutocomplete, wikilinkHighlight } from '@/components/layout/detail-panels/wikilink-autocomplete'
import { createAutoPairExtension } from '@/components/layout/detail-panels/autopair'
import { livePreviewPlugin } from '@/components/layout/detail-panels/live-preview'
import { MarkdownRenderer } from '@/components/markdown/MarkdownRenderer'
import { ViewToggle } from '@/components/wiki/ViewToggle'
import { useCreatePage } from '@/hooks/useWiki'
import type { WikiPageCreate } from '@/types'
import { cn } from '@/lib/utils'

interface NoteEditorProps {
  /** Tab key (e.g. 'note:1713945600000') */
  tabKey: string
  initialTitle?: string
}

/**
 * Note Editor — 空白 Markdown 编辑器，用于创建新笔记。
 * 保存到后端后，通过 upgradeNoteTab 将 tab 升级为 page 类型。
 */
export function NoteEditor({ tabKey, initialTitle }: NoteEditorProps) {
  const [title, setTitle] = useState(initialTitle || '')
  const [content, setContent] = useState('')
  const [saving, setSaving] = useState(false)
  const titleRef = useRef<HTMLInputElement>(null)

  const createMutation = useCreatePage()
  const { pages, fetchPages } = useWikiPagesStore()
  const { upgradeNoteTab } = useWikiTabsStore()

  useEffect(() => {
    fetchPages()
  }, [fetchPages])

  // Auto-focus title on mount
  useEffect(() => {
    titleRef.current?.focus()
  }, [])

  const [isPreview, setIsPreview] = useState(false)
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null)
  const [hasChanges, setHasChanges] = useState(false)

  const handleSave = useCallback(async () => {
    if (saving || !title.trim() || !content.trim()) return
    setSaving(true)

    const slug = title.trim().toLowerCase()
      .replace(/[^\w\u4e00-\u9fa5\s-]/g, '')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-')

    const data: WikiPageCreate = {
      slug,
      title: title.trim(),
      category: 'note',
      content: content.trim(),
      tags: [],
      sources: [],
      outbound_links: [],
    }

    try {
      const res = await createMutation.mutateAsync(data)
      // Upgrade the tab from note -> page
      upgradeNoteTab(tabKey, res.slug, title.trim())
      setLastSavedAt(new Date())
      setHasChanges(false)
    } catch {
      setSaving(false)
    }
  }, [title, content, saving, tabKey, createMutation, upgradeNoteTab])

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault()
        handleSave()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [title, content, saving, handleSave])

  const handleToggle = useCallback(() => {
    if (isPreview) {
      setIsPreview(false)
    } else {
      if (title.trim() && content.trim() && !saving) {
        handleSave()
      } else {
        setIsPreview(true)
      }
    }
  }, [isPreview, title, content, saving, handleSave])

  const handleContentChange = useCallback((value: string) => {
    setContent(value)
    setHasChanges(true)
  }, [])

  const completionPages = pages.map((p) => ({
    slug: p.slug,
    title: p.title,
    category: p.category,
    summary: p.summary,
    isLinked: content.includes(`[[${p.slug}]]`),
  }))

  // Footer status
  const renderStatusText = () => {
    if (saving) return <span className="editor-footer__save-status editor-footer__save-status--saving">保存中...</span>
    if (lastSavedAt) {
      const t = lastSavedAt.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
      return <span className="editor-footer__save-status editor-footer__save-status--saved">已保存 {t}</span>
    }
    if (hasChanges) return <span className="editor-footer__save-status">未保存</span>
    return null
  }

  return (
    <div className="flex flex-col h-full bg-bg-deep relative">
      {/* Title Bar */}
      <div className="flex items-center gap-3 px-5 py-3 border-b border-border-subtle shrink-0">
        <input
          ref={titleRef}
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="笔记标题..."
          disabled={isPreview}
          className={cn(
            "flex-1 bg-transparent text-base font-semibold text-text-primary outline-none placeholder:text-text-muted",
            isPreview && "cursor-default pointer-events-none"
          )}
        />
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent-growth/12 text-accent-growth font-medium">
            笔记
          </span>
          <ViewToggle mode={isPreview ? 'preview' : 'edit'} onToggle={handleToggle} />
          {!isPreview && (
            <button
              onClick={handleSave}
              disabled={saving || !title.trim() || !content.trim()}
              className="btn btn-primary text-xs disabled:opacity-50"
            >
              {saving ? '保存中...' : '保存'}
            </button>
          )}
        </div>
      </div>

      {/* Content Area */}
      {isPreview ? (
        <div className="flex-1 overflow-y-auto px-6 py-4 markdown-body text-sm text-text-primary">
          <div className="page-content">
            {content ? (
              <MarkdownRenderer content={content} />
            ) : (
              <div className="flex items-center justify-center h-full text-text-muted">
                <span className="text-xs">点击顶部铅笔图标开始编辑</span>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-hidden cm-editor-themed">
          <CodeMirror
            value={content}
            height="100%"
            theme="dark"
            extensions={[
              markdown({ base: markdownLanguage }),
              EditorView.lineWrapping,
              wikilinkAutocomplete(completionPages),
              wikilinkHighlight(),
              createAutoPairExtension(),
              livePreviewPlugin,
            ]}
            onChange={handleContentChange}
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
      )}

      {/* Editor Footer */}
      <div className="editor-footer">
        <span>{content.length} 字符 · Cmd+S 保存</span>
        <div className="flex items-center gap-3">
          {renderStatusText()}
        </div>
      </div>
    </div>
  )
}
