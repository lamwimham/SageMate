import { create } from 'zustand'

export interface CompileTask {
  task_id: string
  source_slug: string
  source_title: string
  status: string
  step: number
  total_steps: number
  message: string
  wiki_pages: { slug: string; title: string }[]
  error: string | null
  failed_step: string | null
  created_at: string
  updated_at: string
}

interface CompileTaskState {
  tasks: CompileTask[]
  isLoading: boolean
  error: string | null

  setTasks: (tasks: CompileTask[]) => void
  updateTask: (task: Partial<CompileTask> & { task_id: string }) => void
  setLoading: (v: boolean) => void
  setError: (e: string | null) => void
  removeTask: (task_id: string) => void
}

export const useCompileTaskStore = create<CompileTaskState>((set) => ({
  tasks: [],
  isLoading: false,
  error: null,

  setTasks: (tasks) => set({ tasks }),

  updateTask: (partial) =>
    set((s) => ({
      tasks: s.tasks.map((t) =>
        t.task_id === partial.task_id ? { ...t, ...partial } : t
      ),
    })),

  setLoading: (v) => set({ isLoading: v }),
  setError: (e) => set({ error: e }),

  removeTask: (task_id) =>
    set((s) => ({
      tasks: s.tasks.filter((t) => t.task_id !== task_id),
    })),
}))
