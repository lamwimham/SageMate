import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type WikiTabType = 'overview' | 'note' | 'page'

export interface WikiTab {
  /** Unique key for the tab. For pages: slug. For overview: '__overview'. For notes: 'note:<timestamp>'. */
  key: string
  title: string
  type: WikiTabType
  /** For page tabs, the wiki page slug. For note tabs, undefined until saved. */
  slug?: string
}

interface WikiTabsState {
  tabs: WikiTab[]
  activeKey: string | null
  /** Open the overview tab. */
  openOverview: () => void
  /** Open a new blank note tab. */
  openNote: () => void
  /** Open (or activate) a wiki page tab. */
  openPage: (slug: string, title: string) => void
  closeTab: (key: string) => void
  activateTab: (key: string) => void
  /** Update a note tab's key after it's been saved (note:xxx -> real slug). */
  upgradeNoteTab: (oldKey: string, slug: string, title: string) => void
  closeAll: () => void
}

export const useWikiTabsStore = create<WikiTabsState>()(
  persist(
    (set) => ({
      tabs: [],
      activeKey: null,

      openOverview: () =>
        set((s) => {
          const exists = s.tabs.find((t) => t.key === '__overview')
          if (exists) return { activeKey: '__overview' }
          return {
            tabs: [...s.tabs, { key: '__overview', title: '概览', type: 'overview' as WikiTabType }],
            activeKey: '__overview',
          }
        }),

      openNote: () =>
        set((s) => {
          const key = `note:${Date.now()}`
          return {
            tabs: [...s.tabs, { key, title: '新建笔记', type: 'note' as WikiTabType }],
            activeKey: key,
          }
        }),

      openPage: (slug: string, title: string) =>
        set((s) => {
          const exists = s.tabs.find((t) => t.key === slug)
          if (exists) return { activeKey: slug }
          return {
            tabs: [...s.tabs, { key: slug, title, type: 'page' as WikiTabType, slug }],
            activeKey: slug,
          }
        }),

      closeTab: (key: string) =>
        set((s) => {
          const remaining = s.tabs.filter((t) => t.key !== key)
          if (remaining.length === 0) return { tabs: [], activeKey: null }
          if (s.activeKey === key) {
            return { tabs: remaining, activeKey: remaining[remaining.length - 1].key }
          }
          return { tabs: remaining, activeKey: s.activeKey }
        }),

      activateTab: (key: string) => set({ activeKey: key }),

      upgradeNoteTab: (oldKey: string, slug: string, title: string) =>
        set((s) => {
          const idx = s.tabs.findIndex((t) => t.key === oldKey)
          if (idx === -1) return s
          const newTab: WikiTab = { key: slug, title, type: 'page', slug }
          const newTabs = [...s.tabs]
          newTabs[idx] = newTab
          return { tabs: newTabs, activeKey: slug }
        }),

      closeAll: () => set({ tabs: [], activeKey: null }),
    }),
    {
      name: 'sagemate-wiki-tabs',
      // Only persist tabs and activeKey
      partialize: (state) => ({ tabs: state.tabs, activeKey: state.activeKey }),
    }
  )
)
