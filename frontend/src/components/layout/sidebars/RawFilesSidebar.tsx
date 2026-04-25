import { useRawFilesStore } from '@/stores/rawFiles'
import { FileIcon } from '@/components/icons/FileIcon'
import { EmptyState } from '@/components/ui/EmptyState'
import { cn } from '@/lib/utils'

export function RawFilesSidebar() {
  const { files, selectedIndex, setSelectedIndex } = useRawFilesStore()

  if (files.length === 0) {
    return (
      <>
        <div className="px-4 py-3 border-b border-border-subtle">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted">原始档案</h3>
        </div>
        <EmptyState icon="folder" title="暂无原始文件" size="sm" className="py-8" />
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
              <FileIcon ext={f.ext} mime={f.mime} size="sm" />
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
