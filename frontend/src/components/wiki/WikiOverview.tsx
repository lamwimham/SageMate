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
  icon: React.ReactNode
  color: string
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <div className="flex items-center gap-2">
        <div className={cn('w-7 h-7 rounded-md flex items-center justify-center', color)}>
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

export function WikiOverview() {
  const { data: stats } = useStats()
  const { data: recentPages } = usePages()
  const openPage = useWikiTabsStore((s) => s.openPage)
  const displayPages = recentPages?.slice(0, 5) ?? []

  return (
    <>
      {/* Stats */}
      <div className="card p-4 mb-4">
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
              icon={
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
                  <path d="M4 3h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z" />
                  <path d="M8 7h6" />
                  <path d="M8 10h6" />
                </svg>
              }
              color="text-accent-neural bg-accent-neural/8 border-accent-neural/12"
            />
            <StatBadge
              label="已归档来源"
              value={stats.sources ?? 0}
              icon={
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
                  <path d="M12 5v12M5 12h14" />
                </svg>
              }
              color="text-accent-living bg-accent-living/8 border-accent-living/12"
            />
            <StatBadge
              label="知识库健康"
              value={`${stats.health_score ?? 100}分`}
              icon={
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
                  <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
                </svg>
              }
              color="text-accent-living bg-accent-living/8 border-accent-living/12"
            />
            <StatBadge
              label="今日活动"
              value={stats.today_activity ?? 0}
              icon={
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
                  <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
                </svg>
              }
              color="text-accent-growth bg-accent-growth/8 border-accent-growth/12"
            />
          </>
        )}
      </div>

      {/* Recent */}
      {displayPages.length > 0 && (
        <div className="card overflow-hidden" style={{ padding: 0 }}>
          <div className="px-4 py-3 border-b border-border-subtle">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">最近更新</span>
          </div>
          <div className="px-2 py-1.5 space-y-0.5">
            {displayPages.map((page) => (
              <button
                key={page.slug}
                onClick={() => openPage(page.slug, page.title)}
                className="w-full text-left px-3 py-2 rounded-lg text-xs transition-all duration-150 hover:bg-bg-hover cursor-pointer"
                title={page.title}
              >
                <div className="truncate font-medium text-text-primary text-[12px]">{page.title}</div>
                <div className="flex items-center gap-1.5 mt-1">
                  <Badge variant={page.category as never} className="text-[10px] py-0.5 px-1.5 rounded-md">
                    {page.category}
                  </Badge>
                  <span className="text-[10px] text-text-muted">
                    {new Date(page.updated_at).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </>
  )
}
