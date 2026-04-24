import { useState, useRef, useEffect } from 'react'
import { cn } from '@/lib/utils'
import { usePageLayout } from '@/hooks/usePageLayout'
import { useIngestFile, useIngestUrl, useIngestProgress } from '@/hooks/useIngest'
import { useIngestStore, type IngestProgressState } from '@/stores/ingest'
import { IngestSidebar } from '@/components/layout/sidebars/IngestSidebar'
import { IngestProgressPanel } from '@/components/layout/detail-panels/IngestProgressPanel'

export default function Ingest() {
  usePageLayout({
    sidebar: <IngestSidebar />,
    detailPanel: <IngestProgressPanel />,
  })

  const { method, setProgress, resetProgress } = useIngestStore()

  // File upload state
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)

  // URL state
  const [urlValue, setUrlValue] = useState('')

  // Shared options
  const [autoCompile, setAutoCompile] = useState(true)

  // Task / progress state
  const [taskId, setTaskId] = useState<string | null>(null)
  const { state: progressState, connect, disconnect, steps, pct } = useIngestProgress(taskId)

  // Mutations
  const fileMutation = useIngestFile()
  const urlMutation = useIngestUrl()

  // Sync progress to store
  useEffect(() => {
    if (!progressState && !taskId) return

    const statusMap: Record<string, string> = {
      queued: 'connecting',
      parsing: 'processing',
      reading_context: 'processing',
      calling_llm: 'processing',
      writing_pages: 'processing',
      updating_index: 'processing',
      completed: 'completed',
      failed: 'failed',
    }

    setProgress({
      status: (statusMap[progressState?.status || ''] || 'connecting') as IngestProgressState['status'],
      steps,
      pct,
      error: progressState?.status === 'failed' ? progressState.error || undefined : undefined,
      taskId: taskId || undefined,
    })
  }, [progressState, taskId, steps, pct, setProgress])

  // Reset on unmount
  useEffect(() => {
    return () => {
      disconnect()
    }
  }, [disconnect])

  const handleSubmitFile = async () => {
    if (!selectedFile) return
    disconnect()
    resetProgress()
    const result = await fileMutation.mutateAsync({ file: selectedFile, auto_compile: autoCompile })
    if ('task_id' in result && result.task_id) {
      setTaskId(result.task_id)
      setTimeout(() => connect(), 0)
    }
  }

  const handleSubmitUrl = async () => {
    if (!urlValue.trim()) return
    disconnect()
    resetProgress()
    const result = await urlMutation.mutateAsync({ url: urlValue.trim(), auto_compile: true })
    if ('task_id' in result && result.task_id) {
      setTaskId(result.task_id)
      setTimeout(() => connect(), 0)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    if (e.dataTransfer.files.length) {
      setSelectedFile(e.dataTransfer.files[0])
    }
  }

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div className="flex-1 overflow-y-auto p-4 sm:p-6">
        {/* File Upload View */}
        {method === 'file' && (
          <div className="max-w-2xl mx-auto w-full">
            <div className="mb-5">
              <h1 className="text-xl font-bold tracking-tight text-text-primary">上传文件</h1>
              <p className="text-sm mt-0.5 text-text-tertiary">支持 PDF、Markdown、TXT、DOCX、HTML</p>
            </div>

            <div className="card p-6">
              <div
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                className={cn(
                  'border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition',
                  dragOver ? 'border-accent-neural bg-bg-elevated' : 'border-border-medium bg-bg-elevated'
                )}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  className="hidden"
                  accept=".pdf,.md,.txt,.docx,.html"
                  onChange={(e) => e.target.files?.[0] && setSelectedFile(e.target.files[0])}
                />
                {!selectedFile ? (
                  <div>
                    <div className="text-4xl mb-3 opacity-60">📄</div>
                    <p className="text-text-secondary">拖拽文件到此处，或 <span className="text-accent-neural">点击选择</span></p>
                    <p className="text-xs text-text-muted">PDF / MD / TXT / DOCX / HTML</p>
                  </div>
                ) : (
                  <div>
                    <div className="text-4xl mb-3 text-accent-living">✅</div>
                    <p className="font-medium text-text-primary">{selectedFile.name}</p>
                    <p className="text-sm mt-1 text-text-muted">{(selectedFile.size / 1024).toFixed(1)} KB</p>
                  </div>
                )}
              </div>
              <div className="mt-4 flex items-center justify-between">
                <label className="flex items-center gap-2 text-sm cursor-pointer text-text-secondary">
                  <input
                    type="checkbox"
                    checked={autoCompile}
                    onChange={(e) => setAutoCompile(e.target.checked)}
                    className="rounded border-border-medium text-accent-neural focus:ring-accent-neural"
                  />
                  自动编译为 Wiki
                </label>
                <button
                  onClick={handleSubmitFile}
                  disabled={!selectedFile || fileMutation.isPending}
                  className="btn btn-primary text-sm disabled:opacity-50"
                >
                  {fileMutation.isPending ? '上传中...' : '上传并处理'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* URL View */}
        {method === 'url' && (
          <div className="max-w-2xl mx-auto w-full">
            <div className="mb-5">
              <h1 className="text-xl font-bold tracking-tight text-text-primary">粘贴 URL</h1>
              <p className="text-sm mt-0.5 text-text-tertiary">自动采集网页正文内容并编译为 Wiki</p>
            </div>

            <div className="card p-6">
              <div className="flex gap-2">
                <input
                  type="url"
                  placeholder="https://example.com/article"
                  className="input flex-1"
                  value={urlValue}
                  onChange={(e) => setUrlValue(e.target.value)}
                />
                <button
                  onClick={handleSubmitUrl}
                  disabled={!urlValue.trim() || urlMutation.isPending}
                  className="btn btn-primary text-sm whitespace-nowrap disabled:opacity-50"
                >
                  {urlMutation.isPending ? '采集中...' : '采集并编译'}
                </button>
              </div>
              <p className="text-xs mt-3 text-text-muted">支持普通网页、微信公众号文章、知乎、Medium 等</p>

              <div className="mt-4 p-3 rounded-lg bg-bg-elevated border border-border-subtle">
                <div className="text-xs font-medium mb-1.5 text-text-secondary">💡 提示</div>
                <div className="text-xs text-text-tertiary">URL 采集会自动提取正文内容，去除广告和导航，保留核心文本。复杂页面可能需要几秒钟。</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
