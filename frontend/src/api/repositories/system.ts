import { apiClient } from '../client'
import type { LintReport, QueryRequest, QueryResponse } from '@/types'

export interface HealthStatus {
  status: string
}

export interface Stats {
  wiki_pages: number
  sources: number
  last_ingest: string | null
}

export interface CostSummary {
  total_cost: number
  total_tokens: number
  total_calls: number
}

export interface CostEntry {
  model: string
  tokens_in: number
  tokens_out: number
  cost_usd: number
  timestamp: string
  purpose?: string
  total_tokens?: number
}

export interface CronStatus {
  running: boolean
  auto_compile: { enabled: boolean; interval_seconds: number; last_run: string | null }
  lint_check: { enabled: boolean; interval_seconds: number; last_run: string | null }
  active_tasks: number
}

export const systemRepo = {
  health: () => apiClient.get<HealthStatus>('/health'),

  stats: () => apiClient.get<Stats>('/api/v1/stats'),

  lint: (autoFix = false) => apiClient.post<LintReport>('/api/v1/lint', { auto_fix: autoFix }),

  cost: () => apiClient.get<{ summary: CostSummary | null; recent: CostEntry[] }>('/api/v1/cost'),

  cron: () => apiClient.get<CronStatus>('/api/v1/cron/status'),

  cronToggle: (task: string, enabled: boolean) => {
    const form = new FormData()
    form.append('task', task)
    form.append('enabled', String(enabled))
    return apiClient.post('/api/v1/cron/toggle', form)
  },

  cronRunNow: (task: string) => {
    const form = new FormData()
    form.append('task', task)
    return apiClient.post('/api/v1/cron/run', form)
  },

  logs: () => apiClient.get<{ content: string }>('/api/v1/log'),

  query: (req: QueryRequest) => apiClient.post<QueryResponse>('/api/v1/query', req),
}
