import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { sourcesRepo } from '@/api/repositories'

export function useSources(status?: string, sourceType?: string, q?: string) {
  return useQuery({
    queryKey: ['sources', status, sourceType, q],
    queryFn: () => sourcesRepo.list(status, sourceType, q),
  })
}

export function useRawFiles() {
  return useQuery({
    queryKey: ['raw-files'],
    queryFn: () => sourcesRepo.rawFiles(),
  })
}

export function useDeleteRawFile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (path: string) => sourcesRepo.deleteRawFile(path),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['raw-files'] })
      qc.invalidateQueries({ queryKey: ['sources'] })
    },
  })
}

export function useCompileRawFile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (path: string) => sourcesRepo.compileRawFile(path),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['raw-files'] })
      qc.invalidateQueries({ queryKey: ['sources'] })
    },
  })
}
