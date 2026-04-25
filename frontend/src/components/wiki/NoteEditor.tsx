import { useCallback, useEffect } from 'react'
import { UnifiedWikiEditor } from './UnifiedWikiEditor'
import { useWikiTabsStore } from '@/stores/wikiTabs'
import { useNoteContentStore } from '@/stores/noteContent'
import { useCreatePage } from '@/hooks/useWiki'
import type { WikiPageCreate } from '@/types'

interface NoteEditorProps {
  /** Tab key (e.g. 'note:1713945600000') */
  tabKey: string
  /** Current title from tab (managed by tab bar double-click) */
  title: string
}

/**
 * Note Editor — 新建笔记编辑器
 * - 默认进入编辑态
 * - 预览 toggle 在右侧
 * - 保存后 tab 升级为 page 类型
 */
export function NoteEditor({ tabKey, title }: NoteEditorProps) {
  const content = useNoteContentStore((s) => s.getContent(tabKey))
  const setContent = useNoteContentStore((s) => s.setContent)

  const createMutation = useCreatePage()
  const { upgradeNoteTab, registerDirty, unregisterDirty } = useWikiTabsStore()
  const clearNoteContent = useNoteContentStore((s) => s.clearContent)

  // Track dirty state
  const isDirty = content.trim().length > 0
  useEffect(() => {
    if (isDirty) {
      registerDirty(tabKey)
    } else {
      unregisterDirty(tabKey)
    }
  }, [isDirty, tabKey, registerDirty, unregisterDirty])

  const handleSave = useCallback(async (bodyContent: string) => {
    if (!title || !bodyContent.trim()) return

    const slug = title.toLowerCase()
      .replace(/[^\w\u4e00-\u9fa5\s-]/g, '')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-')

    // Build full content with frontmatter
    const fullContent = `---
title: "${title}"
category: note
tags: []
outbound_links: []
sources: []
---

${bodyContent.trim()}`

    const data: WikiPageCreate = {
      slug,
      title,
      category: 'note',
      content: fullContent,
      tags: [],
      sources: [],
      outbound_links: [],
    }

    const res = await createMutation.mutateAsync(data)
    // Upgrade the tab from note -> page
    upgradeNoteTab(tabKey, res.slug, title)
    // Clear cached note content (page has its own content now)
    clearNoteContent(tabKey)
    unregisterDirty(tabKey)
  }, [title, tabKey, createMutation, upgradeNoteTab, clearNoteContent, unregisterDirty])

  const handleContentChange = useCallback((value: string) => {
    setContent(tabKey, value)
  }, [tabKey, setContent])

  return (
    <UnifiedWikiEditor
      title={title || '新建笔记'}
      content={content}
      category="note"
      defaultEditing={true}
      onSave={handleSave}
      onContentChange={handleContentChange}
    />
  )
}
