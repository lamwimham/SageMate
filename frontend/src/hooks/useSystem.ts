import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { systemRepo } from '@/api/repositories'

export function useStats() {
  return useQuery({
    queryKey: ['stats'],
    queryFn: () => systemRepo.stats(),
  })
}

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => systemRepo.health(),
  })
}

export function useLint(autoFix = false) {
  return useQuery({
    queryKey: ['lint', autoFix],
    queryFn: () => systemRepo.lint(autoFix),
    enabled: false,
  })
}

export function useRunLint() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => systemRepo.lint(false),
    onSuccess: (data) => {
      // Directly cache the result — avoids duplicate refetch
      qc.setQueryData(['lint', false], data)
      qc.setQueryData(['lint', true], data)
      // Invalidate logs since lint writes to log
      qc.invalidateQueries({ queryKey: ['logs'] })
    },
  })
}

export function useCost() {
  return useQuery({
    queryKey: ['cost'],
    queryFn: () => systemRepo.cost(),
  })
}

export function useCron() {
  return useQuery({
    queryKey: ['cron'],
    queryFn: () => systemRepo.cron(),
    refetchInterval: 10000, // Poll every 10s
    staleTime: 0, // Always refetch on mount
  })
}

export function useCronToggle() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ task, enabled }: { task: string; enabled: boolean }) =>
      systemRepo.cronToggle(task, enabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cron'] }),
  })
}

export function useCronRunNow() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (task: string) => systemRepo.cronRunNow(task),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cron'] }),
  })
}

export function useLogs() {
  return useQuery({
    queryKey: ['logs'],
    queryFn: () => systemRepo.logs(),
  })
}
