import { useEffect } from 'react'
import { useRawFiles } from '@/hooks/useSources'
import { useRawFilesStore } from '@/stores/rawFiles'
import { usePageLayout } from '@/hooks/usePageLayout'
import { MarkdownRenderer } from '@/components/markdown/MarkdownRenderer'
import { RawFilesSidebar } from '@/components/layout/sidebars/RawFilesSidebar'
import { cn } from '@/lib/utils'

function FileIcon({ ext, mime }: { ext: string; mime: string }) {
  const isPdf = ext === '.pdf'
  const isDocx = ext === '.docx'
  const isMd = ['.md', '.markdown'].includes(ext)
  const isImage = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'].includes(ext) || mime?.startsWith('image/')

  if (isPdf) {
    return (
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5 text-accent-danger">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <path d="M9 15h6" />
      </svg>
    )
  }
  if (isDocx) {
    return (
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5 text-cat-entity">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
      </svg>
    )
  }
  if (isMd) {
    return (
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5 text-accent-neural">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <path d="M10 13l-2 2 2 2" />
        <path d="M14 13l2 2-2 2" />
      </svg>
    )
  }
  if (isImage) {
    return (
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5 text-accent-warm">
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
        <circle cx="8.5" cy="8.5" r="1.5" />
        <polyline points="21 15 16 10 5 21" />
      </svg>
    )
  }
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5 text-text-muted">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  )
}

export default function RawFiles() {
  usePageLayout({
    sidebar: <RawFilesSidebar />,
  })

  const { data } = useRawFiles()
  const { setFiles, selectedFile } = useRawFilesStore()

  // Sync fetched data to store
  useEffect(() => {
    if (data) {
      setFiles(data.files, data.raw_dir)
    }
  }, [data, setFiles])

  const selected = selectedFile()

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div className="flex-1 overflow-y-auto p-4">
        {!selected ? (
          <div className="flex flex-col items-center justify-center h-full text-center text-text-muted py-16">
            <div className="w-16 h-16 mb-4 rounded-2xl bg-bg-elevated/50 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="w-8 h-8 text-text-muted/60">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
              </svg>
            </div>
            <p className="text-sm text-text-tertiary">从左侧选择一个文件查看详情和预览</p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* File header */}
            <div className="card p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center text-xl bg-bg-elevated border border-border-subtle">
                  <FileIcon ext={selected.ext} mime={selected.mime} />
                </div>
                <div>
                  <h2 className="text-sm font-medium text-text-primary">{selected.name}</h2>
                  <p className="text-xs text-text-muted">{selected.mime} · {selected.size_human}</p>
                </div>
              </div>
              <div className="flex gap-2">
                <a href={selected.file_url} download className="btn btn-secondary text-xs">
                  下载
                </a>
                <a href={selected.file_url} target="_blank" rel="noopener noreferrer" className="btn btn-primary text-xs">
                  新窗口
                </a>
              </div>
            </div>

            {/* Linked source info */}
            {selected.linked_source && (
              <div className="card p-4">
                <div className="text-xs font-semibold text-text-muted mb-2">关联源</div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-text-primary">{selected.linked_source.title}</span>
                  <span className={cn(
                    'text-[12px] px-1.5 py-0.5 rounded',
                    selected.linked_source.status === 'completed' ? 'bg-accent-living/10 text-accent-living' :
                    selected.linked_source.status === 'failed' ? 'bg-accent-danger/10 text-accent-danger' :
                    'bg-bg-elevated text-text-muted'
                  )}>
                    {selected.linked_source.status}
                  </span>
                </div>
                {selected.linked_source.error && (
                  <div className="text-xs text-accent-danger mt-1 font-mono">{selected.linked_source.error}</div>
                )}
              </div>
            )}

            {/* Linked wiki pages */}
            {selected.linked_wiki_pages && selected.linked_wiki_pages.length > 0 && (
              <div className="card p-4">
                <div className="text-xs font-semibold text-text-muted mb-2">生成 Wiki 页面</div>
                <div className="space-y-1">
                  {selected.linked_wiki_pages.map((wp) => (
                    <a
                      key={wp.slug}
                      href={`/wiki/${wp.slug}`}
                      className="block text-xs text-accent-neural hover:text-accent-secondary transition truncate"
                    >
                      → {wp.title}
                    </a>
                  ))}
                </div>
              </div>
            )}

            {/* Preview */}
            {selected.is_text ? (
              <div className="card overflow-hidden" style={{ padding: 0 }}>
                <div className="px-4 py-2 flex items-center justify-between border-b border-border-subtle bg-bg-elevated">
                  <span className="text-xs font-mono text-text-muted">文本预览</span>
                  <span className="text-xs text-text-muted">{(selected.content || '').length} 字符</span>
                </div>
                <div className="p-5 overflow-x-auto">
                  {selected.is_markdown && selected.content ? (
                    <MarkdownRenderer content={selected.content} />
                  ) : (
                    <pre className="text-sm font-mono whitespace-pre text-text-secondary leading-relaxed">
                      {selected.content || ''}
                    </pre>
                  )}
                </div>
              </div>
            ) : selected.is_pdf ? (
              <div className="card overflow-hidden bg-white">
                <iframe src={selected.file_url} className="w-full" style={{ height: 800, border: 'none' }} />
              </div>
            ) : selected.is_image ? (
              <div className="text-center">
                <div className="card p-6 inline-block">
                  <img src={selected.file_url} alt={selected.name} className="max-w-full rounded-lg max-h-[70vh] border border-border-subtle" />
                </div>
              </div>
            ) : selected.is_docx ? (
              <div className="card overflow-hidden" style={{ padding: 0 }}>
                <iframe
                  src={`/web/raw/view?path=${encodeURIComponent(selected.rel_path)}&embed=1`}
                  className="w-full"
                  style={{ height: 800, border: 'none' }}
                />
              </div>
            ) : (
              <div className="card py-12 text-center">
                <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-bg-elevated/50 flex items-center justify-center">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="w-8 h-8 text-text-muted/50">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                  </svg>
                </div>
                <p className="text-text-tertiary">此文件为二进制格式，无法直接预览</p>
                <a href={selected.file_url} download className="btn btn-primary text-xs mt-4">
                  下载文件
                </a>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
