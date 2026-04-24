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
    onSuccess: () => qc.invalidateQueries({ queryKey: ['lint'] }),
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
  })
}

export function useLogs() {
  return useQuery({
    queryKey: ['logs'],
    queryFn: () => systemRepo.logs(),
  })
}
