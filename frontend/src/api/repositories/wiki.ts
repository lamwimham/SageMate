import { apiClient } from '../client'
import type { WikiPage, WikiPageUpdate, IndexEntry, SearchResult, QueryResponse } from '@/types'

export interface IndexResponse {
  content: string
  entries: IndexEntry[]
}

export interface PageDetailResponse {
  page: WikiPage
  content: string
}

export const wikiRepo = {
  getIndex: () => apiClient.get<IndexResponse>('/index'),

  listPages: (category?: string) =>
    apiClient.get<WikiPage[]>(category ? `/pages?category=${category}` : '/pages'),

  getPage: (slug: string) => apiClient.get<PageDetailResponse>(`/pages/${slug}`),

  updatePage: (slug: string, update: WikiPageUpdate) =>
    apiClient.put<WikiPage>(`/pages/${slug}`, update),

  /** Save full page content (for editor) */
  savePageContent: (slug: string, content: string) =>
    apiClient.put<{ success: boolean; slug: string; message: string }>(`/pages/${slug}`, { content }),

  deletePage: (slug: string) => apiClient.del<void>(`/pages/${slug}`),

  search: (q: string) => apiClient.get<SearchResult[]>(`/search?q=${encodeURIComponent(q)}`),

  query: (question: string, save_analysis = false) =>
    apiClient.post<QueryResponse>('/query', { question, save_analysis }),
}
