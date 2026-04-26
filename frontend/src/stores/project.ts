import { create } from 'zustand'
import { projectsRepo } from '../api/repositories/settings'

export interface Project {
  id: string
  name: string
  createdAt: string
  rootPath?: string
}

interface ProjectState {
  projects: Project[]
  activeProjectId: string | null
  isLoading: boolean
  error: string | null
  // Actions
  loadProjects: () => Promise<void>
  setActiveProject: (id: string) => Promise<void>
  addProject: (name: string, rootPath?: string) => Promise<void>
  removeProject: (id: string) => Promise<void>
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  projects: [],
  activeProjectId: null,
  isLoading: false,
  error: null,

  loadProjects: async () => {
    set({ isLoading: true, error: null })
    try {
      const data = await projectsRepo.list()
      const projects = data.projects.map((p: any) => ({
        id: p.id,
        name: p.name,
        createdAt: p.created_at || p.createdAt,
        rootPath: p.root_path,
      }))
      const active = data.projects.find((p: any) => p.status === 'active')
      set({
        projects,
        activeProjectId: active?.id || (projects[0]?.id ?? null),
        isLoading: false,
      })
    } catch (err: any) {
      set({ error: err.message || '加载项目失败', isLoading: false })
    }
  },

  setActiveProject: async (id: string) => {
    const { projects } = get()
    if (!projects.find((p) => p.id === id)) return
    try {
      await projectsRepo.activate(id)
      set({ activeProjectId: id })
      // Refresh page to reload project-specific data
      window.location.reload()
    } catch (err: any) {
      set({ error: err.message || '切换项目失败' })
    }
  },

  addProject: async (name: string, rootPath?: string) => {
    try {
      const result = await projectsRepo.create({
        name,
        ...(rootPath?.trim() ? { root_path: rootPath.trim() } : {}),
      })
      const activated = await projectsRepo.activate(result.project.id)
      const project = activated.project
      set((s) => ({
        projects: [
          ...s.projects,
          {
            id: project.id,
            name: project.name,
            createdAt: project.created_at || project.createdAt,
            rootPath: project.root_path,
          },
        ],
        activeProjectId: project.id,
      }))
      // Refresh to load new project data
      window.location.reload()
    } catch (err: any) {
      set({ error: err.message || '创建项目失败' })
      throw err
    }
  },

  removeProject: async (id: string) => {
    if (id === 'default') return
    try {
      await projectsRepo.delete(id)
      set((s) => {
        const projects = s.projects.filter((p) => p.id !== id)
        const newActive = s.activeProjectId === id ? projects[0]?.id ?? null : s.activeProjectId
        return { projects, activeProjectId: newActive }
      })
    } catch (err: any) {
      set({ error: err.message || '删除项目失败' })
    }
  },
}))
