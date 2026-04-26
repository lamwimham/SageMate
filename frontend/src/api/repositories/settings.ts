import { apiClient } from '../client'
import type { AppSettings, SettingsUpdate } from '@/types'

export interface WeChatAccount {
  logged_in: boolean
  /** iLink user ID */
  user_id?: string
  /** Bot ID */
  bot_id?: string
  /** Token saved timestamp */
  saved_at?: string
}

export interface WeChatQRResult {
  success: boolean
  /** Base64 data URI of the QR code PNG image */
  qr_img_base64: string
  /** Raw QR code string for polling */
  qrcode_str: string
}

export interface WeChatPollResult {
  /** "wait" | "scaned" | "confirmed" | "expired" | "error" */
  status: string
  user_id?: string
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
  get: () => apiClient.get<AppSettings>('/api/v1/settings'),
  update: (patch: SettingsUpdate) => apiClient.patch<AppSettings>('/api/v1/settings', patch),
  reset: () => apiClient.post<{ success: boolean }>('/api/v1/settings/reset'),
  wechatAccount: () => apiClient.get<WeChatAccount>('/api/v1/wechat/account'),
  wechatQR: () => apiClient.post<WeChatQRResult>('/api/v1/wechat/qr'),
  wechatPoll: () => apiClient.post<WeChatPollResult>('/api/v1/wechat/qr/poll'),
  wechatLogout: () => apiClient.post<{ success: boolean }>('/api/v1/wechat/logout'),
  getSchema: () => apiClient.get<{ tables: Record<string, SchemaTable> }>('/api/v1/schema'),
}

export const projectsRepo = {
  list: () => apiClient.get<{ projects: Project[]; count: number }>('/api/v1/projects'),
  create: (data: { name: string; root_path?: string }) =>
    apiClient.post<{ success: boolean; project: Project }>('/api/v1/projects', data),
  get: (id: string) => apiClient.get<{ project: Project }>(`/api/v1/projects/${id}`),
  update: (id: string, data: { name?: string }) =>
    apiClient.patch<{ success: boolean; project: Project }>(`/api/v1/projects/${id}`, data),
  activate: (id: string) =>
    apiClient.post<{ success: boolean; project: Project }>(`/api/v1/projects/${id}/activate`),
  delete: (id: string) =>
    apiClient.del<{ success: boolean }>(`/api/v1/projects/${id}`),
  getActive: () => apiClient.get<{ project: Project | null }>('/api/v1/projects/active'),
  scan: (id: string) =>
    apiClient.post<{ project_id: string; files: any[]; count: number }>(`/api/v1/projects/${id}/scan`),
}
