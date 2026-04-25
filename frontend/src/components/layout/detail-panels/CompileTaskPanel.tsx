import { useEffect, useRef } from 'react'
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

export function CompileTaskPanel() {
  const { tasks, setTasks, updateTask, removeTask } = useCompileTaskStore()
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

      if (esMap.has(task.task_id)) return // already connected

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
            setTimeout(() => removeTask(task.task_id), 5000)
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

    // Close SSE for tasks no longer in active list (incremental cleanup)
    esMap.forEach((es, id) => {
      if (!activeIds.has(id)) {
        es.close()
        esMap.delete(id)
      }
    })
  }, [tasks, updateTask, removeTask])

  // 3. Close all SSE connections on unmount only
  useEffect(() => {
    return () => {
      esMapRef.current.forEach((es) => es.close())
      esMapRef.current.clear()
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
            <div className="text-2xl mb-2 opacity-40">📋</div>
            <p className="text-xs text-text-muted">暂无正在编译的任务</p>
            <p className="text-[12px] text-text-tertiary mt-1">上传文件或提交 URL 后将显示在这里</p>
          </div>
        ) : (
          <div className="space-y-3">
            {tasks.map((task) => {
              const pct = Math.min(100, Math.round((task.step / task.total_steps) * 100))
              const isDone = task.status === 'completed' || task.status === 'failed'

              return (
                <div
                  key={task.task_id}
                  className={cn(
                    'p-3 rounded-xl border transition',
                    isDone
                      ? task.status === 'completed'
                        ? 'bg-accent-living/5 border-accent-living/15'
                        : 'bg-accent-danger/5 border-accent-danger/15'
                      : 'bg-bg-elevated border-border-subtle'
                  )}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm">{STATUS_ICON[task.status] || '⏳'}</span>
                    <span className="text-[13px] font-medium text-text-primary truncate flex-1">
                      {task.source_title || task.source_slug}
                    </span>
                    <span
                      className={cn(
                        'text-[12px] font-medium px-1.5 py-0.5 rounded-full',
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
                </div>
              )
            })}
          </div>
        )}
      </div>
    </aside>
  )
}
