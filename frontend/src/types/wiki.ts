export type WikiCategory = 'entity' | 'concept' | 'relationship' | 'analysis' | 'source' | 'note'

export interface WikiPage {
  slug: string
  title: string
  category: WikiCategory
  file_path: string
  content: string
  summary: string
  created_at: string
  updated_at: string
  word_count: number
  content_hash: string | null
  inbound_links: string[]
  outbound_links: string[]
  tags: string[]
  sources: string[]
  source_pages: number[]
}

export interface WikiPageUpdate {
  slug: string
  title?: string
  content_patch?: string
  reason?: string
  new_links?: string[]
  removed_links?: string[]
  contradictions?: string[]
}

export interface WikiPageCreate {
  slug: string
  title: string
  category: WikiCategory
  content: string
  tags?: string[]
  sources?: string[]
  outbound_links?: string[]
  source_pages?: number[]
}

export interface IndexEntry {
  slug: string
  title: string
  category: WikiCategory
  summary: string
  last_updated: string | null
  source_count: number
  inbound_count: number
}

export interface SearchResult {
  slug: string
  title: string
  category: WikiCategory
  snippet: string
  score: number
}
