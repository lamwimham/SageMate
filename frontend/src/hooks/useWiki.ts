import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { wikiRepo } from '@/api/repositories'
import type { WikiPageCreate, WikiPageUpdate } from '@/types'

export function usePages(category?: string) {
  return useQuery({
    queryKey: ['pages', category],
    queryFn: () => wikiRepo.listPages(category),
  })
}

export function usePage(slug: string) {
  return useQuery({
    queryKey: ['page', slug],
    queryFn: () => wikiRepo.getPage(slug),
  })
}

export function useUpdatePage() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ slug, update }: { slug: string; update: WikiPageUpdate }) =>
      wikiRepo.updatePage(slug, update),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['page', vars.slug] })
      qc.invalidateQueries({ queryKey: ['pages'] })
    },
  })
}

export function useSavePageContent() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ slug, content }: { slug: string; content: string }) =>
      wikiRepo.savePageContent(slug, content),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['page', vars.slug] })
      qc.invalidateQueries({ queryKey: ['pages'] })
    },
  })
}

export function useDeletePage() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (slug: string) => wikiRepo.deletePage(slug),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['pages'] })
    },
  })
}

export function useSearch(q: string) {
  return useQuery({
    queryKey: ['search', q],
    queryFn: () => wikiRepo.search(q),
    enabled: q.length > 0,
  })
}

export function useWikiQuery() {
  return useMutation({
    mutationFn: ({ question, save_analysis }: { question: string; save_analysis?: boolean }) =>
      wikiRepo.query(question, save_analysis),
  })
}

export function useCreatePage() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: WikiPageCreate) => wikiRepo.createPage(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['pages'] })
    },
  })
}
