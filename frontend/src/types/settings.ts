export interface AppSettings {
  llm_base_url: string
  llm_api_key: string
  llm_model: string

  vision_base_url: string
  vision_api_key: string
  vision_model: string

  wechat_base_url: string
  wechat_api_key: string
  wechat_model: string
  wechat_image_policy: string

  compiler_max_source_chars: number
  compiler_max_wiki_context_chars: number

  lint_stale_days: number

  cron_auto_compile_enabled: boolean
  cron_auto_compile_interval: number
  cron_lint_enabled: boolean
  cron_lint_interval: number

  url_tier1_timeout: number
  url_tier2_timeout: number
  url_cache_enabled: boolean
  url_max_concurrent: number
  url_retry_attempts: number
  url_proxy_enabled: boolean
  url_proxy_url: string

  watcher_debounce_ms: number

  raw_dir_path: string
}

export type SettingsUpdate = Partial<Omit<AppSettings, 'wechat_api_key' | 'llm_api_key' | 'vision_api_key'>> & {
  llm_api_key?: string
  vision_api_key?: string
  wechat_api_key?: string
}
