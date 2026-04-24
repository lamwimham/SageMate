import { useRawFilesStore } from '@/stores/rawFiles'
import { cn } from '@/lib/utils'

function FileIcon({ ext, mime }: { ext: string; mime: string }) {
  const isPdf = ext === '.pdf'
  const isDocx = ext === '.docx'
  const isMd = ['.md', '.markdown'].includes(ext)
  const isImage = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'].includes(ext) || mime?.startsWith('image/')

  if (isPdf) return <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 text-accent-danger"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><path d="M9 15h6" /></svg>
  if (isDocx) return <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 text-cat-entity"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /></svg>
  if (isMd) return <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 text-accent-neural"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><path d="M10 13l-2 2 2 2" /><path d="M14 13l2 2-2 2" /></svg>
  if (isImage) return <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 text-accent-warm"><rect x="3" y="3" width="18" height="18" rx="2" ry="2" /><circle cx="8.5" cy="8.5" r="1.5" /><polyline points="21 15 16 10 5 21" /></svg>
  return <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 text-text-muted"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /></svg>
}

export function RawFilesSidebar() {
  const { files, selectedIndex, setSelectedIndex } = useRawFilesStore()

  if (files.length === 0) {
    return (
      <>
        <div className="px-4 py-3 border-b border-border-subtle">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted">原始档案</h3>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center p-6">
          <div className="w-10 h-10 mb-2 rounded-xl bg-bg-elevated/50 flex items-center justify-center">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5 text-text-muted/50">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          <p className="text-xs text-text-muted text-center">暂无原始文件</p>
        </div>
      </>
    )
  }

  return (
    <>
      <div className="px-4 py-3 border-b border-border-subtle">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted">原始档案</h3>
        <p className="text-[12px] mt-0.5 text-text-muted">{files.length} 个文件</p>
      </div>
      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
        {files.map((f, i) => (
          <button
            key={f.rel_path}
            onClick={() => setSelectedIndex(i)}
            className={cn(
              'flex gap-2.5 py-2 px-2 w-full text-left rounded-lg cursor-pointer transition-all duration-150',
              i === selectedIndex ? 'bg-accent-neural/8' : 'hover:bg-bg-hover'
            )}
          >
            <div className="shrink-0 w-7 h-7 rounded-md flex items-center justify-center bg-bg-elevated/50 mt-0.5">
              <FileIcon ext={f.ext} mime={f.mime} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium truncate text-text-primary">{f.name}</div>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className="text-[10px] font-mono text-text-muted">{f.modified.slice(5, 16)}</span>
                <span className="text-[10px] text-text-muted">{f.size_human}</span>
              </div>
            </div>
          </button>
        ))}
      </div>
    </>
  )
}
