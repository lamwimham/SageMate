import { useQuery } from '@tanstack/react-query'
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
