import { useState } from 'react'
import { cn } from '@/lib/utils'
import { usePageLayout } from '@/hooks/usePageLayout'
import { StatusSidebar } from '@/components/layout/sidebars/StatusSidebar'
import { HealthTab } from '@/components/status/HealthTab'
import { LogTab } from '@/components/status/LogTab'
import { CostTab } from '@/components/status/CostTab'
import { CronTab } from '@/components/status/CronTab'

const TABS = [
  { key: 'health', label: '健康检查', icon: (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
    </svg>
  )},
  { key: 'log', label: '活动日志', icon: (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
    </svg>
  )},
  { key: 'cost', label: '成本统计', icon: (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <line x1="12" y1="1" x2="12" y2="23" />
      <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
    </svg>
  )},
  { key: 'cron', label: '定时任务', icon: (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  )},
] as const

type TabKey = (typeof TABS)[number]['key']

const TAB_COMPONENTS: Record<TabKey, React.ComponentType> = {
  health: HealthTab,
  log: LogTab,
  cost: CostTab,
  cron: CronTab,
}

export default function Status() {
  usePageLayout({
    sidebar: <StatusSidebar />,
  })

  const [activeTab, setActiveTab] = useState<TabKey>('health')
  const ActiveTab = TAB_COMPONENTS[activeTab]

  return (
    <div className="flex-1 overflow-y-auto p-4 sm:p-6">
      {/* Tab Bar */}
      <div className="flex items-center gap-1 mb-5 animate-fade-up border-b border-border-subtle pb-0">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              'flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium transition rounded-t-lg cursor-pointer',
              activeTab === tab.key
                ? 'bg-bg-surface text-accent-neural border border-border-subtle border-b-bg-surface -mb-px'
                : 'text-text-muted border border-transparent hover:text-text-secondary'
            )}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      <ActiveTab />
    </div>
  )
}
