import { useState } from 'react'
import { Search, PlusCircle } from 'lucide-react'
import { useSources } from '@/hooks/useSources'
import { Input } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'
import { cn } from '@/lib/utils'

const STATUS_CONFIG: Record<string, { label: string; color: string; dot: string }> = {
  completed: { label: '成功', color: 'text-accent-living', dot: 'bg-accent-living' },
  failed: { label: '失败', color: 'text-accent-danger', dot: 'bg-accent-danger' },
  pending: { label: '等待中', color: 'text-accent-growth', dot: 'bg-accent-growth' },
  processing: { label: '处理中', color: 'text-accent-growth', dot: 'bg-accent-growth' },
}

function SourceTypeIcon({ type }: { type: string }) {
  const iconMap: Record<string, string> = {
    pdf: '📕',
    docx: '📘',
    markdown: '📝',
    md: '📝',
    url: '🔗',
    text: '📃',
  }
  return <span>{iconMap[type] || '📄'}</span>
}

export default function Sources() {
  const [statusFilter, setStatusFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [query, setQuery] = useState('')

  const { data } = useSources(statusFilter || undefined, typeFilter || undefined, query || undefined)
  const sources = data?.sources ?? []
  const sourceTypes = data?.source_types ?? []

  return (
    <div className="p-4 sm:p-6 h-full overflow-y-auto">
      {/* Header */}
      <div className="mb-5 animate-fade-up flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-text-primary">已归档来源</h1>
          <p className="text-sm mt-0.5 text-text-tertiary">所有上传的原始文件及其处理状态</p>
        </div>
        {(statusFilter || typeFilter) && (
          <button
            onClick={() => { setStatusFilter(''); setTypeFilter('') }}
            className="text-xs font-medium text-accent-neural"
          >
            清除筛选 →
          </button>
        )}
      </div>

      {/* Search */}
      <div className="card p-4 mb-5 animate-fade-up stagger-1">
        <Input
          icon={<Search size={20} />}
          placeholder="搜索来源名称..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {/* Sources Table */}
      {sources.length > 0 ? (
        <div className="card overflow-hidden animate-fade-up stagger-2" style={{ padding: 0 }}>
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="bg-bg-elevated">
                <tr>
                  <th className="px-6 py-3.5 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">名称</th>
                  <th className="px-6 py-3.5 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">类型</th>
                  <th className="px-6 py-3.5 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">状态</th>
                  <th className="px-6 py-3.5 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">生成页面</th>
                  <th className="px-6 py-3.5 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">时间</th>
                </tr>
              </thead>
              <tbody>
                {sources.map((source, i) => {
                  const statusCfg = STATUS_CONFIG[source.status] || STATUS_CONFIG.pending
                  return (
                    <tr
                      key={source.slug}
                      className="transition cursor-pointer group"
                      style={{ borderBottom: i < sources.length - 1 ? '1px solid var(--color-border-subtle)' : undefined }}
                    >
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-xl flex items-center justify-center text-lg shrink-0 bg-bg-elevated border border-border-subtle">
                            <SourceTypeIcon type={source.source_type} />
                          </div>
                          <div>
                            <div className="text-sm font-medium text-text-primary">{source.title}</div>
                            <div className="text-xs font-mono text-text-muted">{source.slug}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <Badge variant="entity">{source.source_type}</Badge>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={cn('inline-flex items-center gap-1.5 text-sm font-medium', statusCfg.color)}>
                          <span className={cn('w-2 h-2 rounded-full', statusCfg.dot, source.status === 'processing' && 'animate-pulse')} />
                          {statusCfg.label}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-text-secondary">
                        {source.wiki_pages?.length > 0 ? (
                          <span className="font-medium font-mono text-accent-neural">{source.wiki_pages.length}</span>
                        ) : (
                          <span className="text-text-muted">-</span>
                        )} 页
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-text-muted">
                        {source.ingested_at ? source.ingested_at.slice(0, 10) : '-'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <EmptyState
          icon="📭"
          title="暂无来源文件"
          description="上传第一份文档来开始构建知识库"
          action={{ to: '/ingest', label: '摄入新文档', icon: <PlusCircle size={14} /> }}
        />
      )}

      {/* Type Filter Tags */}
      {sourceTypes.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          <span className="text-xs text-text-muted">按类型筛选:</span>
          {sourceTypes.map((t) => (
            <button
              key={t}
              onClick={() => setTypeFilter(typeFilter === t ? '' : t)}
              className={cn(
                'badge text-xs transition',
                typeFilter === t
                  ? 'bg-accent-neural/10 text-accent-neural'
                  : 'bg-bg-elevated text-text-tertiary hover:text-text-secondary'
              )}
            >
              {t}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
