import { useState, useCallback, useEffect } from 'react'
import { useLocation } from '@tanstack/react-router'
import { usePage, useSavePageContent } from '@/hooks/useWiki'
import { Badge } from '@/components/ui/Badge'
import { SkeletonText } from '@/components/ui/Skeleton'
import { MarkdownRenderer } from '@/components/markdown/MarkdownRenderer'
import { PageEditorView } from './PageEditorView'
import { PageMetadata } from './MetadataBar'

import { useWikiPagesStore } from '@/stores/wikiPages'

/**
 * 通用页面详情面板 — 支持查看和编辑两种模式
 * 
 * 交互原则:
 * - 默认视图模式，纯只读渲染
 * - 点击"编辑"进入编辑模式
 * - 编辑模式支持 CodeMirror 6 WYSIWYG 编辑
 * - 静默保存，失败时才提示
 */
export function PageDetailPanel() {
  const location = useLocation()
  const slug = location.pathname.startsWith('/wiki/')
    ? location.pathname.replace('/wiki/', '')
    : null

  const { data, isLoading, refetch } = usePage(slug ?? '')
  const savePageMutation = useSavePageContent()
  const [isEditing, setIsEditing] = useState(false)
  const { pages, fetchPages } = useWikiPagesStore()

  // 确保 pages 已加载（用于 wikilink 存在性判断）
  useEffect(() => {
    fetchPages()
  }, [fetchPages])

  const page = data?.page
  const content = data?.content || ''

  const handleEdit = useCallback(() => {
    setIsEditing(true)
  }, [])

  const handleCancel = useCallback(() => {
    setIsEditing(false)
  }, [])

  const handleSave = useCallback(async (newContent: string, _metadata?: Partial<PageMetadata>) => {
    if (!slug) return
    await savePageMutation.mutateAsync({
      slug,
      content: newContent,
    })
    // Refresh to get updated content
    await refetch()
    setIsEditing(false)
  }, [slug, savePageMutation, refetch])

  // ── Empty / Loading States ──────────────────────────────────

  if (!slug) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center p-4">
        <div className="text-3xl mb-3 opacity-40">📋</div>
        <p className="text-xs text-text-muted">选中页面可查看详情</p>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="p-4 space-y-3">
        <SkeletonText lines={4} />
      </div>
    )
  }

  if (!page) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center p-4">
        <div className="text-3xl mb-3 opacity-40">📋</div>
        <p className="text-xs text-text-muted">页面信息加载失败</p>
      </div>
    )
  }

  // ── Edit Mode ───────────────────────────────────────────────

  if (isEditing) {
    const initialMetadata: PageMetadata = {
      title: page.title,
      category: page.category,
      tags: page.tags || [],
      sources: page.sources || [],
      created_at: page.created_at,
      updated_at: page.updated_at,
    }

    return (
      <div className="flex flex-col h-full">
        {/* Header */}
        <div className="px-4 py-3 border-b border-border-subtle flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-text-primary">{page.title}</span>
            <Badge variant={page.category as never} className="text-[12px]">
              {page.category}
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleCancel}
              className="text-xs text-text-muted hover:text-text-primary transition px-2 py-1"
            >
              取消
            </button>
          </div>
        </div>

        {/* Editor */}
        <PageEditorView
          initialContent={content}
          initialMetadata={initialMetadata}
          onSave={handleSave}
          onCancel={handleCancel}
        />
      </div>
    )
  }

  // ── View Mode ───────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border-subtle flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-text-primary">{page.title}</span>
          <Badge variant={page.category as never} className="text-[12px]">
            {page.category}
          </Badge>
        </div>
        <button
          onClick={handleEdit}
          className="text-xs text-text-muted hover:text-accent-neural transition flex items-center gap-1"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5">
            <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
            <path d="m15 5 4 4" />
          </svg>
          编辑
        </button>
      </div>

      {/* Content — centered with side margins */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        <div className="page-content">
          <div className="markdown-body text-sm text-text-primary">
            <MarkdownRenderer content={content} existingSlugs={pages.map(p => p.slug)} />
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="editor-footer">
        <span className="text-xs text-text-muted">
          创建 {new Date(page.created_at).toLocaleDateString('zh-CN')}
        </span>
        <span className="text-xs text-text-muted">
          更新 {new Date(page.updated_at).toLocaleDateString('zh-CN')}
        </span>
      </div>
    </div>
  )
}
