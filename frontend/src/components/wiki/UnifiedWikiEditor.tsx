import { useState, useCallback, useEffect, useRef } from 'react'
import CodeMirror from '@uiw/react-codemirror'
import { markdown, markdownLanguage } from '@codemirror/lang-markdown'
import { EditorView } from '@codemirror/view'
import { useWikiPagesStore } from '@/stores/wikiPages'
import { wikilinkAutocomplete, wikilinkHighlight } from '@/components/layout/detail-panels/wikilink-autocomplete'
import { createAutoPairExtension } from '@/components/layout/detail-panels/autopair'
import { livePreviewPlugin } from '@/components/layout/detail-panels/live-preview'
import { autoLineBreak } from '@/components/layout/detail-panels/auto-line-break'
import { MarkdownRenderer } from '@/components/markdown/MarkdownRenderer'
import { useCodeMirrorLifecycle } from '@/hooks/useCodeMirrorLifecycle'

interface UnifiedWikiEditorProps {
  /** 页面唯一标识（用于内存治理） */
  tabKey: string
  /** 页面标题 */
  title: string
  /** 页面内容（不含 frontmatter 的 body） */
  content: string
  /** 页面分类 */
  category: string
  /** 是否默认进入编辑态 */
  defaultEditing?: boolean
  /** 保存回调 — 只传 body */
  onSave: (bodyContent: string) => Promise<void>
  /** 内容变化回调 — 只传 body */
  onContentChange?: (body: string) => void
  /** 进入编辑态回调（用于设置 originalBody） */
  onEditStart?: (body: string) => void
  /** 底部额外信息 */
  footerInfo?: React.ReactNode
}

/**
 * 统一的 Wiki 编辑器/阅读器 — 接入内存治理架构
 *
 * 内存治理要点：
 * 1. CodeMirror 实例注册到 MemoryGovernor，卸载时强制销毁
 * 2. 编辑/阅读切换时，编辑态销毁 CodeMirror，阅读态销毁渲染缓存
 * 3. 非活跃标签页自动冻结（由父组件控制）
 *
 * 状态机：
 *   IDLE → EDITING (点击编辑按钮)
 *   EDITING → PREVIEW (点击预览按钮 / Cmd+S 保存)
 *   EDITING → EDITING (保存失败，保持编辑态)
 */
export function UnifiedWikiEditor({
  tabKey,
  title,
  content,
  category,
  defaultEditing = false,
  onSave,
  onContentChange,
  onEditStart,
  footerInfo,
}: UnifiedWikiEditorProps) {
  const [mode, setMode] = useState<'preview' | 'editing'>(defaultEditing ? 'editing' : 'preview')
  const [editContent, setEditContent] = useState(content)
  const [isSaving, setIsSaving] = useState(false)
  const [hasChanges, setHasChanges] = useState(false)
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null)
  const isTransitioning = useRef(false)

  const { pages, fetchPages } = useWikiPagesStore()

  // 接入内存治理 — 编辑器生命周期管理
  const { setView } = useCodeMirrorLifecycle({
    tabKey,
    content: editContent,
  })

  useEffect(() => {
    fetchPages()
  }, [fetchPages])

  // 当外部 content 变化时同步（只在预览态同步，编辑态不覆盖用户输入）
  useEffect(() => {
    if (mode === 'preview') {
      setEditContent(content)
    }
  }, [content, mode])

  // 状态机：切换到编辑态
  const enterEditing = useCallback(() => {
    if (isTransitioning.current) return
    isTransitioning.current = true
    setEditContent(content)  // content 已经是 body
    setMode('editing')
    setHasChanges(false)
    onEditStart?.(content)
    setTimeout(() => { isTransitioning.current = false }, 100)
  }, [content, onEditStart])

  // 状态机：切换到预览态（只切换，不保存）
  const enterPreview = useCallback(() => {
    if (isTransitioning.current) return
    isTransitioning.current = true
    setMode('preview')
    setTimeout(() => { isTransitioning.current = false }, 100)
  }, [])

  // 切换按钮统一入口
  const handleToggle = useCallback(() => {
    if (mode === 'editing') {
      enterPreview()
    } else {
      enterEditing()
    }
  }, [mode, enterPreview, enterEditing])

  const handleContentChange = useCallback((value: string) => {
    setEditContent(value)
    setHasChanges(true)
    onContentChange?.(value)
  }, [onContentChange])

  // 键盘快捷键 — 只在编辑态注册，避免多个实例重复监听
  useEffect(() => {
    if (mode !== 'editing') return
    const handleKeyDown = async (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault()
        if (hasChanges && editContent.trim()) {
          setIsSaving(true)
          try {
            await onSave(editContent)
            setLastSavedAt(new Date())
            setHasChanges(false)
          } catch {
            // 保存失败，保持编辑态
          } finally {
            setIsSaving(false)
          }
        }
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [mode, hasChanges, editContent, onSave])

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
      aria-label={mode === 'editing' ? '切换预览' : '切换编辑'}
      title={mode === 'editing' ? '切换预览' : '切换编辑'}
    >
      {mode === 'editing' ? (
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
    <div className="flex flex-col h-full bg-bg-deep relative">
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

      {/* Content Area — 条件渲染确保编辑/预览互斥，内存不共存 */}
      {mode === 'editing' ? (
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
            onCreateEditor={(view) => setView(view)}
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


