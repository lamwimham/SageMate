import { useLogs } from '@/hooks/useSystem'
import { MarkdownRenderer } from '@/components/markdown/MarkdownRenderer'
import { EmptyState } from '@/components/ui/EmptyState'

export function LogTab() {
  const { data: logData } = useLogs()
  const logContent = logData?.content ?? ''

  return (
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
  )
}
