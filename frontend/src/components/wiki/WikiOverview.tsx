import { usePages } from '@/hooks/useWiki'
import { useStats } from '@/hooks/useSystem'
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

export function WikiOverview() {
  const { data: stats } = useStats()
  const { data: recentPages } = usePages()
  const displayPages = recentPages?.slice(0, 5) ?? []

  return (
    <>
      {/* Stats */}
      <div className="px-3 py-3">
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
      </div>

      {/* Recent */}
      {displayPages.length > 0 && (
        <>
          <div className="px-3 py-1.5 border-t border-border-subtle">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted">最近更新</span>
          </div>
          <div className="px-2 py-1 space-y-0.5">
            {displayPages.map((page) => (
              <a
                key={page.slug}
                href={`/wiki/${page.slug}`}
                className="block px-3 py-1.5 rounded-lg text-xs transition hover:bg-bg-hover truncate"
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
              </a>
            ))}
          </div>
        </>
      )}
    </>
  )
}
