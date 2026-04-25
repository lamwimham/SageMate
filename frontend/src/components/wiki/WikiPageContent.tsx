import { useState, useCallback } from 'react'
import { usePage, useSavePageContent } from '@/hooks/useWiki'
import { UnifiedWikiEditor } from './UnifiedWikiEditor'
import { SkeletonText } from '@/components/ui/Skeleton'
import { useWikiTabsStore } from '@/stores/wikiTabs'

/**
 * Wiki Page Content — 查看/编辑已有 wiki 页面
 *
 * 职责分层：
 * - 本层：HTTP 通信、frontmatter 解析/拼接、脏状态管理
 * - UnifiedWikiEditor：纯 body 编辑/预览，不感知 frontmatter
 *
 * 数据流：
 *   API (full) → parseFrontmatter → body → UnifiedWikiEditor
 *   UnifiedWikiEditor (body) → onSave → 拼接 frontmatter → API (full)
 */
export function WikiPageContent({ slug }: { slug: string }) {
  const { data, isLoading, refetch } = usePage(slug)
  const savePageMutation = useSavePageContent()
  const [originalBody, setOriginalBody] = useState<string | null>(null)
  const { registerDirty, unregisterDirty } = useWikiTabsStore()

  const page = data?.page
  const fullContent = data?.content || ''

  // 解析出 body 传给编辑器
  const { body: initialBody } = parseFrontmatter(fullContent)

  const handleSave = useCallback(async (bodyContent: string) => {
    if (!page) return
    // 拼接 frontmatter + body
    const full = `---
title: "${page.title}"
category: ${page.category}
tags: ${JSON.stringify(page.tags || [])}
outbound_links: ${JSON.stringify(page.outbound_links || [])}
sources: ${JSON.stringify(page.sources || [])}
---

${bodyContent}`
    await savePageMutation.mutateAsync({ slug, content: full })
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
      tabKey={slug}
      title={page.title}
      content={initialBody}  // 只传 body，不传 frontmatter
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

// Parse frontmatter to get the body part
function parseFrontmatter(full: string): { body: string; hasFrontmatter: boolean; metadata?: Record<string, any> } {
  const match = full.match(/^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/)
  if (match) {
    try {
      const metadata = JSON.parse(match[1].replace(/(\w+):/g, '"$1":'))
      return { body: match[2], hasFrontmatter: true, metadata }
    } catch {
      return { body: match[2], hasFrontmatter: true }
    }
  }
  return { body: full, hasFrontmatter: false }
}
