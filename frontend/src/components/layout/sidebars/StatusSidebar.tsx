import { cn } from '@/lib/utils'
import { useLint, useRunLint, useCron, useLogs } from '@/hooks/useSystem'

export function StatusSidebar() {
  const { refetch: refetchLint } = useLint()
  const runLint = useRunLint()
  const { data: cronStatus } = useCron()
  const { data: logData } = useLogs()
  const logContent = logData?.content ?? ''

  const handleRunLint = async () => {
    await runLint.mutateAsync()
    refetchLint()
  }

  return (
    <>
      <div className="px-4 py-3 border-b border-border-subtle">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted">快捷操作</h3>
      </div>
      <div className="px-2 py-2 space-y-0.5">
        <button
          onClick={handleRunLint}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg transition text-sm text-left text-text-secondary hover:bg-bg-hover"
        >
          <span className="w-6 text-center">🔄</span> 重新健康检查
        </button>
        <button
          onClick={() => window.location.reload()}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg transition text-sm text-left text-text-secondary hover:bg-bg-hover"
        >
          <span className="w-6 text-center">📊</span> 刷新状态
        </button>
        {logContent && (
          <a
            href="/data/log.md"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3 px-3 py-2 rounded-lg transition text-sm text-text-secondary hover:bg-bg-hover"
          >
            <span className="w-6 text-center">📥</span> 导出日志
          </a>
        )}

        {cronStatus && (
          <>
            <div className="border-t border-border-subtle my-2" />
            <div className="px-3 py-2">
              <div className="text-[10px] font-semibold uppercase tracking-wider mb-2 text-text-muted">调度器</div>
              <div className={cn('flex items-center gap-1.5 text-xs', cronStatus.running ? 'text-accent-living' : 'text-accent-danger')}>
                <span className={cn('w-2 h-2 rounded-full', cronStatus.running && 'animate-pulse', cronStatus.running ? 'bg-accent-living' : 'bg-accent-danger')} />
                {cronStatus.running ? '运行中' : '已停止'}
              </div>
            </div>
          </>
        )}
      </div>
    </>
  )
}
