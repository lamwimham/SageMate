import { create } from 'zustand'

export interface RawFileItem {
  name: string
  rel_path: string
  parent: string
  ext: string
  size: number
  size_human: string
  mime: string
  modified: string
  is_text: boolean
  is_markdown: boolean
  is_pdf: boolean
  is_docx: boolean
  is_image: boolean
  file_url: string
  preview_url?: string
  content?: string
  linked_source: {
    slug: string
    title: string
    status: string
    wiki_pages?: string[]
    error: string | null
  } | null
  linked_wiki_pages: { slug: string; title: string; category: string }[]
  can_compile: boolean
  compile_disabled_reason: string | null
}

interface RawFilesState {
  files: RawFileItem[]
  selectedIndex: number
  rawDir: string
  setFiles: (files: RawFileItem[], rawDir: string) => void
  setSelectedIndex: (index: number) => void
  selectedFile: () => RawFileItem | undefined
}

export const useRawFilesStore = create<RawFilesState>((set, get) => ({
  files: [],
  selectedIndex: 0,
  rawDir: '',

  setFiles: (files, rawDir) => {
    set({ files, rawDir, selectedIndex: 0 })
  },

  setSelectedIndex: (index) => set({ selectedIndex: index }),

  selectedFile: () => {
    const { files, selectedIndex } = get()
    return files[selectedIndex]
  },
}))
