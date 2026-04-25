import { useIngestStore } from '@/stores/ingest'
import { cn } from '@/lib/utils'

function StepIcon({ state, index }: { state: string; index: number }) {
  if (state === 'done') return <span className="text-accent-living">✓</span>
  if (state === 'error') return <span className="text-accent-danger">✕</span>
  if (state === 'active') return <span className="w-2 h-2 rounded-full bg-current animate-pulse" />
  return <span>{index + 1}</span>
}

export function IngestProgressPanel() {
  const { progress, resetProgress } = useIngestStore()
  const { status, steps, pct, error, taskId } = progress

  const stepStatus = (_stepKey: string, idx: number) => {
    if (status === 'idle' || status === 'connecting') return 'pending'
    const stepIdx = steps.findIndex((s) => s.key === status)
    if (status === 'failed') {
      return idx < stepIdx ? 'done' : idx === stepIdx ? 'error' : 'pending'
    }
    if (status === 'completed') return 'done'
    return idx < stepIdx ? 'done' : idx === stepIdx ? 'active' : 'pending'
  }

  if (status === 'idle' && !taskId) {
    return (
      <aside className="bg-bg-surface border-l border-border-subtle overflow-hidden flex flex-col" aria-label="详情面板">
        <div className="px-4 py-3 border-b border-border-subtle">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted">处理状态</h3>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center p-6">
          <div className="text-3xl mb-3 opacity-40">⏳</div>
          <p className="text-xs text-text-muted text-center">提交数据后，处理进度将显示在这里</p>
        </div>
      </aside>
    )
  }

  return (
    <aside className="bg-bg-surface border-l border-border-subtle overflow-hidden flex flex-col" aria-label="详情面板">
      <div className="px-4 py-3 border-b border-border-subtle flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted">处理状态</h3>
        {taskId && (
          <span className="badge text-[12px] bg-bg-elevated text-text-muted border border-border-subtle font-mono">
            #{taskId.slice(0, 8)}
          </span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {status === 'idle' && !taskId && (
          <div className="text-center py-6">
            <div className="text-2xl mb-2 opacity-40">⏳</div>
            <p className="text-xs text-text-muted">等待数据...</p>
          </div>
        )}

        {(status !== 'idle' || taskId) && (
          <div className="animate-fade-up">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-text-secondary">
                {status === 'completed' ? '已完成' : status === 'failed' ? '失败' : status === 'connecting' ? '连接中...' : '处理中...'}
              </span>
              <span className="text-xs text-text-muted">{pct}%</span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-bg-elevated overflow-hidden mb-4">
              <div
                className={cn(
                  'h-full rounded-full transition-all duration-500',
                  status === 'completed' ? 'bg-accent-living' : status === 'failed' ? 'bg-accent-danger' : 'bg-accent-neural'
                )}
                style={{ width: `${pct}%` }}
              />
            </div>

            <div className="space-y-1">
              {steps.map((s, i) => {
                const st = stepStatus(s.key, i)
                return (
                  <div key={s.key}>
                    <div className={cn('flex items-start gap-2.5 py-1.5', st === 'pending' && 'opacity-60')}>
                      <div
                        className={cn(
                          'w-6 h-6 rounded-full flex items-center justify-center text-[12px] font-bold shrink-0 border-[1.5px] transition',
                          st === 'done' && 'bg-accent-living/10 text-accent-living border-accent-living/25',
                          st === 'active' && 'bg-accent-neural/10 text-accent-neural border-accent-neural',
                          st === 'error' && 'bg-accent-danger/10 text-accent-danger border-accent-danger/25',
                          st === 'pending' && 'bg-transparent text-text-muted border-border-medium'
                        )}
                      >
                        <StepIcon state={st} index={i} />
                      </div>
                      <div className="flex-1 pt-0.5">
                        <div
                          className={cn(
                            'text-[13px] font-medium',
                            st === 'done' && 'text-accent-living',
                            st === 'active' && 'text-accent-neural',
                            st === 'error' && 'text-accent-danger',
                            st === 'pending' && 'text-text-muted'
                          )}
                        >
                          {s.label}
                        </div>
                        <div className="text-xs text-text-tertiary">{s.desc}</div>
                      </div>
                    </div>
                    {i < steps.length - 1 && (
                      <div className={cn('w-px h-4 ml-3', st === 'done' ? 'bg-accent-living/30' : 'bg-border-subtle')} />
                    )}
                  </div>
                )
              })}
            </div>

            {status === 'completed' && (
              <div className="mt-4 p-3 rounded-xl bg-accent-living/5 border border-accent-living/15">
                <div className="text-xs font-medium text-accent-living">✅ 编译成功</div>
                <div className="text-xs text-text-tertiary mt-1">已在 Wiki 中生成页面</div>
                <a href="/wiki" className="text-xs text-accent-neural mt-2 inline-block">查看知识库 →</a>
              </div>
            )}

            {status === 'failed' && (
              <div className="mt-4 p-3 rounded-xl bg-accent-danger/5 border border-accent-danger/15">
                <div className="text-xs font-medium text-accent-danger">❌ 处理失败</div>
                <div className="text-xs text-accent-danger mt-1 font-mono">{error || '未知错误'}</div>
              </div>
            )}

            {status === 'completed' && (
              <button
                onClick={resetProgress}
                className="mt-3 w-full text-xs text-text-muted hover:text-text-primary transition py-2"
              >
                重置
              </button>
            )}
          </div>
        )}
      </div>
    </aside>
  )
}
