import { apiClient } from '../client'
import type { AppSettings, SettingsUpdate } from '@/types'

export interface WeChatAccount {
  logged_in: boolean
  user_name?: string
  saved_at?: string
}

export interface WeChatQRResult {
  success: boolean
  qr_url: string
  expire_seconds: number
}

export interface WeChatPollResult {
  status: string
  user_name?: string
}

export interface Project {
  id: string
  name: string
  root_path: string
  wiki_dir_name: string
  assets_dir_name: string
  status: 'active' | 'inactive'
  created_at: string
  updated_at: string
}

export interface SchemaTable {
  type: string
  ddl: string
  columns: Array<{
    cid: number
    name: string
    type: string
    notnull: boolean
    default: string | null
    pk: boolean
  }>
  row_count: number
}

export const settingsRepo = {
  get: () => apiClient.get<AppSettings>('/api/settings'),
  update: (patch: SettingsUpdate) => apiClient.patch<AppSettings>('/api/settings', patch),
  reset: () => apiClient.post<{ success: boolean }>('/api/settings/reset'),
  wechatAccount: () => apiClient.get<WeChatAccount>('/api/wechat/account'),
  wechatQR: () => apiClient.post<WeChatQRResult>('/api/wechat/qr'),
  wechatPoll: () => apiClient.post<WeChatPollResult>('/api/wechat/qr/poll'),
  wechatLogout: () => apiClient.post<{ success: boolean }>('/api/wechat/logout'),
  getSchema: () => apiClient.get<{ tables: Record<string, SchemaTable> }>('/api/schema'),
}

export const projectsRepo = {
  list: () => apiClient.get<{ projects: Project[]; count: number }>('/api/projects'),
  create: (data: { root_path: string; name?: string }) =>
    apiClient.post<{ success: boolean; project: Project }>('/api/projects', data),
  get: (id: string) => apiClient.get<{ project: Project }>(`/api/projects/${id}`),
  update: (id: string, data: { name?: string }) =>
    apiClient.patch<{ success: boolean; project: Project }>(`/api/projects/${id}`, data),
  activate: (id: string) =>
    apiClient.post<{ success: boolean; project: Project }>(`/api/projects/${id}/activate`),
  delete: (id: string) =>
    apiClient.del<{ success: boolean }>(`/api/projects/${id}`),
  getActive: () => apiClient.get<{ project: Project | null }>('/api/projects/active'),
  scan: (id: string) =>
    apiClient.post<{ project_id: string; files: any[]; count: number }>(`/api/projects/${id}/scan`),
}
