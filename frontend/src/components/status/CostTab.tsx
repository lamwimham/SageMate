import { useCost } from '@/hooks/useSystem'
import { EmptyState } from '@/components/ui/EmptyState'
import { cn } from '@/lib/utils'

export function CostTab() {
  const { data: costData } = useCost()
  const costSummary = costData?.summary
  const costRecent = costData?.recent ?? []

  if (!costSummary) {
    return (
      <div className="animate-fade-up">
        <div className="mb-5">
          <h2 className="text-lg font-semibold text-text-primary">成本统计</h2>
          <p className="text-sm mt-0.5 text-text-tertiary">LLM API 调用成本与 Token 使用</p>
        </div>
        <EmptyState icon="chart" title="暂无成本数据" description="进行 LLM 调用后将自动记录" />
      </div>
    )
  }

  return (
    <div className="animate-fade-up">
      <div className="mb-5">
        <h2 className="text-lg font-semibold text-text-primary">成本统计</h2>
        <p className="text-sm mt-0.5 text-text-tertiary">LLM API 调用成本与 Token 使用</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
        <div className="card p-5">
          <div className="text-xs font-semibold uppercase tracking-wider mb-1 text-text-muted">总成本 (30天)</div>
          <div className="text-2xl font-bold font-mono text-accent-growth">${(costSummary.total_cost_usd ?? costSummary.total_cost ?? 0).toFixed(4)}</div>
        </div>
        <div className="card p-5">
          <div className="text-xs font-semibold uppercase tracking-wider mb-1 text-text-muted">总 Token 数</div>
          <div className="text-2xl font-bold font-mono text-accent-neural">{(costSummary.total_tokens ?? 0).toLocaleString()}</div>
        </div>
        <div className="card p-5">
          <div className="text-xs font-semibold uppercase tracking-wider mb-1 text-text-muted">调用次数</div>
          <div className="text-2xl font-bold font-mono text-text-primary">{costSummary.total_calls ?? 0}</div>
        </div>
      </div>

      {/* Breakdown by purpose */}
      {costSummary.by_purpose && costSummary.by_purpose.length > 0 && (
        <div className="card overflow-hidden mb-5" style={{ padding: 0 }}>
          <div className="px-6 py-4 border-b border-border-subtle">
            <h3 className="text-sm font-semibold text-text-secondary">按用途分布</h3>
          </div>
          <div className="p-4 space-y-3">
            {costSummary.by_purpose.map((item: any) => (
              <div key={item.purpose} className="flex items-center gap-3">
                <div className="w-24 text-xs text-text-muted">{item.purpose}</div>
                <div className="flex-1 h-2 bg-bg-elevated rounded-full overflow-hidden">
                  <div
                    className="h-full bg-accent-neural/60 rounded-full transition-all duration-300"
                    style={{ width: `${Math.min(100, (item.cost / (costSummary.total_cost_usd || 1)) * 100)}%` }}
                  />
                </div>
                <div className="w-20 text-xs font-mono text-text-secondary text-right">${item.cost.toFixed(4)}</div>
                <div className="w-16 text-[10px] text-text-muted text-right">{item.calls} 次</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Breakdown by model */}
      {costSummary.by_model && costSummary.by_model.length > 0 && (
        <div className="card overflow-hidden mb-5" style={{ padding: 0 }}>
          <div className="px-6 py-4 border-b border-border-subtle">
            <h3 className="text-sm font-semibold text-text-secondary">按模型分布</h3>
          </div>
          <div className="p-4 space-y-3">
            {costSummary.by_model.map((item: any) => (
              <div key={item.model} className="flex items-center gap-3">
                <div className="w-24 text-xs font-medium text-text-primary">{item.model}</div>
                <div className="flex-1 h-2 bg-bg-elevated rounded-full overflow-hidden">
                  <div
                    className="h-full bg-accent-growth/60 rounded-full transition-all duration-300"
                    style={{ width: `${Math.min(100, (item.cost / (costSummary.total_cost_usd || 1)) * 100)}%` }}
                  />
                </div>
                <div className="w-20 text-xs font-mono text-text-secondary text-right">${item.cost.toFixed(4)}</div>
                <div className="w-16 text-[10px] text-text-muted text-right">{item.calls} 次</div>
              </div>
            ))}
          </div>
        </div>
      )}

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
    </div>
  )
}
