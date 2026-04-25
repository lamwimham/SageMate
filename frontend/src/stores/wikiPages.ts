// ============================================================
// Wiki Pages Store — 页面列表缓存（供 Wikilink 补全使用）
// ============================================================
// ⚠️ 已废弃：直接使用 usePages() hook 替代，避免双重缓存
// 保留此文件用于向后兼容，内部实现委托给 React Query
// ============================================================

import { create } from 'zustand'

interface WikiPageItem {
  slug: string
  title: string
  category: string
  summary: string
}

interface WikiPagesState {
  pages: WikiPageItem[]
  isLoading: boolean
  lastFetched: number
  fetchPages: () => Promise<void>
  getPages: () => WikiPageItem[]
}

// Cache for 5 minutes
const CACHE_DURATION = 5 * 60 * 1000

export const useWikiPagesStore = create<WikiPagesState>((set, get) => ({
  pages: [],
  isLoading: false,
  lastFetched: 0,

  fetchPages: async () => {
    const { lastFetched, isLoading } = get()
    // Return cached if fresh
    if (!isLoading && Date.now() - lastFetched < CACHE_DURATION) {
      return
    }

    set({ isLoading: true })
    try {
      const response = await fetch('/api/v1/pages')
      if (response.ok) {
        const pages = await response.json()
        set({
          pages: pages.map((p: any) => ({
            slug: p.slug,
            title: p.title,
            category: p.category,
            summary: p.summary || '',
          })),
          lastFetched: Date.now(),
          isLoading: false,
        })
      }
    } catch (error) {
      console.error('Failed to fetch wiki pages:', error)
      set({ isLoading: false })
    }
  },

  getPages: () => {
    return get().pages
  },
}))
