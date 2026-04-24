import { useState } from 'react'
import { usePages } from '@/hooks/useWiki'
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
            <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">最近更新</span>
          </div>
          <div className="px-2 py-1 space-y-0.5">
            {displayPages.map((page) => (
              <div
                key={page.slug}
                className="block px-3 py-1.5 rounded-lg text-xs truncate"
                title={page.title}
              >
                <div className="truncate font-medium text-text-primary text-[11px]">{page.title}</div>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <Badge variant={page.category as never} className="text-[8px] py-0 px-0.5">
                    {page.category}
                  </Badge>
                  <span className="text-[9px] text-text-muted">
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
  const { openPage, openNote } = useWikiTabsStore()
  const allPages = pages ?? []
  const [q, setQ] = useState('')

  const filtered = q.trim()
    ? allPages.filter((p) =>
        p.title.toLowerCase().includes(q.toLowerCase()) ||
        (p.summary || '').toLowerCase().includes(q.toLowerCase())
      )
    : allPages

  const handlePageClick = (slug: string, title: string) => {
    openPage(slug, title)
  }

  return (
    <>
      {/* Search */}
      <div className="px-3 py-3 border-b border-border-subtle">
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
        className="mx-3 my-2 px-3 py-2 rounded-lg text-xs font-medium text-accent-neural border border-dashed border-accent-neural/30 hover:bg-accent-neural/8 hover:border-accent-neural/50 transition cursor-pointer w-[calc(100%-24px)] text-left"
      >
        ＋ 新建笔记
      </button>

      {/* Page List */}
      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
        {filtered.length > 0 ? (
          filtered.map((page) => (
            <button
              key={page.slug}
              onClick={() => handlePageClick(page.slug, page.title)}
              className={cn(
                'block px-3 py-2 rounded-lg transition text-sm cursor-pointer w-full text-left',
                'hover:bg-bg-hover text-text-primary'
              )}
              title={page.title}
            >
              <div className="truncate font-medium text-xs">{page.title}</div>
              <div className="flex items-center gap-1.5 mt-0.5">
                <Badge variant={page.category as never} className="text-[9px] py-0 px-1">
                  {page.category}
                </Badge>
                <span className="text-[9px] text-text-muted">
                  {new Date(page.updated_at).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })}
                </span>
              </div>
            </button>
          ))
        ) : (
          <div className="px-3 py-4 text-xs text-text-muted text-center">
            {q ? '未找到匹配的页面' : '暂无页面'}
          </div>
        )}
      </div>
    </>
  )
}
