import { useState, useEffect, useRef } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { useCompileTaskStore } from '@/stores/compileTasks'
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

const STATUS_ICON: Record<string, string> = {
  queued: '⏳',
  parsing: '🔍',
  reading_context: '📖',
  calling_llm: '🧠',
  writing_pages: '✍️',
  updating_index: '🔄',
  completed: '✅',
  failed: '❌',
}


const STEP_LABEL_MAP: Record<string, string> = {
  queued: '提交任务',
  parsing: '解析内容',
  reading_context: '读取上下文',
  calling_llm: 'LLM 分析中',
  writing_pages: '生成 Wiki',
  updating_index: '更新索引',
}

export function CompileTaskSidebar() {
  const navigate = useNavigate()
  const { tasks, setTasks, updateTask, removeTask } = useCompileTaskStore()
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const esMapRef = useRef<Map<string, EventSource>>(new Map())

  // 1. Poll task list every 3s
  useEffect(() => {
    const fetchTasks = async () => {
      try {
        const res = await fetch('/api/v1/ingest/tasks')
        if (!res.ok) return
        const data = await res.json()
        setTasks(data.tasks || [])
      } catch {
        // silent fail
      }
    }
    fetchTasks()
    const id = setInterval(fetchTasks, 3000)
    return () => clearInterval(id)
  }, [setTasks])

  // 2. Maintain SSE connections for unfinished tasks
  useEffect(() => {
    const esMap = esMapRef.current
    const activeIds = new Set<string>()

    tasks.forEach((task) => {
      if (task.status === 'completed' || task.status === 'failed') return
      activeIds.add(task.task_id)

      if (esMap.has(task.task_id)) return

      const es = new EventSource(`/api/v1/ingest/progress/${task.task_id}`)
      esMap.set(task.task_id, es)

      es.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data)
          if (data.type === 'heartbeat') return
          updateTask({
            task_id: task.task_id,
            status: data.status,
            step: data.step,
            total_steps: data.total_steps,
            message: data.message,
          })
          if (data.status === 'completed' || data.status === 'failed') {
            setTimeout(() => removeTask(task.task_id), 8000)
          }
        } catch {
          // ignore
        }
      }

      es.onerror = () => {
        es.close()
        esMap.delete(task.task_id)
      }
    })

    esMap.forEach((es, id) => {
      if (!activeIds.has(id)) {
        es.close()
        esMap.delete(id)
      }
    })

    return () => {
      esMap.forEach((es) => es.close())
      esMap.clear()
    }
  }, [tasks, updateTask, removeTask])

  const handleCopyError = (taskId: string, error: string | null) => {
    if (!error) return
    navigator.clipboard.writeText(error).then(() => {
      setCopiedId(taskId)
      setTimeout(() => setCopiedId(null), 2000)
    })
  }

  if (tasks.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-text-muted text-sm">
        <span className="opacity-40 mr-2">📋</span>
        暂无后台编译任务
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-2 border-b border-border-subtle flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">编译任务</span>
          <span className="text-[11px] text-text-muted bg-bg-elevated px-1.5 py-0.5 rounded-full border border-border-subtle">
            {tasks.length}
          </span>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-text-muted">
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-neural" />
            {tasks.filter((t) => t.status !== 'completed' && t.status !== 'failed').length} 进行中
          </span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-living" />
            {tasks.filter((t) => t.status === 'completed').length} 完成
          </span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-danger" />
            {tasks.filter((t) => t.status === 'failed').length} 失败
          </span>
        </div>
      </div>

      {/* Task grid */}
      <div className="flex-1 overflow-x-auto overflow-y-hidden p-3">
        <div className="flex gap-3 h-full">
          {tasks.map((task) => {
            const pct = Math.min(100, Math.round((task.step / task.total_steps) * 100))
            const isExpanded = expandedId === task.task_id
            const isDone = task.status === 'completed' || task.status === 'failed'
            const wikiPages = task.wiki_pages || []

            return (
              <div
                key={task.task_id}
                className={cn(
                  'w-72 shrink-0 rounded-xl border transition flex flex-col',
                  isDone
                    ? task.status === 'completed'
                      ? 'bg-accent-living/5 border-accent-living/15'
                      : 'bg-accent-danger/5 border-accent-danger/15'
                    : 'bg-bg-elevated border-border-subtle'
                )}
              >
                {/* Card header */}
                <button
                  onClick={() => setExpandedId(isExpanded ? null : task.task_id)}
                  className="p-3 text-left shrink-0"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm">{STATUS_ICON[task.status] || '⏳'}</span>
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

                  <div className="w-full h-1.5 rounded-full bg-bg-surface overflow-hidden mb-1">
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

                {/* Expanded content */}
                {isExpanded && (
                  <div className="px-3 pb-3 flex-1 overflow-y-auto animate-fade-up min-h-0">
                    {task.status === 'completed' && wikiPages.length > 0 && (
                      <>
                        <p className="text-xs text-text-secondary mb-2">生成的 Wiki 页面：</p>
                        <div className="space-y-1.5">
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
                    )}

                    {task.status === 'completed' && wikiPages.length === 0 && (
                      <p className="text-xs text-text-secondary">文件已归档，未生成 Wiki 页面。</p>
                    )}

                    {task.status === 'failed' && (
                      <div className="space-y-2">
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

                    {isDone && (
                      <button
                        onClick={() => navigate({ to: '/ingest' })}
                        className="w-full text-center text-xs text-accent-neural hover:text-accent-neural-dim transition py-2"
                      >
                        去摄入页面查看详情 →
                      </button>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
