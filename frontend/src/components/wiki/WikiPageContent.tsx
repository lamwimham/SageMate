import { useState, useCallback } from 'react'
import { usePage, useSavePageContent } from '@/hooks/useWiki'
import { Badge } from '@/components/ui/Badge'
import { SkeletonText } from '@/components/ui/Skeleton'
import { MarkdownRenderer } from '@/components/markdown/MarkdownRenderer'
import { PageEditorView } from '@/components/layout/detail-panels/PageEditorView'
import { PageMetadata } from '@/components/layout/detail-panels/MetadataBar'
import { ViewToggle } from '@/components/wiki/ViewToggle'
import { cn } from '@/lib/utils'

/**
 * Wiki Page Content — 查看/编辑已有 wiki 页面
 * 作为 tab 内容使用，由 slug prop 驱动
 */
export function WikiPageContent({ slug }: { slug: string }) {
  const { data, isLoading, refetch } = usePage(slug)
  const savePageMutation = useSavePageContent()
  const [isEditing, setIsEditing] = useState(false)

  const page = data?.page
  const content = data?.content || ''

  const handleSave = useCallback(async (newContent: string, _metadata?: Partial<PageMetadata>) => {
    await savePageMutation.mutateAsync({ slug, content: newContent })
    await refetch()
    setIsEditing(false)
  }, [slug, savePageMutation, refetch])

  // Toggle between edit and preview
  const handleCancel = useCallback(() => setIsEditing(false), [])

  const handleToggle = useCallback(async () => {
    if (isEditing) {
      // Switching to preview: trigger save via Cmd+S event
      const event = new KeyboardEvent('keydown', { key: 's', metaKey: true, bubbles: true })
      window.dispatchEvent(event)
    } else {
      setIsEditing(true)
    }
  }, [isEditing])

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
        <div className="text-3xl mb-3 opacity-40">📄</div>
        <p className="text-xs text-text-muted">页面不存在</p>
      </div>
    )
  }

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
        <div className="px-4 py-3 border-b border-border-subtle flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-text-primary">{page.title}</span>
            <Badge variant={page.category as never} className="text-[10px]">
              {page.category}
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={handleCancel} className="text-xs text-text-muted hover:text-text-primary transition px-2 py-1">
              取消
            </button>
            <button
              onClick={() => {
                const event = new KeyboardEvent('keydown', { key: 's', metaKey: true, bubbles: true })
                window.dispatchEvent(event)
              }}
              disabled={savePageMutation.isPending}
              className={cn(
                'text-xs px-3 py-1 rounded-md transition',
                savePageMutation.isPending
                  ? 'bg-accent-neural/20 text-text-muted cursor-not-allowed'
                  : 'bg-accent-neural/10 text-accent-neural hover:bg-accent-neural/20'
              )}
            >
              {savePageMutation.isPending ? '保存中...' : '保存'}
            </button>
          </div>
        </div>
        <PageEditorView
          initialContent={content}
          initialMetadata={initialMetadata}
          onSave={handleSave}
          onCancel={handleCancel}
        />
      </div>
    )
  }

  // View mode
  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-border-subtle flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-text-primary">{page.title}</span>
          <Badge variant={page.category as never} className="text-[10px]">
            {page.category}
          </Badge>
        </div>
        <ViewToggle mode="preview" onToggle={handleToggle} />
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-4">
        <div className="page-content">
          <div className="markdown-body text-sm text-text-primary">
            <MarkdownRenderer content={content} />
          </div>
        </div>
      </div>
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
