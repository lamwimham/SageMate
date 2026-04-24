import { create } from 'zustand'

type IngestMethod = 'file' | 'url'

interface IngestStep {
  key: string
  label: string
  desc: string
}

export interface IngestProgressState {
  status: 'idle' | 'connecting' | 'processing' | 'completed' | 'failed'
  steps: IngestStep[]
  pct: number
  error?: string
  taskId?: string
}

interface IngestState {
  method: IngestMethod
  setMethod: (m: IngestMethod) => void

  // Progress state (populated by useIngestProgress hook in the view)
  progress: IngestProgressState
  setProgress: (p: Partial<IngestProgressState>) => void
  resetProgress: () => void
}

export const useIngestStore = create<IngestState>((set) => ({
  method: 'file',
  setMethod: (m) => set({ method: m }),

  progress: {
    status: 'idle',
    steps: [],
    pct: 0,
  },
  setProgress: (p) => set((s) => ({ progress: { ...s.progress, ...p } })),
  resetProgress: () =>
    set({
      progress: { status: 'idle', steps: [], pct: 0 },
    }),
}))
