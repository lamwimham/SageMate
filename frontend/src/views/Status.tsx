import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import { cn } from '@/lib/utils'
import { usePageLayout } from '@/hooks/usePageLayout'
import { StatusSidebar } from '@/components/layout/sidebars/StatusSidebar'
import { useLint, useRunLint, useCost, useCron, useLogs } from '@/hooks/useSystem'
import { MarkdownRenderer } from '@/components/markdown/MarkdownRenderer'
import { EmptyState } from '@/components/ui/EmptyState'

const TABS = [
  { key: 'health', label: '健康检查', icon: (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
    </svg>
  )},
  { key: 'log', label: '活动日志', icon: (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
    </svg>
  )},
  { key: 'cost', label: '成本统计', icon: (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <line x1="12" y1="1" x2="12" y2="23" />
      <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
    </svg>
  )},
  { key: 'cron', label: '定时任务', icon: (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  )},
] as const

type TabKey = (typeof TABS)[number]['key']

const SEVERITY_STYLES: Record<string, { bg: string; text: string }> = {
  high: { bg: 'bg-accent-danger/10', text: 'text-accent-danger' },
  medium: { bg: 'bg-accent-growth/10', text: 'text-accent-growth' },
  low: { bg: 'bg-cat-entity/10', text: 'text-cat-entity' },
}

export default function Status() {
  usePageLayout({
    sidebar: <StatusSidebar />,
  })

  const [activeTab, setActiveTab] = useState<TabKey>('health')

  const { data: lintData, isLoading: lintLoading, refetch: refetchLint } = useLint()
  const runLint = useRunLint()

  const { data: costData } = useCost()
  const { data: cronData } = useCron()
  const { data: logData } = useLogs()

  const lintReport = lintData
  const costSummary = costData?.summary
  const costRecent = costData?.recent ?? []
  const cronStatus = cronData
  const logContent = logData?.content ?? ''

  const handleRunLint = async () => {
    await runLint.mutateAsync()
    refetchLint()
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 sm:p-6">
      {/* Tab Bar */}
      <div className="flex items-center gap-1 mb-5 animate-fade-up border-b border-border-subtle pb-0">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                'flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium transition rounded-t-lg cursor-pointer',
                activeTab === tab.key
                  ? 'bg-bg-surface text-accent-neural border border-border-subtle border-b-bg-surface -mb-px'
                  : 'text-text-muted border border-transparent hover:text-text-secondary'
              )}
            >
              {tab.icon} {tab.label}
            </button>
          ))}
        </div>

        {/* Health Tab */}
        {activeTab === 'health' && (
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

            {lintLoading && !lintReport && (
              <div className="text-center py-12 text-text-muted animate-pulse">加载中...</div>
            )}

            {!lintLoading && !lintReport && (
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
        )}

        {/* Log Tab */}
        {activeTab === 'log' && (
          <div className="animate-fade-up">
            <div className="mb-5">
              <h2 className="text-lg font-semibold text-text-primary">活动日志</h2>
              <p className="text-sm mt-0.5 text-text-tertiary">知识库的增删改查操作记录</p>
            </div>
            {logContent ? (
              <div className="card overflow-hidden p-6" style={{ padding: 0 }}>
                <div className="p-6 markdown-body">
                  <MarkdownRenderer content={logContent} />
                </div>
              </div>
            ) : (
              <EmptyState icon="clipboard" title="暂无活动日志" />
            )}
          </div>
        )}

        {/* Cost Tab */}
        {activeTab === 'cost' && (
          <div className="animate-fade-up">
            <div className="mb-5">
              <h2 className="text-lg font-semibold text-text-primary">成本统计</h2>
              <p className="text-sm mt-0.5 text-text-tertiary">LLM API 调用成本与 Token 使用</p>
            </div>

            {costSummary ? (
              <>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
                  <div className="card p-5">
                    <div className="text-xs font-semibold uppercase tracking-wider mb-1 text-text-muted">总成本 (30天)</div>
                    <div className="text-2xl font-bold font-mono text-accent-growth">${costSummary.total_cost.toFixed(4)}</div>
                  </div>
                  <div className="card p-5">
                    <div className="text-xs font-semibold uppercase tracking-wider mb-1 text-text-muted">总 Token 数</div>
                    <div className="text-2xl font-bold font-mono text-accent-neural">{costSummary.total_tokens.toLocaleString()}</div>
                  </div>
                  <div className="card p-5">
                    <div className="text-xs font-semibold uppercase tracking-wider mb-1 text-text-muted">调用次数</div>
                    <div className="text-2xl font-bold font-mono text-text-primary">{costSummary.total_calls}</div>
                  </div>
                </div>

                {costRecent.length > 0 && (
                  <div className="card overflow-hidden" style={{ padding: 0 }}>
                    <div className="px-6 py-4 border-b border-border-subtle">
                      <h3 className="text-sm font-semibold text-text-secondary">最近调用</h3>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="min-w-full">
                        <thead className="bg-bg-elevated">
                          <tr>
                            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">时间</th>
                            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">模型</th>
                            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">用途</th>
                            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Token</th>
                            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">成本</th>
                          </tr>
                        </thead>
                        <tbody>
                          {costRecent.map((entry, i) => (
                            <tr
                              key={i}
                              className={cn('transition hover:bg-bg-hover', i < costRecent.length - 1 && 'border-b border-border-subtle')}
                            >
                              <td className="px-4 py-3 text-sm font-mono text-text-tertiary">{entry.timestamp ? entry.timestamp.slice(0, 19) : '-'}</td>
                              <td className="px-4 py-3 text-sm font-medium text-text-primary">{entry.model}</td>
                              <td className="px-4 py-3 text-sm text-text-secondary">{entry.purpose || '-'}</td>
                              <td className="px-4 py-3 text-sm font-mono text-text-secondary">{(entry.total_tokens ?? entry.tokens_in + entry.tokens_out).toLocaleString()}</td>
                              <td className="px-4 py-3 text-sm font-medium font-mono text-accent-growth">${(entry.cost_usd ?? 0).toFixed(4)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <EmptyState icon="chart" title="暂无成本数据" description="进行 LLM 调用后将自动记录" />
            )}
          </div>
        )}

        {/* Cron Tab */}
        {activeTab === 'cron' && (
          <div className="animate-fade-up">
            <div className="mb-5">
              <h2 className="text-lg font-semibold text-text-primary">定时任务</h2>
              <p className="text-sm mt-0.5 text-text-tertiary">后台自动编译与检查任务状态</p>
            </div>

            {cronStatus ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="card p-5">
                  <div className="flex items-center justify-between mb-3">
                    <div className="text-xs font-semibold uppercase tracking-wider text-text-muted">调度器状态</div>
                    <span className={cn('inline-flex items-center gap-1.5 text-xs font-medium', cronStatus.running ? 'text-accent-living' : 'text-accent-danger')}>
                      <span className={cn('w-2 h-2 rounded-full', cronStatus.running && 'animate-pulse', cronStatus.running ? 'bg-accent-living' : 'bg-accent-danger')} />
                      {cronStatus.running ? '运行中' : '已停止'}
                    </span>
                  </div>
                  <div className="text-2xl font-bold font-mono text-text-primary">{cronStatus.active_tasks} 个活跃任务</div>
                </div>
                <div className="card p-5">
                  <div className="text-xs font-semibold uppercase tracking-wider mb-3 text-text-muted">自动编译</div>
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-medium text-text-primary">{cronStatus.auto_compile.enabled ? '已启用' : '已禁用'}</div>
                      <div className="text-xs mt-0.5 font-mono text-text-muted">每 {Math.floor(cronStatus.auto_compile.interval_seconds / 60)} 分钟</div>
                    </div>
                    <div className={cn(
                      'w-9 h-9 rounded-lg flex items-center justify-center',
                      cronStatus.auto_compile.enabled
                        ? 'bg-accent-living/8 border border-accent-living/15'
                        : 'bg-bg-elevated border border-border-subtle'
                    )}>
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={cn('w-4 h-4', cronStatus.auto_compile.enabled ? 'text-accent-living' : 'text-text-muted')}>
                        <polyline points="23 4 23 10 17 10" />
                        <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                      </svg>
                    </div>
                  </div>
                </div>
                <div className="card p-5">
                  <div className="text-xs font-semibold uppercase tracking-wider mb-3 text-text-muted">健康检查</div>
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-medium text-text-primary">{cronStatus.lint_check.enabled ? '已启用' : '已禁用'}</div>
                      <div className="text-xs mt-0.5 font-mono text-text-muted">每 {Math.floor(cronStatus.lint_check.interval_seconds / 60)} 分钟</div>
                    </div>
                    <div className={cn(
                      'w-9 h-9 rounded-lg flex items-center justify-center',
                      cronStatus.lint_check.enabled
                        ? 'bg-accent-neural/8 border border-accent-neural/15'
                        : 'bg-bg-elevated border border-border-subtle'
                    )}>
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={cn('w-4 h-4', cronStatus.lint_check.enabled ? 'text-accent-neural' : 'text-text-muted')}>
                        <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
                      </svg>
                    </div>
                  </div>
                </div>
                <div className="card p-5">
                  <div className="text-xs font-semibold uppercase tracking-wider mb-3 text-text-muted">系统信息</div>
                  <div className="text-sm font-medium text-text-primary">SageMate Core v0.4.0</div>
                  <div className="text-xs mt-0.5 text-text-muted">本地优先知识库</div>
                </div>
              </div>
            ) : (
              <EmptyState icon="clock" title="无法获取定时任务状态" />
            )}
          </div>
        )}
      </div>
  )
}
