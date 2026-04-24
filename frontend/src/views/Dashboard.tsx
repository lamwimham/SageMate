import { Link } from '@tanstack/react-router'
import { Search, PlusCircle } from 'lucide-react'
import { usePages } from '@/hooks/useWiki'
import { useStats } from '@/hooks/useSystem'
import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'
import { SkeletonCard } from '@/components/ui/Skeleton'
import { cn } from '@/lib/utils'

function CategoryBadge({ category }: { category: string }) {
  return (
    <Badge variant={(category as never) || 'default'}>
      {category}
    </Badge>
  )
}

export default function Dashboard() {
  const { data: stats } = useStats()
  const { data: recentPages } = usePages()

  const displayPages = recentPages?.slice(0, 10) ?? []

  return (
    <div className="p-4 sm:p-6 h-full overflow-y-auto">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl mb-6 p-5 sm:p-6 bg-gradient-to-br from-bg-surface via-bg-deep to-bg-elevated border border-border-subtle animate-fade-up">
        <div className="absolute top-0 right-0 w-96 h-96 opacity-30 pointer-events-none bg-[radial-gradient(circle_at_70%_20%,rgba(129,140,248,0.15),transparent_60%)]" />
        <div className="absolute bottom-0 left-0 w-72 h-72 opacity-20 pointer-events-none bg-[radial-gradient(circle_at_30%_80%,rgba(192,132,252,0.12),transparent_55%)]" />
        <div className="relative z-10 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-text-primary">知识库概览</h1>
            <p className="text-sm mt-1 text-text-tertiary">本地优先的持久化知识网络 · 文件即真相</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link to="/wiki" className="btn btn-secondary text-[0.8125rem] flex items-center gap-1.5">
              <Search size={15} /> 查询知识
            </Link>
            <Link to="/ingest" className="btn btn-primary text-[0.8125rem] flex items-center gap-1.5">
              <PlusCircle size={15} /> 摄入数据
            </Link>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {!stats ? (
          <>
            <SkeletonCard className="h-[88px]" />
            <SkeletonCard className="h-[88px]" />
            <SkeletonCard className="h-[88px]" />
            <SkeletonCard className="h-[88px]" />
          </>
        ) : (
          <>
            <StatCard
              label="Wiki 页面"
              value={stats.wiki_pages ?? 0}
              icon="📚"
              color="text-accent-neural"
              bg="bg-accent-neural/8 border-accent-neural/12"
              stagger="stagger-1"
            />
            <StatCard
              label="已归档来源"
              value={stats.sources ?? 0}
              icon="📥"
              color="text-accent-living"
              bg="bg-accent-living/8 border-accent-living/12"
              stagger="stagger-2"
            />
            <StatCard
              label="知识库健康"
              value="良好"
              icon="✅"
              color="text-accent-living"
              bg="bg-accent-living/8 border-accent-living/12"
              stagger="stagger-3"
            />
            <StatCard
              label="今日活动"
              value={0}
              icon="⚡"
              color="text-accent-growth"
              bg="bg-accent-growth/8 border-accent-growth/12"
              stagger="stagger-4"
            />
          </>
        )}
      </div>

      {/* Recent Pages */}
      <div className="animate-fade-up stagger-5">
        <div className="card overflow-hidden">
          <div className="px-5 py-4 flex items-center justify-between border-b border-border-subtle">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary">最近更新</h2>
            <Link to="/wiki" className="text-xs font-medium text-accent-neural">查看全部 →</Link>
          </div>
          {displayPages.length > 0 ? (
            <div>
              {displayPages.map((page, i) => (
                <Link
                  key={page.slug}
                  to="/wiki/$slug"
                  params={{ slug: page.slug }}
                  className="block px-5 py-4 transition group hover:bg-bg-hover"
                  style={{ borderBottom: i < displayPages.length - 1 ? '1px solid var(--color-border-subtle)' : undefined }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium truncate transition group-hover:text-accent-neural text-text-primary">
                          {page.title}
                        </span>
                        <CategoryBadge category={page.category} />
                      </div>
                      <p className="text-sm line-clamp-2 text-text-tertiary">{page.summary || '暂无摘要'}</p>
                    </div>
                    <span className="text-xs shrink-0 mt-1 font-mono text-text-muted">
                      {new Date(page.updated_at).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState
              icon="📝"
              title="暂无 Wiki 页面"
              action={{ to: '/ingest', label: '摄入第一份文档 →' }}
            />
          )}
        </div>
      </div>
    </div>
  )
}

function StatCard({
  label,
  value,
  icon,
  color,
  bg,
  stagger,
}: {
  label: string
  value: string | number
  icon: string
  color: string
  bg: string
  stagger: string
}) {
  return (
    <div className={cn('card card-glow p-5 animate-fade-up', stagger)}>
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="text-xs font-medium uppercase tracking-wider text-text-muted">{label}</div>
          <div className={cn('text-3xl font-bold mt-1', color)}>{value}</div>
        </div>
        <div className={cn('w-10 h-10 rounded-xl flex items-center justify-center text-xl border', bg)}>
          {icon}
        </div>
      </div>
    </div>
  )
}
