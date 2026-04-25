import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { wikiRepo } from '@/api/repositories'
import type { WikiPageCreate, WikiPageUpdate } from '@/types'

/**
 * Query 缓存策略 — 分层治理
 *
 * L1 (热缓存): 页面内容 — gcTime=0，标签关闭即清除，不常驻内存
 * L2 (温缓存): 页面列表 — staleTime=5min，全局共享，适度复用
 * L3 (冷缓存): 索引数据 — staleTime=∞，极少变化，长期保留
 */

const CACHE_STRATEGIES = {
  /** 页面内容：标签级，关闭即释放 */
  pageContent: { gcTime: 0, staleTime: 30_000 },
  /** 页面列表：应用级，5分钟新鲜期 */
  pageList: { gcTime: 10 * 60 * 1000, staleTime: 5 * 60 * 1000 },
  /** 搜索结果：会话级，用完即弃 */
  search: { gcTime: 60_000, staleTime: 30_000 },
}

/** 清除指定页面的缓存（标签关闭时调用） */
export function invalidatePageCache(qc: ReturnType<typeof useQueryClient>, slug: string) {
  qc.removeQueries({ queryKey: ['page', slug], exact: true })
}

export function usePages(category?: string) {
  return useQuery({
    queryKey: ['pages', category],
    queryFn: () => wikiRepo.listPages(category),
    ...CACHE_STRATEGIES.pageList,
  })
}

export function usePage(slug: string) {
  return useQuery({
    queryKey: ['page', slug],
    queryFn: () => wikiRepo.getPage(slug),
    ...CACHE_STRATEGIES.pageContent,
    enabled: !!slug,
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
    ...CACHE_STRATEGIES.search,
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
