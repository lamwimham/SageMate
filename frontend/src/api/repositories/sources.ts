import { apiClient } from '../client'

export interface SourceItem {
  slug: string
  title: string
  source_type: string
  status: string
  ingested_at: string | null
  wiki_pages: string[]
  error: string | null
}

export interface SourcesResponse {
  sources: SourceItem[]
  source_types: string[]
}

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
    error: string | null
  } | null
  linked_wiki_pages: { slug: string; title: string; category: string }[]
}

export interface RawFilesResponse {
  files: RawFileItem[]
  raw_dir: string
}

export const sourcesRepo = {
  list: (status?: string, sourceType?: string, q?: string) => {
    const params = new URLSearchParams()
    if (status) params.set('status', status)
    if (sourceType) params.set('source_type', sourceType)
    if (q) params.set('q', q)
    const qs = params.toString()
    return apiClient.get<SourcesResponse>(`/api/sources${qs ? '?' + qs : ''}`)
  },

  rawFiles: () => apiClient.get<RawFilesResponse>('/api/v1/raw/files'),
}
