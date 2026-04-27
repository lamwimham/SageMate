export interface IngestRequest {
  source_type?: string
  auto_compile?: boolean
}

export interface IngestResult {
  success: boolean
  source_slug: string | null
  wiki_pages_created: number
  wiki_pages_updated: number
  wiki_pages: { slug: string; title: string }[]
  plan_summary?: CompilePlanSummary | null
  error: string | null
  task_id?: string
  status?: string
  message?: string
}

export interface CompilePlanSummary {
  mode: string
  total_chunks: number
  scanned_chunks: number
  candidate_pages: number
  planned_pages: number
  evidence_refs: number
  evidence_blocks: number
  page_slugs: string[]
  budget: Record<string, number>
  fallback_reason?: string | null
}

export type IngestTaskStatus =
  | 'queued'
  | 'parsing'
  | 'reading_context'
  | 'calling_llm'
  | 'writing_pages'
  | 'updating_index'
  | 'completed'
  | 'failed'
  | 'connecting'
  | 'idle'

export interface IngestTaskState {
  type?: string
  task_id: string
  status: IngestTaskStatus
  step: number
  total_steps: number
  step_name: string
  message: string
  result: IngestResult | null
  error: string | null
  failed_step?: string
  created_at: string
  updated_at: string
}
