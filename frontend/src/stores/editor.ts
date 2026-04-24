// ============================================================
// Wiki Page Editor Store — 编辑状态管理
// ============================================================

import { create } from 'zustand'

export type EditorMode = 'view' | 'edit'

interface EditorState {
  mode: EditorMode
  content: string
  originalContent: string
  pageSlug: string | null  // Track which page this content belongs to
  isDirty: boolean
  isSaving: boolean
  saveError: string | null
  externalModified: boolean

  // Actions
  enterEditMode: (content: string, pageSlug?: string) => void
  exitEditMode: () => void
  updateContent: (content: string) => void
  setPageSlug: (slug: string | null) => void
  setSaving: (saving: boolean) => void
  setSaveError: (error: string | null) => void
  setExternalModified: (modified: boolean) => void
  saveDraft: () => void
  loadDraft: () => string | null
  clearDraft: () => void
  reset: () => void
}

const DRAFT_KEY_PREFIX = 'sagemate-editor-draft-'

export const useEditorStore = create<EditorState>((set, get) => ({
  mode: 'view',
  content: '',
  originalContent: '',
  pageSlug: null,
  isDirty: false,
  isSaving: false,
  saveError: null,
  externalModified: false,

  enterEditMode: (content: string, pageSlug?: string) => {
    set({
      mode: 'edit',
      content,
      originalContent: content,
      pageSlug: pageSlug ?? null,
      isDirty: false,
      saveError: null,
      externalModified: false,
    })
  },

  exitEditMode: () => {
    set({
      mode: 'view',
      content: '',
      originalContent: '',
      pageSlug: null,
      isDirty: false,
      saveError: null,
    })
  },

  updateContent: (content: string) => {
    const { originalContent } = get()
    set({
      content,
      isDirty: content !== originalContent,
    })
  },

  setPageSlug: (slug: string | null) => {
    set({ pageSlug: slug })
  },

  setSaving: (saving: boolean) => {
    set({ isSaving: saving })
  },

  setSaveError: (error: string | null) => {
    set({ saveError: error })
  },

  setExternalModified: (modified: boolean) => {
    set({ externalModified: modified })
  },

  saveDraft: () => {
    const { content } = get()
    if (content) {
      localStorage.setItem(DRAFT_KEY_PREFIX + 'current', content)
    }
  },

  loadDraft: () => {
    return localStorage.getItem(DRAFT_KEY_PREFIX + 'current')
  },

  clearDraft: () => {
    localStorage.removeItem(DRAFT_KEY_PREFIX + 'current')
  },

  reset: () => {
    set({
      mode: 'view',
      content: '',
      originalContent: '',
      pageSlug: null,
      isDirty: false,
      isSaving: false,
      saveError: null,
      externalModified: false,
    })
    get().clearDraft()
  },
}))
