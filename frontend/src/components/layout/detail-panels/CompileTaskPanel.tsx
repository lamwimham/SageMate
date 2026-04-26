import { useState, useEffect, useRef } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { useCompileTaskStore } from '@/stores/compileTasks'
import { useWikiTabsStore } from '@/stores/wikiTabs'
import { cn } from '@/lib/utils'

const STATUS_LABEL: Record<string, string> = {
  queued: '排队中',
  parsing: '解析中',
  reading_context: '读上下文',
  calling_llm: 'LLM分析',
  writing_pages: '写Wiki',
  updating_index: '更新索引',
  completed: '完成',
  failed: '失败',
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'queued':
      return <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>
    case 'parsing':
      return <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" /></svg>
    case 'reading_context':
      return <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" /><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" /></svg>
    case 'calling_llm':
      return <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><rect x="2" y="2" width="20" height="8" rx="2" ry="2" /><rect x="2" y="14" width="20" height="8" rx="2" ry="2" /><line x1="6" y1="6" x2="6.01" y2="6" /><line x1="6" y1="18" x2="6.01" y2="18" /></svg>
    case 'writing_pages':
      return <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" /><path d="m15 5 4 4" /></svg>
    case 'updating_index':
      return <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" /></svg>
    case 'completed':
      return <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg>
    case 'failed':
      return <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" /></svg>
    default:
      return <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>
  }
}

const STEP_LABEL_MAP: Record<string, string> = {
  queued: '提交任务',
  parsing: '解析内容',
  reading_context: '读取上下文',
  calling_llm: 'LLM 分析中',
  writing_pages: '生成 Wiki',
  updating_index: '更新索引',
}

export function CompileTaskPanel() {
  const navigate = useNavigate()
  const openPage = useWikiTabsStore((s) => s.openPage)
  const { tasks } = useCompileTaskStore()
  const [expandedTaskId, setExpandedTaskId] = useState<string | null>(null)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Pure render-only component — polling + SSE live in CompileTaskSidebar
  // to avoid duplicate connections and memory churn.

  const handleCopyError = (taskId: string, error: string | null) => {
    if (!error) return
    navigator.clipboard.writeText(error).then(() => {
      setCopiedId(taskId)
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current)
      copyTimerRef.current = setTimeout(() => setCopiedId(null), 2000)
    })
  }

  useEffect(() => {
    return () => {
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current)
    }
  }, [])

  return (
    <aside className="bg-bg-surface border-l border-border-subtle overflow-hidden flex flex-col" aria-label="编译任务">
      <div className="px-4 py-3 border-b border-border-subtle flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted">编译任务</h3>
        {tasks.length > 0 && (
          <span className="badge text-[12px] bg-bg-elevated text-text-muted border border-border-subtle">
            {tasks.length}
          </span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-3">
        {tasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-8 h-8 mb-2 opacity-40 text-text-muted">
              <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            <p className="text-xs text-text-muted">暂无正在编译的任务</p>
            <p className="text-[12px] text-text-tertiary mt-1">上传文件或提交 URL 后将显示在这里</p>
          </div>
        ) : (
          <div className="space-y-3">
            {tasks.map((task) => {
              const pct = Math.min(100, Math.round((task.step / task.total_steps) * 100))
              const isDone = task.status === 'completed' || task.status === 'failed'
              const isExpanded = expandedTaskId === task.task_id
              const wikiPages = task.wiki_pages || []

              return (
                <div
                  key={task.task_id}
                  className={cn(
                    'rounded-xl border transition',
                    isDone
                      ? task.status === 'completed'
                        ? 'bg-accent-living/5 border-accent-living/15'
                        : 'bg-accent-danger/5 border-accent-danger/15'
                      : 'bg-bg-elevated border-border-subtle'
                  )}
                >
                  {/* Header — always visible */}
                  <button
                    onClick={() => setExpandedTaskId(isExpanded ? null : task.task_id)}
                    className="w-full p-3 text-left"
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <StatusIcon status={task.status} />
                      <span className="text-[13px] font-medium text-text-primary truncate flex-1">
                        {task.source_title || task.source_slug || '未命名任务'}
                      </span>
                      <span
                        className={cn(
                          'text-[12px] font-medium px-1.5 py-0.5 rounded-full shrink-0',
                          task.status === 'completed'
                            ? 'bg-accent-living/10 text-accent-living'
                            : task.status === 'failed'
                              ? 'bg-accent-danger/10 text-accent-danger'
                              : 'bg-accent-neural/10 text-accent-neural'
                        )}
                      >
                        {STATUS_LABEL[task.status] || task.status}
                      </span>
                    </div>

                    <div className="w-full h-1.5 rounded-full bg-bg-surface overflow-hidden mb-1.5">
                      <div
                        className={cn(
                          'h-full rounded-full transition-all duration-500',
                          task.status === 'completed'
                            ? 'bg-accent-living'
                            : task.status === 'failed'
                              ? 'bg-accent-danger'
                              : 'bg-accent-neural'
                        )}
                        style={{ width: `${pct}%` }}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <p className="text-[12px] text-text-tertiary truncate flex-1 mr-2">{task.message}</p>
                      <span className="text-[12px] text-text-muted font-mono shrink-0">{pct}%</span>
                    </div>
                  </button>

                  {/* Expanded content — result / diagnosis cards */}
                  {isExpanded && (
                    <div className="px-3 pb-3 animate-fade-up">
                      {/* Success result card */}
                      {task.status === 'completed' && wikiPages.length > 0 && (
                        <div className="mt-1 space-y-1.5">
                          <p className="text-xs text-text-secondary mb-1.5">生成的 Wiki 页面：</p>
                          {wikiPages.map((page) => (
                            <button
                              key={page.slug}
                              onClick={() => {
                                openPage(page.slug, page.title || page.slug)
                                navigate({ to: '/wiki' })
                              }}
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
                          <button
                            onClick={() => {
                              openPage('index', 'Wiki 首页')
                              navigate({ to: '/wiki' })
                            }}
                            className="w-full text-center text-xs text-accent-neural hover:text-accent-neural-dim transition py-1.5"
                          >
                            查看全部页面 →
                          </button>
                        </div>
                      )}

                      {task.status === 'completed' && wikiPages.length === 0 && (
                        <p className="text-xs text-text-secondary mt-1">文件已归档，未生成 Wiki 页面。</p>
                      )}

                      {/* Failure diagnosis card */}
                      {task.status === 'failed' && (
                        <div className="mt-1 space-y-2">
                          {task.failed_step && (
                            <div className="text-xs">
                              <span className="text-text-muted">失败环节：</span>
                              <span className="font-medium text-accent-danger">
                                {STEP_LABEL_MAP[task.failed_step] || task.failed_step}
                              </span>
                            </div>
                          )}
                          {task.error && (
                            <div className="relative">
                              <div className="text-xs text-accent-danger leading-relaxed bg-bg-void rounded-lg p-2.5 border border-border-subtle">
                                {task.error}
                              </div>
                              <button
                                onClick={() => handleCopyError(task.task_id, task.error)}
                                className="absolute top-1.5 right-1.5 p-1 rounded bg-bg-elevated/80 hover:bg-bg-elevated text-text-muted hover:text-text-secondary transition"
                                title="复制错误信息"
                              >
                                {copiedId === task.task_id ? (
                                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-3 h-3 text-accent-living">
                                    <polyline points="20 6 9 17 4 12" />
                                  </svg>
                                ) : (
                                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-3 h-3">
                                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                                  </svg>
                                )}
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </aside>
  )
}
