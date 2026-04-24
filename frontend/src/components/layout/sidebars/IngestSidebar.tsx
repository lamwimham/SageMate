import { useIngestStore } from '@/stores/ingest'
import { cn } from '@/lib/utils'

const INGEST_METHODS = [
  { key: 'file', label: '文件上传', desc: 'PDF / DOCX / MD', icon: '📄' },
  { key: 'url', label: '粘贴 URL', desc: '网页采集', icon: '🔗' },
] as const

const SHORTCUTS = [
  ['标题 H1-H3', 'Ctrl+1'],
  ['加粗', 'Ctrl+B'],
  ['斜体', 'Ctrl+I'],
  ['行内代码', 'Ctrl+E'],
  ['链接', 'Ctrl+K'],
  ['双向链接', 'Ctrl+L'],
  ['无序列表', 'Ctrl+U'],
  ['引用', 'Ctrl+Q'],
  ['预览', 'Ctrl+Shift+V'],
] as const

export function IngestSidebar() {
  const { method, setMethod } = useIngestStore()

  return (
    <>
      <div className="px-4 py-3 border-b border-border-subtle">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted">输入方式</h3>
      </div>
      <div className="px-2 py-2 space-y-0.5">
        {INGEST_METHODS.map((m) => (
          <button
            key={m.key}
            onClick={() => setMethod(m.key)}
            className={cn(
              'flex items-center gap-3 px-3 py-2.5 rounded-lg transition text-sm w-full text-left',
              method === m.key
                ? 'bg-accent-neural/10 text-accent-neural'
                : 'text-text-secondary hover:bg-bg-hover'
            )}
          >
            <span className="w-6 text-center text-lg">{m.icon}</span>
            <div>
              <div className="font-medium">{m.label}</div>
              <div className="text-[10px] text-text-muted">{m.desc}</div>
            </div>
          </button>
        ))}

        <div className="border-t border-border-subtle my-3" />
        <div className="px-3 py-2">
          <div className="text-[10px] font-semibold uppercase tracking-wider mb-2 text-text-muted">快捷键</div>
          <div className="space-y-1 text-[10px] text-text-tertiary">
            {SHORTCUTS.map(([label, key]) => (
              <div key={label} className="flex justify-between">
                <span>{label}</span>
                <kbd className="font-mono bg-bg-elevated px-1 rounded">{key}</kbd>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  )
}
