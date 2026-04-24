import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { settingsRepo, projectsRepo } from '@/api/repositories'
import type { SettingsUpdate } from '@/types'

export function useSettings() {
  return useQuery({
    queryKey: ['settings'],
    queryFn: () => settingsRepo.get(),
  })
}

export function useUpdateSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (patch: SettingsUpdate) => settingsRepo.update(patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['settings'] }),
  })
}

export function useResetSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => settingsRepo.reset(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['settings'] }),
  })
}

export function useWeChatAccount() {
  return useQuery({
    queryKey: ['wechat-account'],
    queryFn: () => settingsRepo.wechatAccount(),
  })
}

export function useWeChatQR() {
  return useMutation({
    mutationFn: () => settingsRepo.wechatQR(),
  })
}

export function useWeChatPoll() {
  return useMutation({
    mutationFn: () => settingsRepo.wechatPoll(),
  })
}

export function useWeChatLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => settingsRepo.wechatLogout(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['wechat-account'] }),
  })
}

// ── Project Hooks ──────────────────────────────────────────────

export function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: () => projectsRepo.list(),
  })
}

export function useActiveProject() {
  return useQuery({
    queryKey: ['projects', 'active'],
    queryFn: () => projectsRepo.getActive(),
  })
}

export function useCreateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { root_path: string; name?: string }) => projectsRepo.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      qc.invalidateQueries({ queryKey: ['projects', 'active'] })
    },
  })
}

export function useActivateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => projectsRepo.activate(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      qc.invalidateQueries({ queryKey: ['projects', 'active'] })
    },
  })
}

export function useDeleteProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => projectsRepo.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      qc.invalidateQueries({ queryKey: ['projects', 'active'] })
    },
  })
}

export function useScanProject() {
  return useMutation({
    mutationFn: (id: string) => projectsRepo.scan(id),
  })
}

export function useSchema() {
  return useQuery({
    queryKey: ['schema'],
    queryFn: () => settingsRepo.getSchema(),
  })
}
