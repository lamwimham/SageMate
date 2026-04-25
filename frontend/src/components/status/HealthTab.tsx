import { Link } from '@tanstack/react-router'
import { cn } from '@/lib/utils'
import { useLint, useRunLint } from '@/hooks/useSystem'
import { EmptyState } from '@/components/ui/EmptyState'

const SEVERITY_STYLES: Record<string, { bg: string; text: string }> = {
  high: { bg: 'bg-accent-danger/10', text: 'text-accent-danger' },
  medium: { bg: 'bg-accent-growth/10', text: 'text-accent-growth' },
  low: { bg: 'bg-cat-entity/10', text: 'text-cat-entity' },
}

export function HealthTab() {
  const { data: lintReport, isLoading, refetch } = useLint()
  const runLint = useRunLint()

  const handleRunLint = async () => {
    await runLint.mutateAsync()
    refetch()
  }

  return (
    <div className="animate-fade-up">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-semibold text-text-primary">知识库健康检查</h2>
          <p className="text-sm mt-0.5 text-text-tertiary">自动检测孤立页面、断链、过时声明等问题</p>
        </div>
        <button
          onClick={handleRunLint}
          disabled={runLint.isPending}
          className="btn btn-primary text-sm disabled:opacity-50"
        >
          {runLint.isPending ? '检查中...' : '重新检查'}
        </button>
      </div>

      {isLoading && !lintReport && (
        <div className="text-center py-12 text-text-muted animate-pulse">加载中...</div>
      )}

      {!isLoading && !lintReport && (
        <EmptyState icon="search" title="点击"重新检查"运行健康扫描" />
      )}

      {lintReport && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
            <div className="card p-4 text-center">
              <div className="text-2xl font-bold text-text-primary">{lintReport.total_pages_scanned}</div>
              <div className="text-xs mt-1 text-text-muted">扫描页面</div>
            </div>
            <div className="card p-4 text-center">
              <div className={cn('text-2xl font-bold', lintReport.issues.length === 0 ? 'text-accent-living' : 'text-text-primary')}>
                {lintReport.issues.length}
              </div>
              <div className="text-xs mt-1 text-text-muted">发现问题</div>
            </div>
            <div className="card p-4 text-center">
              <div className={cn(
                'text-2xl font-bold',
                lintReport.issues.some((i) => i.severity === 'high') ? 'text-accent-danger' : 'text-text-primary'
              )}>
                {lintReport.issues.filter((i) => i.severity === 'high').length}
              </div>
              <div className="text-xs mt-1 text-text-muted">高危问题</div>
            </div>
            <div className="card p-4 text-center">
              <div className="text-2xl font-bold font-mono text-text-primary">
                {lintReport.timestamp ? lintReport.timestamp.slice(5, 16).replace('T', ' ') : '-'}
              </div>
              <div className="text-xs mt-1 text-text-muted">检查时间</div>
            </div>
          </div>

          {lintReport.issues.length > 0 ? (
            <div className="card overflow-hidden" style={{ padding: 0 }}>
              <div className="px-6 py-4 border-b border-border-subtle">
                <h3 className="text-sm font-semibold text-text-secondary">问题列表</h3>
              </div>
              <div>
                {lintReport.issues.map((issue, i) => {
                  const severityStyle = SEVERITY_STYLES[issue.severity] || SEVERITY_STYLES.low
                  return (
                    <div
                      key={`${issue.page_slug}-${i}`}
                      className={cn('px-6 py-4 transition hover:bg-bg-hover', i < lintReport.issues.length - 1 && 'border-b border-border-subtle')}
                    >
                      <div className="flex items-start gap-3">
                        <div className={cn('w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 mt-0.5', severityStyle.bg, severityStyle.text)}>
                          {issue.severity[0].toUpperCase()}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <Link to="/wiki/$slug" params={{ slug: issue.page_slug }} className="text-sm font-medium text-accent-neural hover:underline">
                              {issue.page_slug}
                            </Link>
                            <span className="text-xs font-mono text-text-muted">{issue.issue_type}</span>
                          </div>
                          <p className="text-sm text-text-secondary">{issue.description}</p>
                          {issue.suggestion && (
                            <p className="text-xs mt-1 text-text-muted">建议: {issue.suggestion}</p>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ) : (
            <div className="card p-8 text-center">
              <EmptyState icon="search" title="知识库状态良好" description="未发现任何问题" />
            </div>
          )}
        </>
      )}
    </div>
  )
}
