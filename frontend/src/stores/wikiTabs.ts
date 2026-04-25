import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type WikiTabType = 'note' | 'page'

export interface WikiTab {
  /** Unique key for the tab. For pages: slug. For notes: 'note:<timestamp>'. */
  key: string
  title: string
  type: WikiTabType
  /** For page tabs, the wiki page slug. For note tabs, undefined until saved. */
  slug?: string
}

/** Save handler registered by a tab's editor component */
export type TabSaveHandler = () => Promise<void>

interface WikiTabsState {
  tabs: WikiTab[]
  activeKey: string | null
  /** Set of tab keys that have unsaved changes. */
  dirtyKeys: Set<string>
  /** Map of tab key -> save handler (registered by editor components) */
  saveHandlers: Map<string, TabSaveHandler>

  /** Open a new blank note tab. */
  openNote: () => void
  /** Open (or activate) a wiki page tab. */
  openPage: (slug: string, title: string) => void
  /** Close a single tab. If dirty, returns the key to let UI prompt. */
  closeTab: (key: string, force?: boolean) => string | null
  activateTab: (key: string) => void
  /** Update a note tab's key after it's been saved (note:xxx -> real slug). */
  upgradeNoteTab: (oldKey: string, slug: string, title: string) => void
  /** Update a tab's title (for double-click inline rename). */
  updateTabTitle: (key: string, title: string) => void
  /** Close all tabs. Returns array of dirty keys that need UI confirmation. */
  closeAll: () => string[]
  /** Register a tab as having unsaved changes. */
  registerDirty: (key: string) => void
  /** Unregister a tab's dirty state (after save). */
  unregisterDirty: (key: string) => void
  /** Check if a tab has unsaved changes. */
  isDirty: (key: string) => boolean
  /** Register a save handler for a tab (called when user chooses "save & close"). */
  registerSaveHandler: (key: string, handler: TabSaveHandler) => void
  /** Unregister a save handler. */
  unregisterSaveHandler: (key: string) => void
  /** Get save handler for a tab. */
  getSaveHandler: (key: string) => TabSaveHandler | undefined
}

type S = WikiTabsState

export const useWikiTabsStore = create<WikiTabsState>()(
  persist(
    (set, get) => ({
      tabs: [],
      activeKey: null,
      dirtyKeys: new Set<string>(),
      saveHandlers: new Map<string, TabSaveHandler>(),

      openNote: () =>
        set((s: S) => {
          const key = `note:${Date.now()}`
          const newTabs = [...s.tabs, { key, title: '新建笔记', type: 'note' as WikiTabType }]
          const trimmed = newTabs.length > 20 ? newTabs.slice(newTabs.length - 20) : newTabs
          return {
            tabs: trimmed,
            activeKey: key,
          }
        }),

      openPage: (slug: string, title: string) =>
        set((s: S) => {
          const exists = s.tabs.find((t: WikiTab) => t.key === slug)
          if (exists) return { activeKey: slug }
          const newTabs = [...s.tabs, { key: slug, title, type: 'page' as WikiTabType, slug }]
          const trimmed = newTabs.length > 20 ? newTabs.slice(newTabs.length - 20) : newTabs
          return {
            tabs: trimmed,
            activeKey: slug,
          }
        }),

      closeTab: (key: string, force = false) => {
        const { dirtyKeys } = get()
        if (!force && dirtyKeys.has(key)) {
          return key
        }
        set((s: S) => {
          const remaining = s.tabs.filter((t: WikiTab) => t.key !== key)
          if (remaining.length === 0) return { tabs: [], activeKey: null }
          if (s.activeKey === key) {
            return { tabs: remaining, activeKey: remaining[remaining.length - 1].key }
          }
          return { tabs: remaining, activeKey: s.activeKey }
        })
        return null
      },

      activateTab: (key: string) => set({ activeKey: key }),

      upgradeNoteTab: (oldKey: string, slug: string, title: string) =>
        set((s: S) => {
          const idx = s.tabs.findIndex((t: WikiTab) => t.key === oldKey)
          if (idx === -1) return s
          const newTab: WikiTab = { key: slug, title, type: 'page', slug }
          const newTabs = [...s.tabs]
          newTabs[idx] = newTab
          // Clear dirty state and save handler on upgrade (save completed)
          const newDirty = new Set(s.dirtyKeys)
          newDirty.delete(oldKey)
          const newHandlers = new Map(s.saveHandlers)
          newHandlers.delete(oldKey)
          return { tabs: newTabs, activeKey: slug, dirtyKeys: newDirty, saveHandlers: newHandlers }
        }),

      updateTabTitle: (key: string, title: string) =>
        set((s: S) => {
          const idx = s.tabs.findIndex((t: WikiTab) => t.key === key)
          if (idx === -1) return s
          const newTabs = [...s.tabs]
          newTabs[idx] = { ...newTabs[idx], title }
          return { tabs: newTabs }
        }),

      closeAll: () => {
        const { dirtyKeys, tabs } = get()
        const dirtyInTabs = tabs.filter((t: WikiTab) => dirtyKeys.has(t.key)).map((t: WikiTab) => t.key)
        if (dirtyInTabs.length === 0) {
          set({ tabs: [], activeKey: null, dirtyKeys: new Set(), saveHandlers: new Map() })
        }
        return dirtyInTabs
      },

      registerDirty: (key: string) =>
        set((s: S) => {
          const next = new Set(s.dirtyKeys)
          next.add(key)
          return { dirtyKeys: next }
        }),

      unregisterDirty: (key: string) =>
        set((s: S) => {
          const next = new Set(s.dirtyKeys)
          next.delete(key)
          return { dirtyKeys: next }
        }),

      isDirty: (key: string) => get().dirtyKeys.has(key),

      registerSaveHandler: (key: string, handler: TabSaveHandler) =>
        set((s: S) => {
          const next = new Map(s.saveHandlers)
          next.set(key, handler)
          return { saveHandlers: next }
        }),

      unregisterSaveHandler: (key: string) =>
        set((s: S) => {
          const next = new Map(s.saveHandlers)
          next.delete(key)
          return { saveHandlers: next }
        }),

      getSaveHandler: (key: string) => get().saveHandlers.get(key),
    }),
    {
      name: 'sagemate-wiki-tabs',
      partialize: (state) => ({ tabs: state.tabs, activeKey: state.activeKey }),
      merge: (persisted: unknown, current: WikiTabsState) => {
        const p = persisted as Partial<WikiTabsState>
        return {
          ...current,
          tabs: p.tabs ?? current.tabs,
          activeKey: p.activeKey ?? current.activeKey,
          dirtyKeys: new Set(),
          saveHandlers: new Map(),
        }
      },
    }
  )
)
