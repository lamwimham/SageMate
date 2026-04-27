import { useEffect, useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { useCompileRawFile, useDeleteRawFile, useRawFiles } from '@/hooks/useSources'
import { useRawFilesStore } from '@/stores/rawFiles'
import { usePageLayout } from '@/hooks/usePageLayout'
import { MarkdownRenderer } from '@/components/markdown/MarkdownRenderer'
import { RawFilesSidebar } from '@/components/layout/sidebars/RawFilesSidebar'
import { FileIcon } from '@/components/icons/FileIcon'
import { EmptyState } from '@/components/ui/EmptyState'
import { cn } from '@/lib/utils'
import { useWikiTabsStore } from '@/stores/wikiTabs'

export default function RawFiles() {
  usePageLayout({
    sidebar: <RawFilesSidebar />,
  })

  const { data } = useRawFiles()
  const { setFiles, selectedFile } = useRawFilesStore()
  const compileRawFile = useCompileRawFile()
  const deleteRawFile = useDeleteRawFile()
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Sync fetched data to store
  useEffect(() => {
    if (data) {
      setFiles(data.files, data.raw_dir)
    }
  }, [data, setFiles])

  const selected = selectedFile()
  const previewUrl = selected?.preview_url || selected?.file_url
  const isBusy = compileRawFile.isPending || deleteRawFile.isPending

  const handleCompile = async () => {
    if (!selected || !selected.can_compile) return
    setNotice(null)
    setError(null)
    try {
      const res = await compileRawFile.mutateAsync(selected.rel_path)
      setNotice(res.message || `已提交编译任务：${res.task_id}`)
    } catch (err: any) {
      setError(err?.message || '提交编译失败')
    }
  }

  const handleDelete = async () => {
    if (!selected) return
    if (!window.confirm(`确认删除原始文件「${selected.name}」吗？此操作不可撤销。`)) return
    setNotice(null)
    setError(null)
    try {
      await deleteRawFile.mutateAsync(selected.rel_path)
      setNotice('原始文件已删除')
    } catch (err: any) {
      setError(err?.message || '删除失败')
    }
  }

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div className="flex-1 overflow-y-auto p-4">
        {!selected ? (
          <EmptyState icon="folder" title="从左侧选择一个文件查看详情和预览" />
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
                <button
                  onClick={handleCompile}
                  disabled={!selected.can_compile || isBusy}
                  className={cn(
                    'btn text-xs disabled:opacity-50 disabled:cursor-not-allowed',
                    selected.can_compile ? 'btn-secondary' : 'bg-bg-elevated text-text-muted border-border-subtle'
                  )}
                  title={selected.compile_disabled_reason || '编译为 Wiki'}
                >
                  {compileRawFile.isPending
                    ? '提交中...'
                    : !selected.can_compile
                      ? (selected.compile_disabled_reason || '不可编译')
                      : '编译'}
                </button>
                <a href={selected.file_url} download className="btn btn-secondary text-xs">
                  下载
                </a>
                <button
                  onClick={handleDelete}
                  disabled={isBusy}
                  className="btn btn-secondary text-xs text-accent-danger disabled:opacity-50"
                >
                  {deleteRawFile.isPending ? '删除中...' : '删除'}
                </button>
                <a href={previewUrl} target="_blank" rel="noopener noreferrer" className="btn btn-primary text-xs">
                  新窗口
                </a>
              </div>
            </div>

            {(notice || error) && (
              <div className={cn(
                'card px-4 py-3 text-xs',
                error ? 'text-accent-danger border-accent-danger/30' : 'text-accent-living border-accent-living/30'
              )}>
                {error || notice}
              </div>
            )}

            {/* Linked source info */}
            {selected.linked_source && (
              <div className="card p-4">
                <div className="text-xs font-semibold text-text-muted mb-2">关联源</div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-text-primary">{selected.linked_source.title}</span>
                  <span className={cn(
                    'text-[12px] px-1.5 py-0.5 rounded',
                    selected.linked_source.status === 'completed' && !selected.can_compile ? 'bg-accent-living/10 text-accent-living' :
                    selected.linked_source.status === 'failed' ? 'bg-accent-danger/10 text-accent-danger' :
                    'bg-bg-elevated text-text-muted'
                  )}>
                    {selected.linked_source.status === 'completed' && selected.can_compile
                      ? '未编译'
                      : formatSourceStatus(selected.linked_source.status)}
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
                    <WikiPageLink key={wp.slug} slug={wp.slug} title={wp.title} />
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
                <iframe
                  key={selected.rel_path}
                  src={previewUrl}
                  title={selected.name}
                  className="w-full"
                  style={{ height: 800, border: 'none' }}
                />
              </div>
            ) : selected.is_image ? (
              <div className="text-center">
                <div className="card p-6 inline-block">
                  <img src={previewUrl} alt={selected.name} className="max-w-full rounded-lg max-h-[70vh] border border-border-subtle" />
                </div>
              </div>
            ) : selected.is_docx ? (
              <div className="card overflow-hidden" style={{ padding: 0 }}>
                <iframe
                  key={selected.rel_path}
                  src={previewUrl}
                  title={selected.name}
                  className="w-full"
                  style={{ height: 800, border: 'none' }}
                />
              </div>
            ) : (
              <div className="card py-12 text-center">
                <EmptyState icon="file" title="此文件为二进制格式，无法直接预览" size="md" />
                <a href={selected.file_url} download className="btn btn-primary text-xs mt-2">
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

function formatSourceStatus(status: string) {
  const labels: Record<string, string> = {
    archived: '未编译',
    pending: '待编译',
    processing: '编译中',
    completed: '已编译',
    failed: '编译失败',
  }
  return labels[status] || status
}

function WikiPageLink({ slug, title }: { slug: string; title: string }) {
  const navigate = useNavigate()
  const openPage = useWikiTabsStore((s) => s.openPage)

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    openPage(slug, title)
    navigate({ to: '/wiki' })
  }

  return (
    <a
      href={`/wiki/${slug}`}
      onClick={handleClick}
      className="block text-xs text-accent-neural hover:text-accent-secondary transition truncate cursor-pointer"
    >
      → {title}
    </a>
  )
}
