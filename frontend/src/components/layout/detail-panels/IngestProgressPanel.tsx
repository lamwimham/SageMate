import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { cn } from '@/lib/utils'
import { useIngestProgress } from '@/hooks/useIngest'

function StepIcon({ state, index }: { state: string; index: number }) {
  if (state === 'done') return <span className="text-accent-living">✓</span>
  if (state === 'error') return <span className="text-accent-danger">✕</span>
  if (state === 'active') return <span className="w-2 h-2 rounded-full bg-current animate-pulse" />
  return <span>{index + 1}</span>
}

const STEP_LABEL_MAP: Record<string, string> = {
  queued: '提交任务',
  parsing: '解析内容',
  reading_context: '读取上下文',
  calling_llm: 'LLM 分析中',
  writing_pages: '生成 Wiki',
  updating_index: '更新索引',
}

interface IngestProgressPanelProps {
  taskId: string | null
}

export function IngestProgressPanel({ taskId }: IngestProgressPanelProps) {
  const navigate = useNavigate()
  const { state, connected, steps, pct } = useIngestProgress(taskId)
  const [logExpanded, setLogExpanded] = useState(false)
  const [copied, setCopied] = useState(false)

  const status = state?.status ?? 'idle'
  const isCompleted = status === 'completed'
  const isFailed = status === 'failed'

  const stepStatus = (_stepKey: string, idx: number) => {
    if (status === 'idle' || status === 'connecting') return 'pending'
    const stepIdx = steps.findIndex((s) => s.key === status)
    if (status === 'failed') {
      return idx < stepIdx ? 'done' : idx === stepIdx ? 'error' : 'pending'
    }
    if (status === 'completed') return 'done'
    return idx < stepIdx ? 'done' : idx === stepIdx ? 'active' : 'pending'
  }

  const handleCopyLog = () => {
    const logText = state
      ? `[${state.updated_at}] ${state.status}\n${state.error || state.message || ''}`
      : ''
    navigator.clipboard.writeText(logText).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const wikiPages = state?.result?.wiki_pages ?? []

  return (
    <aside className="bg-bg-surface border-l border-border-subtle overflow-hidden flex flex-col" aria-label="处理进度">
      <div className="px-4 py-3 border-b border-border-subtle flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted">处理进度</h3>
        {taskId && (
          <span className="badge text-[12px] bg-bg-elevated text-text-muted border border-border-subtle font-mono">
            #{taskId.slice(0, 8)}
          </span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {!connected && status === 'idle' && (
          <div className="text-center py-6">
            <div className="text-2xl mb-2 opacity-40">⏳</div>
            <p className="text-xs text-text-muted">等待任务开始...</p>
          </div>
        )}

        {(connected || status !== 'idle') && (
          <div className="animate-fade-up">
            {/* Progress bar */}
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-text-secondary">
                {isCompleted ? '已完成' : isFailed ? '失败' : connected ? '处理中...' : '连接中...'}
              </span>
              <span className="text-xs text-text-muted">{pct}%</span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-bg-elevated overflow-hidden mb-4">
              <div
                className={cn(
                  'h-full rounded-full transition-all duration-500',
                  isCompleted ? 'bg-accent-living' : isFailed ? 'bg-accent-danger' : 'bg-accent-neural'
                )}
                style={{ width: `${pct}%` }}
              />
            </div>

            {/* Step timeline */}
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

            {/* ── Success Outcome Card ── */}
            {isCompleted && (
              <div className="mt-5 p-4 rounded-xl bg-accent-living/5 border border-accent-living/15 animate-fade-up">
                <div className="flex items-center gap-2 mb-3">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5 text-accent-living">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" />
                  </svg>
                  <span className="text-sm font-semibold text-text-primary">编译完成</span>
                </div>

                {wikiPages.length > 0 ? (
                  <>
                    <p className="text-xs text-text-secondary mb-2">
                      生成了 {wikiPages.length} 个 Wiki 页面：
                    </p>
                    <div className="space-y-1.5 mb-3">
                      {wikiPages.map((page) => (
                        <button
                          key={page.slug}
                          onClick={() => navigate({ to: '/wiki/$slug', params: { slug: page.slug } })}
                          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-bg-surface border border-border-subtle hover:border-accent-neural/40 hover:bg-accent-neural/5 transition text-left group"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 text-text-muted group-hover:text-accent-neural transition">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                            <polyline points="14 2 14 8 20 8" />
                            <line x1="16" y1="13" x2="8" y2="13" />
                            <line x1="16" y1="17" x2="8" y2="17" />
                            <polyline points="10 9 9 9 8 9" />
                          </svg>
                          <span className="text-[13px] text-text-secondary group-hover:text-text-primary transition truncate flex-1">
                            {page.title || page.slug}
                          </span>
                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5 text-text-muted group-hover:text-accent-neural transition">
                            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                            <polyline points="15 3 21 3 21 9" />
                            <line x1="10" y1="14" x2="21" y2="3" />
                          </svg>
                        </button>
                      ))}
                    </div>
                  </>
                ) : (
                  <p className="text-xs text-text-secondary mb-3">
                    文件已归档至素材库，未生成 Wiki 页面。
                  </p>
                )}

                <div className="flex items-center gap-2">
                  {wikiPages.length > 0 && (
                    <button
                      onClick={() => navigate({ to: '/wiki' })}
                      className="btn btn-primary text-xs px-3 py-1.5"
                    >
                      查看全部页面
                    </button>
                  )}
                  <button
                    onClick={() => navigate({ to: '/raw' })}
                    className="btn btn-secondary text-xs px-3 py-1.5"
                  >
                    去素材库
                  </button>
                </div>
              </div>
            )}

            {/* ── Failure Diagnosis Card ── */}
            {isFailed && (
              <div className="mt-5 p-4 rounded-xl bg-accent-danger/5 border border-accent-danger/15 animate-fade-up">
                <div className="flex items-center gap-2 mb-3">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5 text-accent-danger">
                    <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" />
                  </svg>
                  <span className="text-sm font-semibold text-text-primary">编译失败</span>
                </div>

                {/* Failed step */}
                {state?.failed_step && (
                  <div className="mb-2">
                    <span className="text-xs text-text-muted">失败环节：</span>
                    <span className="text-xs font-medium text-accent-danger">
                      {STEP_LABEL_MAP[state.failed_step] || state.failed_step}
                    </span>
                  </div>
                )}

                {/* Error message */}
                <div className="text-xs text-accent-danger leading-relaxed mb-3">
                  {state?.error || state?.message || '未知错误'}
                </div>

                {/* Log area */}
                <button
                  onClick={() => setLogExpanded((v) => !v)}
                  className="flex items-center gap-1 text-xs text-text-muted hover:text-text-secondary transition mb-2"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={cn('w-3.5 h-3.5 transition-transform', logExpanded && 'rotate-90')}>
                    <polyline points="9 18 15 12 9 6" />
                  </svg>
                  查看日志
                </button>

                {logExpanded && (
                  <div className="mb-3">
                    <div className="relative">
                      <pre className="text-[11px] font-mono text-text-tertiary bg-bg-void rounded-lg p-3 max-h-40 overflow-auto border border-border-subtle whitespace-pre-wrap break-all">
                        {state
                          ? `[${state.updated_at}] status=${state.status}\nstep=${state.step}/${state.total_steps}\nmessage=${state.message}\nerror=${state.error || 'N/A'}\nfailed_step=${state.failed_step || 'N/A'}`
                          : '无日志'}
                      </pre>
                      <button
                        onClick={handleCopyLog}
                        className="absolute top-2 right-2 p-1 rounded bg-bg-elevated/80 hover:bg-bg-elevated text-text-muted hover:text-text-secondary transition"
                        title="复制日志"
                      >
                        {copied ? (
                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5 text-accent-living">
                            <polyline points="20 6 9 17 4 12" />
                          </svg>
                        ) : (
                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5">
                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                          </svg>
                        )}
                      </button>
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => window.location.reload()}
                    className="btn btn-primary text-xs px-3 py-1.5"
                  >
                    刷新重试
                  </button>
                  <button
                    onClick={() => navigate({ to: '/raw' })}
                    className="btn btn-secondary text-xs px-3 py-1.5"
                  >
                    去素材库
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  )
}
