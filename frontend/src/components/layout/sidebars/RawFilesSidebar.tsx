import { useRawFilesStore } from '@/stores/rawFiles'
import { cn } from '@/lib/utils'

function FileIcon({ ext, mime }: { ext: string; mime: string }) {
  if (ext === '.pdf') return '📕'
  if (ext === '.docx') return '📘'
  if (['.md', '.markdown'].includes(ext)) return '📝'
  if (['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'].includes(ext)) return '🖼️'
  if (mime?.startsWith('image/')) return '🖼️'
  return '📃'
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
          <div className="text-2xl mb-2 opacity-40">📂</div>
          <p className="text-xs text-text-muted text-center">暂无原始文件</p>
        </div>
      </>
    )
  }

  return (
    <>
      <div className="px-4 py-3 border-b border-border-subtle">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted">原始档案</h3>
        <p className="text-[10px] mt-0.5 text-text-muted">{files.length} 个文件</p>
      </div>
      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
        {files.map((f, i) => (
          <button
            key={f.rel_path}
            onClick={() => setSelectedIndex(i)}
            className={cn(
              'flex gap-2.5 py-2 px-2 w-full text-left rounded-lg cursor-pointer transition',
              i === selectedIndex ? 'bg-accent-neural/8' : 'hover:bg-bg-hover'
            )}
          >
            <div className="shrink-0 text-base leading-5 mt-0.5">
              <FileIcon ext={f.ext} mime={f.mime} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium truncate text-text-primary">{f.name}</div>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className="text-[9px] font-mono text-text-muted">{f.modified.slice(5, 16)}</span>
                <span className="text-[9px] text-text-muted">{f.size_human}</span>
              </div>
            </div>
          </button>
        ))}
      </div>
    </>
  )
}
