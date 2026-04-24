import { useState, useRef } from 'react'
import { cn } from '@/lib/utils'
import { usePageLayout } from '@/hooks/usePageLayout'
import { useIngestFile, useIngestUrl } from '@/hooks/useIngest'
import { useIngestStore } from '@/stores/ingest'
import { IngestSidebar } from '@/components/layout/sidebars/IngestSidebar'
import { CompileTaskPanel } from '@/components/layout/detail-panels/CompileTaskPanel'

export default function Ingest() {
  usePageLayout({
    sidebar: <IngestSidebar />,
    detailPanel: <CompileTaskPanel />,
  })

  const { method } = useIngestStore()

  // File upload state
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)

  // URL state
  const [urlValue, setUrlValue] = useState('')

  // Shared options
  const [autoCompile, setAutoCompile] = useState(true)

  // Mutations
  const fileMutation = useIngestFile()
  const urlMutation = useIngestUrl()

  const handleSubmitFile = async () => {
    if (!selectedFile) return
    await fileMutation.mutateAsync({ file: selectedFile, auto_compile: autoCompile })
  }

  const handleSubmitUrl = async () => {
    if (!urlValue.trim()) return
    await urlMutation.mutateAsync({ url: urlValue.trim(), auto_compile: true })
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
                    <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-accent-neural/5 flex items-center justify-center">
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="w-8 h-8 text-accent-neural/60">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <polyline points="17 8 12 3 7 8" />
                        <line x1="12" y1="3" x2="12" y2="15" />
                      </svg>
                    </div>
                    <p className="text-text-secondary">拖拽文件到此处，或 <span className="text-accent-neural">点击选择</span></p>
                    <p className="text-xs text-text-muted">PDF / MD / TXT / DOCX / HTML</p>
                  </div>
                ) : (
                  <div>
                    <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-accent-living/5 flex items-center justify-center">
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-8 h-8 text-accent-living">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                        <polyline points="22 4 12 14.01 9 11.01" />
                      </svg>
                    </div>
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

              <div className="mt-4 p-3 rounded-lg bg-bg-elevated/50 border border-border-subtle/60">
                <div className="flex items-start gap-2">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 text-accent-neural shrink-0 mt-0.5">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="16" x2="12" y2="12" />
                    <line x1="12" y1="8" x2="12.01" y2="8" />
                  </svg>
                  <div>
                    <div className="text-xs font-medium mb-1 text-text-secondary">提示</div>
                    <div className="text-xs text-text-tertiary">URL 采集会自动提取正文内容，去除广告和导航，保留核心文本。复杂页面可能需要几秒钟。</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
