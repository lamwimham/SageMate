import { create } from 'zustand'

export interface Project {
  id: string
  name: string
  createdAt: string
}

interface ProjectState {
  projects: Project[]
  activeProjectId: string
  setActiveProject: (id: string) => void
  addProject: (name: string) => void
  removeProject: (id: string) => void
}

const DEFAULT_PROJECT: Project = {
  id: 'default',
  name: 'Default',
  createdAt: new Date().toISOString(),
}

function loadProjects(): Project[] {
  try {
    const raw = localStorage.getItem('sagemate:projects')
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed) && parsed.length > 0) return parsed
    }
  } catch { /* ignore */ }
  return [DEFAULT_PROJECT]
}

function loadActiveProjectId(): string {
  return localStorage.getItem('sagemate:activeProject') || 'default'
}

function persist(projects: Project[], activeId: string) {
  localStorage.setItem('sagemate:projects', JSON.stringify(projects))
  localStorage.setItem('sagemate:activeProject', activeId)
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  projects: loadProjects(),
  activeProjectId: loadActiveProjectId(),

  setActiveProject: (id: string) => {
    const { projects } = get()
    if (!projects.find((p) => p.id === id)) return
    persist(projects, id)
    set({ activeProjectId: id })
  },

  addProject: (name: string) => {
    const project: Project = {
      id: `proj_${Date.now().toString(36)}`,
      name,
      createdAt: new Date().toISOString(),
    }
    set((s) => {
      const projects = [...s.projects, project]
      persist(projects, project.id)
      return { projects, activeProjectId: project.id }
    })
  },

  removeProject: (id: string) => {
    if (id === 'default') return
    set((s) => {
      const projects = s.projects.filter((p) => p.id !== id)
      const newActive = s.activeProjectId === id ? 'default' : s.activeProjectId
      persist(projects, newActive)
      return { projects, activeProjectId: newActive }
    })
  },
}))
