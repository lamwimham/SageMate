import { useState, useCallback } from 'react'
import { usePage, useSavePageContent } from '@/hooks/useWiki'
import { UnifiedWikiEditor } from './UnifiedWikiEditor'
import { SkeletonText } from '@/components/ui/Skeleton'
import { useWikiTabsStore } from '@/stores/wikiTabs'

/**
 * Wiki Page Content — 查看/编辑已有 wiki 页面
 * - 默认进入阅读态
 * - 编辑时检测变更、显示保存状态、支持 Cmd+S
 */
export function WikiPageContent({ slug }: { slug: string }) {
  const { data, isLoading, refetch } = usePage(slug)
  const savePageMutation = useSavePageContent()
  const [originalBody, setOriginalBody] = useState<string | null>(null)
  const { registerDirty, unregisterDirty } = useWikiTabsStore()

  const page = data?.page
  const content = data?.content || ''

  const handleSave = useCallback(async (bodyContent: string) => {
    if (!page) return
    await savePageMutation.mutateAsync({ slug, content: bodyContent })
    await refetch()
    setOriginalBody(bodyContent)
    unregisterDirty(slug)
  }, [slug, page, savePageMutation, refetch, unregisterDirty])

  const handleContentChange = useCallback((body: string) => {
    if (originalBody !== null) {
      if (body === originalBody) {
        unregisterDirty(slug)
      } else {
        registerDirty(slug)
      }
    }
  }, [slug, originalBody, registerDirty, unregisterDirty])

  const handleEditStart = useCallback((body: string) => {
    setOriginalBody(body)
  }, [])

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
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-10 h-10 mb-3 opacity-40 text-text-muted">
          <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
          <polyline points="14 2 14 8 20 8" />
        </svg>
        <p className="text-xs text-text-muted">页面不存在</p>
      </div>
    )
  }

  return (
    <UnifiedWikiEditor
      title={page.title}
      content={content}
      category={page.category}
      defaultEditing={false}
      onSave={handleSave}
      onContentChange={handleContentChange}
      onEditStart={handleEditStart}
      footerInfo={
        <>
          <span className="text-xs text-text-muted">
            创建 {new Date(page.created_at).toLocaleDateString('zh-CN')}
          </span>
          <span className="text-xs text-text-muted">
            更新 {new Date(page.updated_at).toLocaleDateString('zh-CN')}
          </span>
        </>
      }
    />
  )
}
