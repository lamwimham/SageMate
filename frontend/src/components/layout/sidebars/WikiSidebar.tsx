import { useState } from 'react'
import { usePages, useDeletePage } from '@/hooks/useWiki'
import { useStats } from '@/hooks/useSystem'
import { useWikiTabsStore } from '@/stores/wikiTabs'
import { Badge } from '@/components/ui/Badge'
import { SkeletonCard } from '@/components/ui/Skeleton'
import { cn } from '@/lib/utils'

function StatBadge({
  label,
  value,
  icon,
  color,
}: {
  label: string
  value: string | number
  icon: string
  color: string
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <div className="flex items-center gap-2">
        <div className={cn('w-7 h-7 rounded-lg flex items-center justify-center text-sm', color)}>
          {icon}
        </div>
        <span className="text-xs text-text-muted">{label}</span>
      </div>
      <span className={cn('text-sm font-bold font-mono', color.replace('/8 border-', ' '))}>
        {value}
      </span>
    </div>
  )
}

function OverviewStats() {
  const { data: stats } = useStats()
  const { data: recentPages } = usePages()
  const displayPages = recentPages?.slice(0, 5) ?? []

  return (
    <>
      {!stats ? (
        <div className="space-y-2">
          {[1, 2, 3, 4].map((i) => (
            <SkeletonCard key={i} className="h-[34px]" />
          ))}
        </div>
      ) : (
        <>
          <StatBadge
            label="Wiki 页面"
            value={stats.wiki_pages ?? 0}
            icon="📚"
            color="text-accent-neural bg-accent-neural/8 border-accent-neural/12"
          />
          <StatBadge
            label="已归档来源"
            value={stats.sources ?? 0}
            icon="📥"
            color="text-accent-living bg-accent-living/8 border-accent-living/12"
          />
          <StatBadge
            label="知识库健康"
            value="良好"
            icon="✅"
            color="text-accent-living bg-accent-living/8 border-accent-living/12"
          />
          <StatBadge
            label="今日活动"
            value={0}
            icon="⚡"
            color="text-accent-growth bg-accent-growth/8 border-accent-growth/12"
          />
        </>
      )}

      {displayPages.length > 0 && (
        <>
          <div className="px-3 py-1.5 border-t border-border-subtle mt-2">
            <span className="text-[12px] font-semibold uppercase tracking-wider text-text-muted">最近更新</span>
          </div>
          <div className="px-2 py-1 space-y-0.5">
            {displayPages.map((page) => (
              <div
                key={page.slug}
                className="block px-3 py-1.5 rounded-lg text-xs truncate"
                title={page.title}
              >
                <div className="truncate font-medium text-text-primary text-[12px]">{page.title}</div>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <Badge variant={page.category as never} className="text-[12px] py-0 px-0.5">
                    {page.category}
                  </Badge>
                  <span className="text-[12px] text-text-muted">
                    {new Date(page.updated_at).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </>
  )
}

export function WikiOverview() {
  return <OverviewStats />
}

export function WikiSidebar() {
  const { data: pages } = usePages()
  const deleteMutation = useDeletePage()
  const { openPage, openNote, closeTab, tabs } = useWikiTabsStore()
  const allPages = pages ?? []
  const [q, setQ] = useState('')
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)

  const filtered = q.trim()
    ? allPages.filter((p) =>
        p.title.toLowerCase().includes(q.toLowerCase()) ||
        (p.summary || '').toLowerCase().includes(q.toLowerCase())
      )
    : allPages

  const handlePageClick = (slug: string, title: string) => {
    openPage(slug, title)
  }

  const handleDelete = async (slug: string) => {
    await deleteMutation.mutateAsync(slug)
    // Close tab if open
    const hasTab = tabs.some((t) => t.key === slug)
    if (hasTab) {
      closeTab(slug)
    }
    setConfirmDelete(null)
  }

  return (
    <>
      {/* Search */}
      <div className="px-3 py-2.5 border-b border-border-subtle">
        <input
          type="text"
          placeholder="搜索页面..."
          className="input text-xs py-1.5"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>

      {/* New Note Button */}
      <button
        onClick={() => openNote()}
        className="mx-3 my-2 px-3 py-2 rounded-lg text-xs font-medium text-accent-neural border border-dashed border-accent-neural/30 hover:bg-accent-neural/10 hover:border-accent-neural/50 transition cursor-pointer w-[calc(100%-24px)] text-left flex items-center gap-1.5"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5">
          <line x1="12" y1="5" x2="12" y2="19" />
          <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
        新建笔记
      </button>

      {/* Page List */}
      <div className="flex-1 overflow-y-auto px-2 py-1.5 space-y-0.5">
        {filtered.length > 0 ? (
          filtered.map((page) => (
            <div
              key={page.slug}
              className="group flex items-center gap-1 px-2 py-2 rounded-lg transition-all duration-150 hover:bg-bg-hover"
            >
              <button
                onClick={() => handlePageClick(page.slug, page.title)}
                className="flex-1 text-left min-w-0 cursor-pointer"
                title={page.title}
              >
                <div className="truncate font-medium text-xs text-text-primary">{page.title}</div>
                <div className="flex items-center gap-1.5 mt-1">
                  <Badge variant={page.category as never} className="text-[10px] py-0.5 px-1.5 rounded-md">
                    {page.category}
                  </Badge>
                  <span className="text-[10px] text-text-muted">
                    {new Date(page.updated_at).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })}
                  </span>
                </div>
              </button>

              {/* Delete button - visible on hover */}
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  setConfirmDelete(page.slug)
                }}
                className="opacity-0 group-hover:opacity-100 p-1 rounded-md text-text-muted hover:text-accent-danger hover:bg-accent-danger/10 transition-all duration-150 cursor-pointer shrink-0"
                title="删除页面"
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5">
                  <path d="M3 6h18" />
                  <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
                  <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
                </svg>
              </button>
            </div>
          ))
        ) : (
          <div className="px-3 py-6 text-xs text-text-muted text-center">
            {q ? '未找到匹配的页面' : '暂无页面'}
          </div>
        )}
      </div>

      {/* Delete confirmation modal */}
      {confirmDelete && (
        <div className="modal-backdrop" onClick={() => setConfirmDelete(null)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <p className="modal-text">
              确定删除页面 "<span className="modal-highlight">{allPages.find((p) => p.slug === confirmDelete)?.title}</span>" 吗？此操作不可恢复。
            </p>
            <div className="modal-actions">
              <button className="modal-btn modal-btn--cancel" onClick={() => setConfirmDelete(null)}>取消</button>
              <button
                className="modal-btn modal-btn--danger"
                onClick={() => handleDelete(confirmDelete)}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? '删除中...' : '删除'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
