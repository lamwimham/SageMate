import { create } from 'zustand'

/**
 * Session-level store for note editor content.
 * - Keyed by tabKey (e.g. 'note:1713945600000')
 * - NOT persisted to localStorage — session only
 * - Content is cleaned up when the note tab is closed or upgraded
 */
interface NoteContentState {
  /** Map of tabKey -> editor content */
  contents: Record<string, string>

  /** Set content for a note tab */
  setContent: (tabKey: string, content: string) => void

  /** Get content for a note tab, defaults to empty string */
  getContent: (tabKey: string) => string

  /** Clear content for a specific tab (on close or upgrade) */
  clearContent: (tabKey: string) => void

  /** Clear all content (on close all) */
  clearAll: () => void
}

export const useNoteContentStore = create<NoteContentState>((set, get) => ({
  contents: {},

  setContent: (tabKey: string, content: string) =>
    set((s) => ({
      contents: { ...s.contents, [tabKey]: content },
    })),

  getContent: (tabKey: string) => get().contents[tabKey] ?? '',

  clearContent: (tabKey: string) =>
    set((s) => {
      const { [tabKey]: _, ...rest } = s.contents
      return { contents: rest }
    }),

  clearAll: () => set({ contents: {} }),
}))
