import { cn } from '@/lib/utils'

const SETTING_GROUPS = [
  {
    key: 'system',
    label: '系统',
    icon: '⚙️',
    sections: [
      { key: 'lint', label: '巡检', icon: '🩺' },
      { key: 'compiler', label: '编译', icon: '🔨' },
      { key: 'cron', label: '定时任务', icon: '⏰' },
      { key: 'url', label: 'URL 采集器', icon: '🌐' },
      { key: 'watcher', label: '文件监视', icon: '👁️‍🗨️' },
      { key: 'projects', label: '项目管理', icon: '📁' },
    ],
  },
  {
    key: 'model',
    label: '模型',
    icon: '🧠',
    sections: [
      { key: 'llm', label: '文本模型', icon: '💬' },
      { key: 'vision', label: 'OCR 模型', icon: '👁️' },
    ],
  },
  {
    key: 'plugin',
    label: '插件',
    icon: '🔌',
    sections: [
      { key: 'wechat', label: '微信插件', icon: '💬' },
    ],
  },
]

export function SettingsSidebar() {
  return (
    <>
      {SETTING_GROUPS.map((group) => (
        <div key={group.key} className="border-b border-border-subtle last:border-b-0">
          {/* Group Header */}
          <div className="px-4 py-2">
            <div className="flex items-center gap-1.5">
              <span className="text-xs">{group.icon}</span>
              <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">{group.label}</span>
            </div>
          </div>

          {/* Section Links */}
          <div className="px-2 pb-2 space-y-0.5">
            {group.sections.map((s) => (
              <a
                key={s.key}
                href={`#section-${s.key}`}
                className={cn(
                  'flex items-center gap-2 px-3 py-1.5 rounded-md transition text-xs',
                  'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
                )}
              >
                <span className="text-[12px]">{s.icon}</span>
                <span>{s.label}</span>
              </a>
            ))}
          </div>
        </div>
      ))}
    </>
  )
}
