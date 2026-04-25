import { useState, useEffect, useCallback } from 'react'
import { cn } from '@/lib/utils'
import { usePageLayout } from '@/hooks/usePageLayout'
import { Modal } from '@/components/ui/Modal'
import { ThemeToggle } from '@/components/ui/ThemeToggle'
import { SettingsSidebar } from '@/components/layout/sidebars/SettingsSidebar'
import { useSettings, useUpdateSettings, useResetSettings, useWeChatAccount, useWeChatQR, useWeChatPoll, useWeChatLogout, useProjects, useActiveProject, useCreateProject, useActivateProject, useDeleteProject, useSchema } from '@/hooks/useSettings'
import type { AppSettings, SettingsUpdate } from '@/types'
import type { Project } from '@/api/repositories/settings'

// ============================================================
// Settings Grouped Architecture
// ============================================================

interface SettingsSection {
  key: string
  label: string
  icon: React.ReactNode
  fields: string[]
}

interface SettingsGroup {
  key: string
  label: string
  icon: React.ReactNode
  sections: SettingsSection[]
}

const SETTING_GROUPS: SettingsGroup[] = [
  {
    key: 'system',
    label: '系统',
    icon: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>,
    sections: [
      { key: 'theme', label: '外观', icon: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><circle cx="12" cy="12" r="10" /><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" /></svg>, fields: [] },
      { key: 'lint', label: '巡检', icon: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><path d="M22 12h-4l-3 9L9 3l-3 9H2" /></svg>, fields: ['lint_stale_days'] },
      { key: 'compiler', label: '编译', icon: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><polyline points="16 18 22 12 16 6" /><polyline points="8 6 2 12 8 18" /></svg>, fields: ['compiler_max_source_chars', 'compiler_max_wiki_context_chars'] },
      { key: 'cron', label: '定时任务', icon: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>, fields: ['cron_auto_compile_enabled', 'cron_auto_compile_interval', 'cron_lint_enabled', 'cron_lint_interval'] },
      { key: 'url', label: 'URL 采集器', icon: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" /><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" /></svg>, fields: ['url_tier1_timeout', 'url_tier2_timeout', 'url_cache_enabled', 'url_max_concurrent', 'url_retry_attempts', 'url_proxy_enabled', 'url_proxy_url'] },
      { key: 'watcher', label: '文件监视', icon: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></svg>, fields: ['watcher_debounce_ms'] },
      { key: 'projects', label: '项目管理', icon: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" /></svg>, fields: [] },
    ],
  },
  {
    key: 'model',
    label: '模型',
    icon: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><rect x="2" y="2" width="20" height="8" rx="2" ry="2" /><rect x="2" y="14" width="20" height="8" rx="2" ry="2" /><line x1="6" y1="6" x2="6.01" y2="6" /><line x1="6" y1="18" x2="6.01" y2="18" /></svg>,
    sections: [
      { key: 'llm', label: '文本模型', icon: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>, fields: ['llm_model', 'llm_base_url', 'llm_api_key'] },
      { key: 'vision', label: 'OCR 模型', icon: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></svg>, fields: ['vision_model', 'vision_base_url', 'vision_api_key'] },
    ],
  },
  {
    key: 'plugin',
    label: '插件',
    icon: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" /><polyline points="15 3 21 3 21 9" /><line x1="10" y1="14" x2="21" y2="3" /></svg>,
    sections: [
      { key: 'wechat', label: '微信插件', icon: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>, fields: [] },
    ],
  },
]

const FIELD_META: Record<string, { label: string; hint?: string; type: 'text' | 'password' | 'number' | 'toggle' } > = {
  llm_model: { label: '模型名称', hint: '例如 qwen-plus, gpt-4o, claude-3-sonnet', type: 'text' },
  llm_base_url: { label: 'API Base URL', type: 'text' },
  llm_api_key: { label: 'API Key', type: 'password' },
  vision_model: { label: '模型名称', hint: '用于 PDF 图片提取和 OCR', type: 'text' },
  vision_base_url: { label: 'API Base URL', type: 'text' },
  vision_api_key: { label: 'API Key', type: 'password' },
  wechat_model: { label: '模型名称', type: 'text' },
  wechat_base_url: { label: 'API Base URL', type: 'text' },
  wechat_api_key: { label: 'API Key', type: 'password' },
  compiler_max_source_chars: { label: '最大源文档字符数', hint: '发送给 LLM 的源文档最大长度', type: 'number' },
  compiler_max_wiki_context_chars: { label: '最大 Wiki 上下文字符数', hint: '读取已有 Wiki 页面作为上下文的最大长度', type: 'number' },
  lint_stale_days: { label: '过期天数阈值', hint: '超过此天数未更新的页面标记为过期', type: 'number' },
  cron_auto_compile_enabled: { label: '自动编译', hint: '定时将新源文件编译为 Wiki', type: 'toggle' },
  cron_auto_compile_interval: { label: '自动编译间隔（秒）', type: 'number' },
  cron_lint_enabled: { label: '自动 Lint 检查', hint: '定时检查知识库健康状态', type: 'toggle' },
  cron_lint_interval: { label: 'Lint 检查间隔（秒）', type: 'number' },
  url_tier1_timeout: { label: 'Tier1 超时（秒）', hint: 'curl_cffi 请求超时', type: 'number' },
  url_tier2_timeout: { label: 'Tier2 超时（秒）', hint: 'Playwright 页面加载超时', type: 'number' },
  url_cache_enabled: { label: '启用缓存', type: 'toggle' },
  url_max_concurrent: { label: '最大并发请求数', type: 'number' },
  url_retry_attempts: { label: '最大重试次数', type: 'number' },
  url_proxy_enabled: { label: '启用代理', type: 'toggle' },
  url_proxy_url: { label: '代理 URL', hint: 'http://127.0.0.1:7890', type: 'text' },
  watcher_debounce_ms: { label: '防抖间隔（毫秒）', hint: '文件变更后等待多久触发同步', type: 'number' },
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={cn(
        'relative w-10 h-[22px] rounded-full transition cursor-pointer shrink-0',
        checked ? 'bg-accent-neural' : 'bg-border-strong'
      )}
    >
      <span
        className={cn(
          'absolute top-[2px] left-[2px] w-[18px] h-[18px] rounded-full bg-white shadow transition-transform',
          checked && 'translate-x-[18px]'
        )}
      />
    </button>
  )
}

function PasswordField({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  const [visible, setVisible] = useState(false)
  return (
    <div className="relative">
      <input
        type={visible ? 'text' : 'password'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="input pr-9"
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary"
      >
        {visible ? '🙈' : '👁️'}
      </button>
    </div>
  )
}

export default function Settings() {
  usePageLayout({
    sidebar: <SettingsSidebar />,
  })

  const { data: settings, isLoading } = useSettings()
  const updateMutation = useUpdateSettings()
  const resetMutation = useResetSettings()

  const [draft, setDraft] = useState<Partial<AppSettings>>({})
  const [saveStatus, setSaveStatus] = useState<'' | 'saving' | 'saved' | 'error'>('')

  // WeChat modal state
  const [qrModalOpen, setQrModalOpen] = useState(false)
  const [qrUrl, setQrUrl] = useState('')
  const [qrStatus, setQrStatus] = useState<'fetching' | 'showing' | 'expired' | 'error'>('fetching')
  const [qrErrorMsg, setQrErrorMsg] = useState('')

  const { data: wechatAccount } = useWeChatAccount()
  const wechatQRMutation = useWeChatQR()
  const wechatPollMutation = useWeChatPoll()
  const wechatLogoutMutation = useWeChatLogout()

  useEffect(() => {
    if (settings) {
      setDraft(settings)
    }
  }, [settings])

  const setField = useCallback((key: keyof AppSettings, value: unknown) => {
    setDraft((prev) => ({ ...prev, [key]: value }))
  }, [])

  const handleSave = async () => {
    setSaveStatus('saving')
    try {
      const patch: SettingsUpdate = {}
      for (const key of Object.keys(draft) as Array<keyof AppSettings>) {
        if (draft[key] !== undefined && draft[key] !== settings?.[key]) {
          ;(patch as Record<string, unknown>)[key] = draft[key]
        }
      }
      await updateMutation.mutateAsync(patch)
      setSaveStatus('saved')
      setTimeout(() => setSaveStatus(''), 2000)
    } catch {
      setSaveStatus('error')
    }
  }

  const handleReset = async () => {
    if (!confirm('确定要恢复默认设置吗？所有自定义设置将被清除。')) return
    await resetMutation.mutateAsync()
  }

  const fetchQR = async () => {
    setQrStatus('fetching')
    try {
      const res = await wechatQRMutation.mutateAsync()
      if (res.qr_url) {
        setQrUrl(res.qr_url)
        setQrStatus('showing')
        startPolling()
      } else {
        setQrStatus('error')
        setQrErrorMsg('获取二维码失败')
      }
    } catch (e) {
      setQrStatus('error')
      setQrErrorMsg(e instanceof Error ? e.message : '网络错误')
    }
  }

  const startPolling = useCallback(() => {
    const interval = setInterval(async () => {
      try {
        const res = await wechatPollMutation.mutateAsync()
        if (res.status === 'success') {
          clearInterval(interval)
          setQrModalOpen(false)
        } else if (res.status === 'expired') {
          clearInterval(interval)
          setQrStatus('expired')
        }
      } catch {
        // ignore polling errors
      }
    }, 2000)
    // Auto stop after 5 minutes
    setTimeout(() => clearInterval(interval), 300000)
  }, [wechatPollMutation])

  const openQRModal = () => {
    setQrModalOpen(true)
    fetchQR()
  }

  const closeQRModal = () => {
    setQrModalOpen(false)
    setQrStatus('fetching')
    setQrUrl('')
  }

  if (isLoading) {
    return (
      <div className="p-8 text-text-secondary">
        <div className="animate-pulse">加载设置中...</div>
      </div>
    )
  }

  return (
    <div className="p-4 sm:p-6 max-w-4xl h-full overflow-y-auto">
      <div className="space-y-6">
        {SETTING_GROUPS.map((group) => (
          <div key={group.key}>
            {/* Group Header */}
            <div className="flex items-center gap-2 mb-3">
              <span className="text-[15px]">{group.icon}</span>
              <h2 className="text-[15px] font-semibold uppercase tracking-wider text-text-muted">{group.label}</h2>
            </div>

            {/* Group Sections */}
            <div className="space-y-4">
              {group.sections.map((section) => (
          <div
            key={section.key}
            id={`section-${section.key}`}
            className="card overflow-hidden"
            style={{ padding: 0 }}
          >
            <div className="w-full flex items-center justify-between px-5 py-3.5">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-md flex items-center justify-center text-sm bg-accent-neural/8 border border-accent-neural/15">
                  {section.icon}
                </div>
                <span className="text-[14px] font-semibold text-text-primary">{section.label}</span>
              </div>
            </div>

            <div className="px-5 pb-5 grid grid-cols-1 md:grid-cols-2 gap-4">
                {section.key === 'wechat' && (
                  <div className="md:col-span-2">
                    <div className="flex items-center gap-3 p-3 rounded-xl bg-bg-elevated/50 border border-border-subtle/60">
                      {!wechatAccount?.logged_in ? (
                        <>
                          <div className="w-9 h-9 rounded-lg bg-accent-growth/10 border border-accent-growth/15 flex items-center justify-center">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 text-accent-growth">
                              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                              <line x1="12" y1="9" x2="12" y2="13" />
                              <line x1="12" y1="17" x2="12.01" y2="17" />
                            </svg>
                          </div>
                          <div className="flex-1">
                            <div className="text-sm font-medium text-text-primary">未登录</div>
                            <div className="text-xs text-text-muted">扫码绑定微信通信通道</div>
                          </div>
                          <button onClick={openQRModal} className="btn btn-primary text-sm">扫码登录</button>
                        </>
                      ) : (
                        <>
                          <div className="w-9 h-9 rounded-lg bg-accent-living/10 border border-accent-living/15 flex items-center justify-center">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 text-accent-living">
                              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                              <polyline points="22 4 12 14.01 9 11.01" />
                            </svg>
                          </div>
                          <div className="flex-1">
                            <div className="text-sm font-medium text-text-primary">{wechatAccount.user_name || '已登录'}</div>
                            <div className="text-xs text-text-muted">{wechatAccount.saved_at || '--'}</div>
                          </div>
                          <button onClick={openQRModal} className="btn btn-secondary text-sm">更换账号</button>
                          <button
                            onClick={() => wechatLogoutMutation.mutate()}
                            className="btn btn-danger text-sm"
                          >
                            退出
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                )}

                {/* Custom: Theme Section */}
                {section.key === 'theme' && <ThemeToggle />}

                {/* Custom: Projects Section */}
                {section.key === 'projects' && (
                  <div className="md:col-span-2">
                    <ProjectManager />
                  </div>
                )}

                {/* Custom: Schema Section */}
                {section.key === 'schema' && (
                  <div className="md:col-span-2">
                    <SchemaViewer />
                  </div>
                )}

                {section.fields.map((fieldKey) => {
                  const meta = FIELD_META[fieldKey]
                  if (!meta) return null
                  const value = draft[fieldKey as keyof AppSettings] ?? ''
                  return (
                    <div key={fieldKey} className="flex flex-col gap-1.5">
                      <label className="text-[13px] font-medium text-text-secondary flex items-center gap-1.5">
                        {meta.label}
                      </label>
                      {meta.type === 'toggle' && (
                        <div className="flex items-center gap-3">
                          <Toggle
                            checked={!!value}
                            onChange={(v) => setField(fieldKey as keyof AppSettings, v)}
                          />
                          <span className="text-sm font-medium text-text-primary">{meta.label}</span>
                        </div>
                      )}
                      {meta.type === 'text' && (
                        <input
                          type="text"
                          value={String(value)}
                          onChange={(e) => setField(fieldKey as keyof AppSettings, e.target.value)}
                          placeholder={meta.hint}
                          className="input"
                        />
                      )}
                      {meta.type === 'password' && (
                        <PasswordField
                          value={String(value)}
                          onChange={(v) => setField(fieldKey as keyof AppSettings, v)}
                          placeholder="sk-..."
                        />
                      )}
                      {meta.type === 'number' && (
                        <input
                          type="number"
                          value={String(value)}
                          onChange={(e) => {
                            const num = e.target.value === '' ? '' : Number(e.target.value)
                            setField(fieldKey as keyof AppSettings, num)
                          }}
                          className="input"
                        />
                      )}
                      {meta.hint && meta.type !== 'text' && (
                        <div className="text-xs text-text-muted">{meta.hint}</div>
                      )}
                    </div>
                  )
                })}
              </div>
          </div>
        ))}
            </div>
          </div>
        ))}
      </div>

      {/* Save bar */}
      <div className="mt-8 p-4 rounded-xl bg-bg-surface border border-border-subtle flex items-center justify-between">
        <div className="text-[13px] flex items-center gap-1.5">
          {saveStatus === 'saving' && <span className="text-text-muted">保存中...</span>}
          {saveStatus === 'saved' && <span className="text-accent-living">✓ 已保存</span>}
          {saveStatus === 'error' && <span className="text-accent-danger">保存失败</span>}
          {saveStatus === '' && <span className="text-text-muted">所有更改自动保存到本地数据库</span>}
        </div>
        <div className="flex items-center gap-3">
          <button onClick={handleReset} className="btn btn-secondary text-sm">恢复默认</button>
          <button onClick={handleSave} className="btn btn-primary text-sm">保存设置</button>
        </div>
      </div>

      {/* QR Modal */}
      <Modal open={qrModalOpen} onClose={closeQRModal} title="微信登录" size="sm">
        <div className="text-center">
          {qrStatus === 'fetching' && (
            <div className="py-10">
              <div className="w-6 h-6 border-3 border-accent-neural border-t-transparent rounded-full animate-spin mx-auto" />
              <p className="mt-3 text-sm text-text-secondary">正在获取二维码...</p>
            </div>
          )}
          {qrStatus === 'showing' && (
            <div>
              <img src={qrUrl} alt="微信扫码" className="w-[220px] h-[220px] rounded-xl border border-border-subtle bg-white mx-auto" />
              <p className="mt-4 text-sm text-text-secondary">打开微信 → 扫一扫 → 确认登录</p>
              <p className="mt-2 text-[13px] text-accent-neural font-medium">等待扫码...</p>
            </div>
          )}
          {qrStatus === 'expired' && (
            <div className="py-10">
              <div className="w-12 h-12 mx-auto mb-3 rounded-xl bg-accent-growth/5 flex items-center justify-center">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-6 h-6 text-accent-growth">
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
              </div>
              <p className="text-sm text-text-secondary">二维码已过期</p>
              <button onClick={fetchQR} className="btn btn-primary mt-3">刷新二维码</button>
            </div>
          )}
          {qrStatus === 'error' && (
            <div className="py-10">
              <div className="w-12 h-12 mx-auto mb-3 rounded-xl bg-accent-danger/5 flex items-center justify-center">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-6 h-6 text-accent-danger">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="15" y1="9" x2="9" y2="15" />
                  <line x1="9" y1="9" x2="15" y2="15" />
                </svg>
              </div>
              <p className="text-sm text-accent-danger">{qrErrorMsg}</p>
              <button onClick={fetchQR} className="btn btn-primary mt-3">重试</button>
            </div>
          )}
        </div>
      </Modal>
    </div>
  )
}

// ── Project Manager Component ────────────────────────────────

function ProjectManager() {
  const { data, isLoading } = useProjects()
  const { data: activeData } = useActiveProject()
  const createProject = useCreateProject()
  const activateProject = useActivateProject()
  const deleteProject = useDeleteProject()
  const [showAdd, setShowAdd] = useState(false)
  const [newPath, setNewPath] = useState('')
  const [newName, setNewName] = useState('')

  const projects = data?.projects ?? []
  const activeId = activeData?.project?.id ?? null

  const handleCreate = async () => {
    if (!newPath.trim()) return
    await createProject.mutateAsync({
      root_path: newPath.trim(),
      name: newName.trim() || undefined,
    })
    setNewPath('')
    setNewName('')
    setShowAdd(false)
  }

  const handleActivate = async (id: string) => {
    await activateProject.mutateAsync(id)
  }

  const handleDelete = async (id: string) => {
    if (!confirm('确定删除该项目？（不会删除文件）')) return
    await deleteProject.mutateAsync(id)
  }

  if (isLoading) return <div className="text-text-muted animate-pulse">加载中...</div>

  return (
    <div className="space-y-4">
      {/* Project List */}
      {projects.length > 0 ? (
        <div className="space-y-2">
          {projects.map((p: Project) => (
            <div
              key={p.id}
              className={cn(
                'flex items-center gap-3 p-3 rounded-xl border transition',
                p.id === activeId
                  ? 'bg-accent-neural/5 border-accent-neural/20'
                  : 'bg-bg-elevated border-border-subtle hover:border-border-medium'
              )}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-text-primary">{p.name}</span>
                  {p.id === activeId && (
                    <span className="text-[12px] px-1.5 py-0.5 rounded-full bg-accent-neural/15 text-accent-neural font-medium">
                      活跃
                    </span>
                  )}
                </div>
                <div className="text-xs text-text-muted font-mono mt-0.5 truncate">{p.root_path}</div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {p.id !== activeId && (
                  <button
                    onClick={() => handleActivate(p.id)}
                    className="btn btn-primary text-xs px-2.5"
                  >
                    激活
                  </button>
                )}
                {p.id !== activeId && (
                  <button
                    onClick={() => handleDelete(p.id)}
                    className="text-xs text-text-muted hover:text-accent-danger transition"
                  >
                    删除
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-8 text-text-muted">
          <div className="text-2xl mb-2 opacity-40">📁</div>
          <p className="text-sm">暂无项目，点击下方按钮添加</p>
        </div>
      )}

      {/* Add Project */}
      {!showAdd ? (
        <button
          onClick={() => setShowAdd(true)}
          className="w-full py-2.5 rounded-xl border border-dashed border-border-medium text-text-muted hover:text-accent-neural hover:border-accent-neural/40 transition text-sm"
        >
          ＋ 添加项目
        </button>
      ) : (
        <div className="p-4 rounded-xl bg-bg-elevated border border-border-subtle space-y-3">
          <div>
            <label className="text-[13px] font-medium text-text-secondary">目录路径</label>
            <input
              type="text"
              value={newPath}
              onChange={(e) => setNewPath(e.target.value)}
              placeholder="/path/to/your/project"
              className="input mt-1 w-full"
            />
          </div>
          <div>
            <label className="text-[13px] font-medium text-text-secondary">
              项目名 <span className="text-text-muted text-[12px]">（留空使用目录名）</span>
            </label>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="MyProject"
              className="input mt-1 w-full"
            />
          </div>
          <div className="flex items-center gap-3 pt-1">
            <button
              onClick={handleCreate}
              disabled={createProject.isPending || !newPath.trim()}
              className="btn btn-primary text-sm disabled:opacity-50"
            >
              {createProject.isPending ? '创建中...' : '确认添加'}
            </button>
            <button
              onClick={() => { setShowAdd(false); setNewPath(''); setNewName('') }}
              className="btn btn-secondary text-sm"
            >
              取消
            </button>
          </div>
        </div>
      )}

      {/* Info */}
      <div className="text-[12px] text-text-muted leading-relaxed">
        <p>💡 项目目录下的文档将自动纳入数据来源（状态：未编译）。</p>
        <p>编译后的 Wiki 页面将输出到 <code className="font-mono text-text-secondary">项目目录/wiki/</code>。</p>
      </div>
    </div>
  )
}

// ── Schema Viewer Component ────────────────────────────────────

function SchemaViewer() {
  const { data, isLoading } = useSchema()
  const tables = data?.tables ?? {}

  if (isLoading) return <div className="text-text-muted animate-pulse">加载 Schema...</div>
  if (!Object.keys(tables).length) return <div className="text-text-muted">暂无 Schema 数据</div>

  return (
    <div className="space-y-4">
      {Object.entries(tables).map(([name, info]) => (
        <div key={name} className="rounded-xl border border-border-subtle bg-bg-elevated overflow-hidden">
          {/* Table Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border-subtle">
            <div className="flex items-center gap-2">
              <span className="text-[13px] font-mono font-bold text-accent-neural">{name}</span>
              <span className="text-[12px] px-1.5 py-0.5 rounded bg-bg-hover text-text-muted">{info.type}</span>
              <span className="text-[12px] text-text-muted">{info.row_count} 行</span>
            </div>
          </div>

          {/* DDL */}
          {info.ddl && (
            <div className="px-4 py-2 border-b border-border-subtle">
              <pre className="text-[12px] font-mono text-text-secondary whitespace-pre-wrap leading-relaxed overflow-x-auto">
                {info.ddl}
              </pre>
            </div>
          )}

          {/* Columns */}
          {info.columns && info.columns.length > 0 && (
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-border-subtle text-text-muted">
                  <th className="text-left px-4 py-2 font-medium">#</th>
                  <th className="text-left px-4 py-2 font-medium">字段</th>
                  <th className="text-left px-4 py-2 font-medium">类型</th>
                  <th className="text-center px-4 py-2 font-medium">PK</th>
                  <th className="text-center px-4 py-2 font-medium">NOT NULL</th>
                  <th className="text-left px-4 py-2 font-medium">默认值</th>
                </tr>
              </thead>
              <tbody>
                {info.columns.map((col) => (
                  <tr key={col.cid} className="border-b border-border-subtle/50 hover:bg-bg-hover/50">
                    <td className="px-4 py-1.5 text-text-muted">{col.cid}</td>
                    <td className="px-4 py-1.5 font-mono text-text-primary">{col.name}</td>
                    <td className="px-4 py-1.5 font-mono text-text-secondary">{col.type || '-'}</td>
                    <td className="px-4 py-1.5 text-center">{col.pk ? '🔑' : ''}</td>
                    <td className="px-4 py-1.5 text-center">{col.notnull ? '✓' : ''}</td>
                    <td className="px-4 py-1.5 font-mono text-text-muted">
                      {col.default !== null && col.default !== undefined ? String(col.default) : 'NULL'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ))}
    </div>
  )
}
