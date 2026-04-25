import { useCron } from '@/hooks/useSystem'
import { EmptyState } from '@/components/ui/EmptyState'
import { cn } from '@/lib/utils'

export function CronTab() {
  const { data: cronStatus } = useCron()

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

  return (
    <div className="animate-fade-up">
      <div className="mb-5">
        <h2 className="text-lg font-semibold text-text-primary">定时任务</h2>
        <p className="text-sm mt-0.5 text-text-tertiary">后台自动编译与检查任务状态</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="text-xs font-semibold uppercase tracking-wider text-text-muted">调度器状态</div>
            <span className={cn('inline-flex items-center gap-1.5 text-xs font-medium', cronStatus.running ? 'text-accent-living' : 'text-accent-danger')}>
              <span className={cn('w-2 h-2 rounded-full', cronStatus.running && 'animate-pulse', cronStatus.running ? 'bg-accent-living' : 'bg-accent-danger')} />
              {cronStatus.running ? '运行中' : '已停止'}
            </span>
          </div>
          <div className="text-2xl font-bold font-mono text-text-primary">{cronStatus.active_tasks} 个活跃任务</div>
        </div>
        <div className="card p-5">
          <div className="text-xs font-semibold uppercase tracking-wider mb-3 text-text-muted">自动编译</div>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium text-text-primary">{cronStatus.auto_compile.enabled ? '已启用' : '已禁用'}</div>
              <div className="text-xs mt-0.5 font-mono text-text-muted">每 {Math.floor(cronStatus.auto_compile.interval_seconds / 60)} 分钟</div>
            </div>
            <div className={cn(
              'w-9 h-9 rounded-lg flex items-center justify-center',
              cronStatus.auto_compile.enabled
                ? 'bg-accent-living/8 border border-accent-living/15'
                : 'bg-bg-elevated border border-border-subtle'
            )}>
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={cn('w-4 h-4', cronStatus.auto_compile.enabled ? 'text-accent-living' : 'text-text-muted')}>
                <polyline points="23 4 23 10 17 10" />
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
              </svg>
            </div>
          </div>
        </div>
        <div className="card p-5">
          <div className="text-xs font-semibold uppercase tracking-wider mb-3 text-text-muted">健康检查</div>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium text-text-primary">{cronStatus.lint_check.enabled ? '已启用' : '已禁用'}</div>
              <div className="text-xs mt-0.5 font-mono text-text-muted">每 {Math.floor(cronStatus.lint_check.interval_seconds / 60)} 分钟</div>
            </div>
            <div className={cn(
              'w-9 h-9 rounded-lg flex items-center justify-center',
              cronStatus.lint_check.enabled
                ? 'bg-accent-neural/8 border border-accent-neural/15'
                : 'bg-bg-elevated border border-border-subtle'
            )}>
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={cn('w-4 h-4', cronStatus.lint_check.enabled ? 'text-accent-neural' : 'text-text-muted')}>
                <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
              </svg>
            </div>
          </div>
        </div>
        <div className="card p-5">
          <div className="text-xs font-semibold uppercase tracking-wider mb-3 text-text-muted">系统信息</div>
          <div className="text-sm font-medium text-text-primary">SageMate Core v0.4.0</div>
          <div className="text-xs mt-0.5 text-text-muted">本地优先知识库</div>
        </div>
      </div>
    </div>
  )
}
