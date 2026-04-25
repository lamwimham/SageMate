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

const STATUS_COLOR: Record<string, string> = {
  queued: 'text-text-muted',
  parsing: 'text-accent-neural',
  reading_context: 'text-accent-neural',
  calling_llm: 'text-accent-neural',
  writing_pages: 'text-accent-neural',
  updating_index: 'text-accent-neural',
  completed: 'text-accent-living',
  failed: 'text-accent-danger',
}

export function CompileTaskSidebar() {
  const navigate = useNavigate()
  const { tasks, setTasks, updateTask, removeTask } = useCompileTaskStore()
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const esMapRef = useRef<Map<string, EventSource>>(new Map())

  // 1. Poll task list every 5s
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
    const id = setInterval(fetchTasks, 5000)
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

  if (tasks.length === 0) return null

  return (
    <div className="border-t border-border-subtle bg-bg-surface shrink-0">
      <div className="px-3 py-2 border-b border-border-subtle flex items-center justify-between">
        <h4 className="text-[12px] font-semibold uppercase tracking-wider text-text-muted">
          编译任务
        </h4>
        <span className="text-[11px] text-text-muted bg-bg-elevated px-1.5 py-0.5 rounded-full">
          {tasks.length}
        </span>
      </div>
      <div className="max-h-48 overflow-y-auto py-1">
        {tasks.map((task) => {
          const pct = Math.min(100, Math.round((task.step / task.total_steps) * 100))
          const isExpanded = expandedId === task.task_id
          const isDone = task.status === 'completed' || task.status === 'failed'
          const wikiPages = task.wiki_pages || []

          return (
            <div key={task.task_id} className="px-3 py-1.5">
              <button
                onClick={() => setExpandedId(isExpanded ? null : task.task_id)}
                className="w-full text-left"
              >
                <div className="flex items-center justify-between mb-0.5">
                  <span className="text-[12px] font-medium text-text-secondary truncate max-w-[140px]">
                    {task.source_title || task.source_slug}
                  </span>
                  <span className={cn('text-[12px]', STATUS_COLOR[task.status] || 'text-text-muted')}>
                    {STATUS_LABEL[task.status] || task.status}
                  </span>
                </div>
                <div className="w-full h-1 rounded-full bg-bg-elevated overflow-hidden">
                  <div
                    className={cn(
                      'h-full rounded-full transition-all duration-500',
                      task.status === 'failed' ? 'bg-accent-danger' : 'bg-accent-neural'
                    )}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <p className="text-[12px] text-text-tertiary mt-0.5 truncate">{task.message}</p>
              </button>

              {/* Expanded mini card */}
              {isExpanded && (
                <div className="mt-1.5 space-y-1 animate-fade-up">
                  {task.status === 'completed' && wikiPages.length > 0 && (
                    <>
                      {wikiPages.slice(0, 3).map((page) => (
                        <button
                          key={page.slug}
                          onClick={() => navigate({ to: '/wiki/$slug', params: { slug: page.slug } })}
                          className="w-full flex items-center gap-1.5 px-2 py-1 rounded-md bg-bg-elevated hover:bg-accent-neural/5 transition text-left"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="w-3 h-3 text-text-muted">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                            <polyline points="14 2 14 8 20 8" />
                          </svg>
                          <span className="text-[11px] text-text-secondary truncate flex-1">{page.title || page.slug}</span>
                        </button>
                      ))}
                      {wikiPages.length > 3 && (
                        <span className="text-[11px] text-text-muted px-2">还有 {wikiPages.length - 3} 个页面...</span>
                      )}
                    </>
                  )}

                  {task.status === 'completed' && wikiPages.length === 0 && (
                    <span className="text-[11px] text-text-muted px-2">已归档，未生成 Wiki 页面</span>
                  )}

                  {task.status === 'failed' && task.error && (
                    <div className="px-2 py-1 rounded-md bg-accent-danger/5 border border-accent-danger/10">
                      <p className="text-[11px] text-accent-danger truncate">{task.error}</p>
                    </div>
                  )}

                  {isDone && (
                    <button
                      onClick={() => navigate({ to: '/ingest' })}
                      className="w-full text-center text-[11px] text-accent-neural hover:text-accent-neural-dim transition py-1"
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
  )
}
