export type LogEntryType = 'ingest' | 'query' | 'lint' | 'manual_edit' | 'repair'

export interface LogEntry {
  timestamp: string
  entry_type: LogEntryType
  title: string
  details: string
  affected_pages: string[]
}

export type LintIssueSeverity = 'low' | 'medium' | 'high'

export type LintIssueType =
  | 'contradiction'
  | 'stale_claim'
  | 'orphan_page'
  | 'broken_link'
  | 'missing_cross_ref'
  | 'no_summary'

export interface LintIssue {
  issue_type: LintIssueType
  severity: LintIssueSeverity
  page_slug: string
  description: string
  suggestion: string
  related_pages: string[]
}

export interface LintReport {
  timestamp: string
  total_pages_scanned: number
  issues: LintIssue[]
}

export interface QueryRequest {
  question: string
  save_analysis?: boolean
}

export interface QueryResponse {
  answer: string
  sources: string[]
  citations: Record<string, unknown>[]
  related_pages: Record<string, unknown>[]
}
