import { apiClient } from '../client'
import type { IngestRequest, IngestResult, IngestTaskState } from '@/types'

export const ingestRepo = {
  ingestText: (text: string, title: string, opts?: IngestRequest) => {
    const form = new FormData()
    form.append('text', text)
    form.append('title', title)
    form.append('auto_compile', String(opts?.auto_compile ?? true))
    return apiClient.postForm<IngestResult>('/ingest', form)
  },

  ingestFile: (file: File, opts?: IngestRequest) => {
    const form = new FormData()
    form.append('file', file)
    if (opts?.source_type) form.append('source_type', opts.source_type)
    form.append('auto_compile', String(opts?.auto_compile ?? true))
    return apiClient.postForm<IngestResult>('/ingest', form)
  },

  ingestUrl: (url: string, opts?: IngestRequest) => {
    const form = new FormData()
    form.append('url', url)
    form.append('auto_compile', String(opts?.auto_compile ?? true))
    return apiClient.postForm<IngestResult>('/ingest', form)
  },

  taskStatus: (taskId: string) =>
    apiClient.get<IngestTaskState>(`/ingest/progress/${taskId}`),
}
