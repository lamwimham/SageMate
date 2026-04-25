import { useCron, useCronToggle, useCronRunNow } from '@/hooks/useSystem'
import { EmptyState } from '@/components/ui/EmptyState'
import { cn } from '@/lib/utils'
import { useState } from 'react'

function ToggleSwitch({ enabled, onToggle, loading }: { enabled: boolean; onToggle: () => void; loading?: boolean }) {
  return (
    <button
      onClick={onToggle}
      disabled={loading}
      className={cn(
        'relative w-10 h-5 rounded-full transition-colors duration-200',
        enabled ? 'bg-accent-living' : 'bg-bg-elevated border border-border-subtle',
        loading && 'opacity-50 cursor-wait'
      )}
    >
      <div className={cn(
        'absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200',
        enabled ? 'translate-x-5' : 'translate-x-0.5'
      )} />
    </button>
  )
}

function formatLastRun(iso: string | null): string {
  if (!iso) return '从未运行'
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin} 分钟前`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr} 小时前`
  return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

export function CronTab() {
  const { data: cronStatus, isLoading } = useCron()
  const toggle = useCronToggle()
  const runNow = useCronRunNow()
  const [runningTask, setRunningTask] = useState<string | null>(null)

  if (isLoading) {
    return (
      <div className="animate-fade-up">
        <div className="mb-5">
          <h2 className="text-lg font-semibold text-text-primary">定时任务</h2>
          <p className="text-sm mt-0.5 text-text-tertiary">后台自动编译与检查任务状态</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="card p-5 h-[100px] animate-pulse bg-bg-elevated/30" />
          ))}
        </div>
      </div>
    )
  }

  if (!cronStatus) {
    return (
      <div className="animate-fade-up">
        <div className="mb-5">
          <h2 className="text-lg font-semibold text-text-primary">定时任务</h2>
          <p className="text-sm mt-0.5 text-text-tertiary">后台自动编译与检查任务状态</p>
        </div>
        <EmptyState icon="clock" title="无法获取定时任务状态" />
      </div>
    )
  }

  const handleToggle = (task: string) => {
    const current = task === 'auto_compile' ? cronStatus.auto_compile.enabled : cronStatus.lint_check.enabled
    toggle.mutate({ task, enabled: !current })
  }

  const handleRunNow = async (task: string) => {
    setRunningTask(task)
    try {
      await runNow.mutateAsync(task)
    } finally {
      setRunningTask(null)
    }
  }

  return (
    <div className="animate-fade-up">
      <div className="mb-5">
        <h2 className="text-lg font-semibold text-text-primary">定时任务</h2>
        <p className="text-sm mt-0.5 text-text-tertiary">后台自动编译与检查任务状态</p>
      </div>

      {/* Scheduler Status */}
      <div className="card p-5 mb-4">
        <div className="flex items-center justify-between">
          <div className="text-xs font-semibold uppercase tracking-wider text-text-muted">调度器状态</div>
          <span className={cn('inline-flex items-center gap-1.5 text-xs font-medium', cronStatus.running ? 'text-accent-living' : 'text-accent-danger')}>
            <span className={cn('w-2 h-2 rounded-full', cronStatus.running && 'animate-pulse', cronStatus.running ? 'bg-accent-living' : 'bg-accent-danger')} />
            {cronStatus.running ? '运行中' : '已停止'}
          </span>
        </div>
        <div className="text-2xl font-bold font-mono text-text-primary mt-2">{cronStatus.active_tasks} 个活跃任务</div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Auto Compile */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="text-xs font-semibold uppercase tracking-wider text-text-muted">自动编译</div>
            <ToggleSwitch
              enabled={cronStatus.auto_compile.enabled}
              onToggle={() => handleToggle('auto_compile')}
              loading={toggle.isPending}
            />
          </div>
          <div className="text-xs mt-0.5 font-mono text-text-muted">
            每 {Math.floor(cronStatus.auto_compile.interval_seconds / 60)} 分钟 · 上次：{formatLastRun(cronStatus.auto_compile.last_run)}
          </div>
          <button
            onClick={() => handleRunNow('auto_compile')}
            disabled={runNow.isPending || runningTask === 'auto_compile'}
            className="mt-3 w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition bg-bg-elevated text-text-secondary hover:bg-bg-hover disabled:opacity-40"
          >
            {runningTask === 'auto_compile' ? (
              <div className="w-3 h-3 border border-accent-neural border-t-transparent rounded-full animate-spin" />
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
            )}
            {runningTask === 'auto_compile' ? '编译中...' : '立即运行'}
          </button>
        </div>

        {/* Lint Check */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="text-xs font-semibold uppercase tracking-wider text-text-muted">健康检查</div>
            <ToggleSwitch
              enabled={cronStatus.lint_check.enabled}
              onToggle={() => handleToggle('lint_check')}
              loading={toggle.isPending}
            />
          </div>
          <div className="text-xs mt-0.5 font-mono text-text-muted">
            每 {Math.floor(cronStatus.lint_check.interval_seconds / 60)} 分钟 · 上次：{formatLastRun(cronStatus.lint_check.last_run)}
          </div>
          <button
            onClick={() => handleRunNow('lint_check')}
            disabled={runNow.isPending || runningTask === 'lint_check'}
            className="mt-3 w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition bg-bg-elevated text-text-secondary hover:bg-bg-hover disabled:opacity-40"
          >
            {runningTask === 'lint_check' ? (
              <div className="w-3 h-3 border border-accent-neural border-t-transparent rounded-full animate-spin" />
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
            )}
            {runningTask === 'lint_check' ? '检查中...' : '立即运行'}
          </button>
        </div>
      </div>
    </div>
  )
}
