import { apiClient } from '../client'
import type { WikiPage, WikiPageCreate, WikiPageUpdate, IndexEntry, SearchResult, QueryResponse } from '@/types'

export interface IndexResponse {
  content: string
  entries: IndexEntry[]
}

export interface PageDetailResponse {
  page: WikiPage
  content: string
}

export const wikiRepo = {
  getIndex: () => apiClient.get<IndexResponse>('/api/v1/index'),

  listPages: (category?: string) =>
    apiClient.get<WikiPage[]>(category ? `/api/v1/pages?category=${category}` : '/api/v1/pages'),

  getPage: (slug: string) => apiClient.get<PageDetailResponse>(`/api/v1/pages/${slug}`),

  /** Create a new wiki page (e.g. Note) */
  createPage: (data: WikiPageCreate) =>
    apiClient.post<{ success: boolean; slug: string }>(`/api/v1/pages`, data),

  updatePage: (slug: string, update: WikiPageUpdate) =>
    apiClient.put<WikiPage>(`/api/v1/pages/${slug}`, update),

  /** Save full page content (for editor) */
  savePageContent: (slug: string, content: string) =>
    apiClient.put<{ success: boolean; slug: string; message: string }>(`/api/v1/pages/${slug}`, { content }),

  deletePage: (slug: string) => apiClient.del<void>(`/api/v1/pages/${slug}`),

  search: (q: string) => apiClient.get<SearchResult[]>(`/api/v1/search?q=${encodeURIComponent(q)}`),

  query: (question: string, save_analysis = false) =>
    apiClient.post<QueryResponse>('/api/v1/query', { question, save_analysis }),
}
