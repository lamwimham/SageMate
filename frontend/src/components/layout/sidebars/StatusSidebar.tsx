import { cn } from '@/lib/utils'
import { useRunLint, useCron, useLogs } from '@/hooks/useSystem'

export function StatusSidebar() {
  const runLint = useRunLint()
  const { data: cronStatus } = useCron()
  const { data: logData } = useLogs()
  const logContent = logData?.content ?? ''

  // Debug: log cron status to console
  if (cronStatus) {
    console.log('[StatusSidebar] cronStatus:', cronStatus)
  }

  const handleRunLint = async () => {
    await runLint.mutateAsync()
    // onSuccess already invalidates ['lint'] query → auto-refetch
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
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
            <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/>
          </svg>
          重新健康检查
        </button>
        <button
          onClick={() => window.location.reload()}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg transition text-sm text-left text-text-secondary hover:bg-bg-hover"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
            <path d="M3 3v18h18"/>
            <path d="M18.7 8l-5.1 5.2-2.8-2.7L7 14.3"/>
          </svg>
          刷新状态
        </button>
        {logContent && (
          <a
            href="/data/log.md"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3 px-3 py-2 rounded-lg transition text-sm text-text-secondary hover:bg-bg-hover"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="7 10 12 15 17 10"/>
              <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            导出日志
          </a>
        )}

        {cronStatus && (
          <>
            <div className="border-t border-border-subtle my-2" />
            <div className="px-3 py-2">
              <div className="text-[12px] font-semibold uppercase tracking-wider mb-2 text-text-muted">调度器</div>
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
