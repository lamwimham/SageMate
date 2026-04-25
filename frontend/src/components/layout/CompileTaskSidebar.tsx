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
            // Keep in list for a moment so user sees final state, then remove
            setTimeout(() => removeTask(task.task_id), 3000)
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

    // Close SSE for tasks no longer in active list
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
    <div className="border-t border-border-subtle bg-bg-surface">
      <div className="px-3 py-2 border-b border-border-subtle">
        <h4 className="text-[12px] font-semibold uppercase tracking-wider text-text-muted">
          编译任务 ({tasks.length})
        </h4>
      </div>
      <div className="max-h-48 overflow-y-auto py-1">
        {tasks.map((task) => {
          const pct = Math.min(100, Math.round((task.step / task.total_steps) * 100))
          return (
            <div key={task.task_id} className="px-3 py-1.5 hover:bg-bg-hover transition">
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
            </div>
          )
        })}
      </div>
    </div>
  )
}
