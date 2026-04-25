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

/** Recently closed tab for undo-close (Cmd+Shift+T) */
export interface ClosedTab {
  tab: WikiTab
  wasActive: boolean
}

interface WikiTabsState {
  tabs: WikiTab[]
  activeKey: string | null
  /** Set of tab keys that have unsaved changes. */
  dirtyKeys: Set<string>
  /** Map of tab key -> save handler (registered by editor components) */
  saveHandlers: Map<string, TabSaveHandler>
  /** Recently closed tabs stack (max 10) for undo-close. */
  recentlyClosed: ClosedTab[]

  /** Open a new blank note tab. */
  openNote: () => void
  /** Open (or activate) a wiki page tab. */
  openPage: (slug: string, title: string) => void
  /** Close a single tab. If dirty and not force, returns the key to let UI prompt. */
  closeTab: (key: string, force?: boolean) => string | null
  /** Activate a tab by key. */
  activateTab: (key: string) => void
  /** Activate the tab at the given index (wraps around). */
  activateTabByIndex: (delta: number) => void
  /** Update a note tab's key after it's been saved (note:xxx -> real slug). */
  upgradeNoteTab: (oldKey: string, slug: string, title: string) => void
  /** Update a tab's title (for double-click inline rename). */
  updateTabTitle: (key: string, title: string) => void
  /** Close all tabs. Returns array of dirty keys that need UI confirmation. */
  closeAll: () => string[]
  /** Close all tabs except the given one. Returns dirty keys needing confirmation. */
  closeOther: (exceptKey: string) => string[]
  /** Close all tabs to the left of the given one. */
  closeLeft: (key: string) => string[]
  /** Close all tabs to the right of the given one. */
  closeRight: (key: string) => string[]
  /** Restore the most recently closed tab. */
  restoreTab: () => void
  /** Register a tab as having unsaved changes. */
  registerDirty: (key: string) => void
  /** Unregister a tab's dirty state (after save). */
  unregisterDirty: (key: string) => void
  /** Check if a tab has unsaved changes. */
  isDirty: (key: string) => boolean
  /** Register a save handler for a tab. */
  registerSaveHandler: (key: string, handler: TabSaveHandler) => void
  /** Unregister a save handler. */
  unregisterSaveHandler: (key: string) => void
  /** Get save handler for a tab. */
  getSaveHandler: (key: string) => TabSaveHandler | undefined
}

type S = WikiTabsState

/** Strategy: determine which tab to activate after closing a tab.
 *  Browser standard: prefer right neighbor, fallback to left neighbor.
 */
function pickNextActive(tabs: WikiTab[], closingKey: string): string | null {
  if (tabs.length === 0) return null
  const idx = tabs.findIndex((t) => t.key === closingKey)
  if (idx === -1) return tabs[0]?.key ?? null
  // Prefer right neighbor (index stays the same after removal)
  if (idx < tabs.length - 1) return tabs[idx + 1].key
  // Fallback to left neighbor
  if (idx > 0) return tabs[idx - 1].key
  return null
}

export const useWikiTabsStore = create<WikiTabsState>()(
  persist(
    (set, get) => ({
      tabs: [],
      activeKey: null,
      dirtyKeys: new Set<string>(),
      saveHandlers: new Map<string, TabSaveHandler>(),
      recentlyClosed: [],

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
          const currentTabs = s.tabs
          const idx = currentTabs.findIndex((t: WikiTab) => t.key === key)
          if (idx === -1) return s // tab not found, no-op

          const remaining = currentTabs.filter((t: WikiTab) => t.key !== key)

          // Save to recentlyClosed for undo
          const closedTab: ClosedTab = {
            tab: currentTabs[idx],
            wasActive: s.activeKey === key,
          }
          const newClosed = [closedTab, ...s.recentlyClosed].slice(0, 10)

          if (remaining.length === 0) {
            return { tabs: [], activeKey: null, recentlyClosed: newClosed }
          }

          // Determine next active tab using strategy
          const nextActive = pickNextActive(remaining, key)
          const finalActive = s.activeKey === key ? nextActive : s.activeKey

          return { tabs: remaining, activeKey: finalActive, recentlyClosed: newClosed }
        })
        return null
      },

      activateTab: (key: string) => {
        const { tabs } = get()
        if (!tabs.find((t) => t.key === key)) return // safety: tab must exist
        set({ activeKey: key })
      },

      activateTabByIndex: (delta: number) => {
        const { tabs, activeKey } = get()
        if (tabs.length === 0) return
        const currentIdx = tabs.findIndex((t) => t.key === activeKey)
        const nextIdx = (currentIdx + delta + tabs.length) % tabs.length
        set({ activeKey: tabs[nextIdx].key })
      },

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
          // Push all to recentlyClosed
          const newClosed = tabs.map((t) => ({ tab: t, wasActive: false })).slice(0, 10)
          set({ tabs: [], activeKey: null, dirtyKeys: new Set(), saveHandlers: new Map(), recentlyClosed: newClosed })
        }
        return dirtyInTabs
      },

      closeOther: (exceptKey: string) => {
        const { dirtyKeys, tabs } = get()
        const toClose = tabs.filter((t) => t.key !== exceptKey)
        const dirtyInToClose = toClose.filter((t) => dirtyKeys.has(t.key)).map((t) => t.key)
        if (dirtyInToClose.length === 0) {
          const newClosed = toClose.map((t) => ({ tab: t, wasActive: false })).slice(0, 10)
          set({ tabs: [tabs.find((t) => t.key === exceptKey)!], activeKey: exceptKey, recentlyClosed: newClosed })
        }
        return dirtyInToClose
      },

      closeLeft: (key: string) => {
        const { dirtyKeys, tabs } = get()
        const idx = tabs.findIndex((t) => t.key === key)
        if (idx <= 0) return []
        const toClose = tabs.slice(0, idx)
        const dirtyInToClose = toClose.filter((t) => dirtyKeys.has(t.key)).map((t) => t.key)
        if (dirtyInToClose.length === 0) {
          const remaining = tabs.slice(idx)
          set({ tabs: remaining })
        }
        return dirtyInToClose
      },

      closeRight: (key: string) => {
        const { dirtyKeys, tabs } = get()
        const idx = tabs.findIndex((t) => t.key === key)
        if (idx === -1 || idx >= tabs.length - 1) return []
        const toClose = tabs.slice(idx + 1)
        const dirtyInToClose = toClose.filter((t) => dirtyKeys.has(t.key)).map((t) => t.key)
        if (dirtyInToClose.length === 0) {
          const remaining = tabs.slice(0, idx + 1)
          set({ tabs: remaining })
        }
        return dirtyInToClose
      },

      restoreTab: () => {
        const { recentlyClosed, tabs } = get()
        if (recentlyClosed.length === 0) return
        const [first, ...rest] = recentlyClosed
        set({
          tabs: [...tabs, first.tab],
          activeKey: first.tab.key,
          recentlyClosed: rest,
        })
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
          recentlyClosed: [],
        }
      },
    }
  )
)
