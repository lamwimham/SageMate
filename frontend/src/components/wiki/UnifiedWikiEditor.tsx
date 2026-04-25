import { useState, useCallback, useEffect } from 'react'
import CodeMirror from '@uiw/react-codemirror'
import { markdown, markdownLanguage } from '@codemirror/lang-markdown'
import { EditorView } from '@codemirror/view'
import { useWikiPagesStore } from '@/stores/wikiPages'
import { wikilinkAutocomplete, wikilinkHighlight } from '@/components/layout/detail-panels/wikilink-autocomplete'
import { createAutoPairExtension } from '@/components/layout/detail-panels/autopair'
import { livePreviewPlugin } from '@/components/layout/detail-panels/live-preview'
import { autoLineBreak } from '@/components/layout/detail-panels/auto-line-break'
import { MarkdownRenderer } from '@/components/markdown/MarkdownRenderer'

interface UnifiedWikiEditorProps {
  /** 页面标题 */
  title: string
  /** 页面内容 */
  content: string
  /** 页面分类 */
  category: string
  /** 是否默认进入编辑态 */
  defaultEditing?: boolean
  /** 保存回调 */
  onSave: (content: string) => Promise<void>
  /** 内容变化回调 */
  onContentChange?: (content: string) => void
  /** 进入编辑态回调（用于设置 originalBody） */
  onEditStart?: (body: string) => void
  /** 底部额外信息 */
  footerInfo?: React.ReactNode
}

/**
 * 统一的 Wiki 编辑器/阅读器
 * - 支持编辑态和阅读态切换
 * - 新增 note 默认编辑态
 * - 已有 page 默认阅读态
 */
export function UnifiedWikiEditor({
  title,
  content,
  category,
  defaultEditing = false,
  onSave,
  onContentChange,
  onEditStart,
  footerInfo,
}: UnifiedWikiEditorProps) {
  const [isEditing, setIsEditing] = useState(defaultEditing)
  const [editContent, setEditContent] = useState(content)
  const [isSaving, setIsSaving] = useState(false)
  const [hasChanges, setHasChanges] = useState(false)
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null)

  const { pages, fetchPages } = useWikiPagesStore()

  useEffect(() => {
    fetchPages()
  }, [fetchPages])

  // Parse frontmatter to get the body part
  const parseFrontmatter = (full: string): { body: string; hasFrontmatter: boolean } => {
    const match = full.match(/^---\s*\n[\s\S]*?\n---\s*\n([\s\S]*)$/)
    if (match) return { body: match[1], hasFrontmatter: true }
    return { body: full, hasFrontmatter: false }
  }

  // 当外部 content 变化时同步（用于已有页面加载后）
  useEffect(() => {
    const { body } = parseFrontmatter(content)
    setEditContent(body)
  }, [content])

  const handleToggle = useCallback(() => {
    if (isEditing) {
      // 从编辑切换到阅读：如果有变化先保存
      if (hasChanges && editContent.trim()) {
        handleSave()
      }
      setIsEditing(false)
    } else {
      // 从阅读切换到编辑
      const { body } = parseFrontmatter(content)
      setEditContent(body)
      setIsEditing(true)
      onEditStart?.(body)
    }
  }, [isEditing, hasChanges, editContent, content, onEditStart])

  const handleSave = useCallback(async () => {
    if (isSaving || !editContent.trim()) return
    setIsSaving(true)
    try {
      await onSave(editContent)
      setLastSavedAt(new Date())
      setHasChanges(false)
      setIsEditing(false)
    } catch {
      // 保存失败保持编辑态
    } finally {
      setIsSaving(false)
    }
  }, [editContent, isSaving, onSave])

  const handleContentChange = useCallback((value: string) => {
    setEditContent(value)
    setHasChanges(true)
    onContentChange?.(value)
  }, [onContentChange])

  // 键盘快捷键
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault()
        if (isEditing && hasChanges) {
          handleSave()
        }
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isEditing, hasChanges, handleSave])

  const completionPages = pages.map((p) => ({
    slug: p.slug,
    title: p.title,
    category: p.category,
    summary: p.summary,
    isLinked: editContent.includes(`[[${p.slug}]]`),
  }))

  // 预览/编辑切换按钮
  const ToggleButton = () => (
    <button
      onClick={handleToggle}
      className="p-1.5 rounded-md text-text-muted hover:text-accent-neural hover:bg-bg-hover transition cursor-pointer"
      aria-label={isEditing ? '切换预览' : '切换编辑'}
      title={isEditing ? '切换预览' : '切换编辑'}
    >
      {isEditing ? (
        // 预览图标（眼睛）
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
          <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
          <circle cx="12" cy="12" r="3" />
        </svg>
      ) : (
        // 编辑图标（铅笔）
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
          <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
          <path d="m15 5 4 4" />
        </svg>
      )}
    </button>
  )

  // 状态文本
  const renderStatusText = () => {
    if (isSaving) return <span className="editor-footer__save-status editor-footer__save-status--saving">保存中...</span>
    if (lastSavedAt) {
      const t = lastSavedAt.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
      return <span className="editor-footer__save-status editor-footer__save-status--saved">已保存 {t}</span>
    }
    if (hasChanges) return <span className="editor-footer__save-status">未保存</span>
    return null
  }

  return (
    <div className="flex flex-col h-full relative">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-1.5 border-b border-border-subtle shrink-0 bg-bg-surface">
        {/* 左侧：wiki 类型标签 */}
        <span className="text-[12px] px-1.5 py-0.5 rounded-full bg-accent-neural/12 text-accent-neural font-medium shrink-0">
          {category}
        </span>

        {/* 中间：标题（有就显示） */}
        {title && (
          <span className="text-sm font-medium text-text-primary mx-2 truncate">
            {title}
          </span>
        )}

        {/* 右侧：预览/编辑切换按钮 */}
        <div className="flex items-center gap-2 shrink-0">
          <ToggleButton />
        </div>
      </div>

      {/* Content Area */}
      {isEditing ? (
        <div className="flex-1 overflow-hidden cm-editor-themed">
          <CodeMirror
            value={editContent}
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
      ) : (
        <div className="flex-1 overflow-y-auto py-4">
          <div className="page-content">
            <div className="markdown-body text-sm text-text-primary">
              {content ? (
                <MarkdownRenderer content={content} existingSlugs={pages.map(p => p.slug)} />
              ) : (
                <div className="flex items-center justify-center h-full text-text-muted">
                  <span className="text-xs">开始输入内容</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="editor-footer">
        <span>{editContent.length} 字符 · Cmd+S 保存</span>
        <div className="flex items-center gap-3">
          {footerInfo}
          {renderStatusText()}
        </div>
      </div>
    </div>
  )
}
