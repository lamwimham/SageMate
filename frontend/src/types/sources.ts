export type SourceStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface SourceDocument {
  file_path: string
  title: string
  slug: string
  source_type: string
  ingested_at: string | null
  wiki_pages_created: string[]
  status: SourceStatus
  error: string | null
}
