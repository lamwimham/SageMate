import { useIngestStore } from '@/stores/ingest'
import { cn } from '@/lib/utils'

const INGEST_METHODS = [
  { key: 'file', label: '文件上传', desc: 'PDF / DOCX / MD', icon: (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  )},
  { key: 'url', label: '粘贴 URL', desc: '网页采集', icon: (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
    </svg>
  )},
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
              'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-150 text-sm w-full text-left',
              method === m.key
                ? 'bg-accent-neural/10 text-accent-neural'
                : 'text-text-secondary hover:bg-bg-hover'
            )}
          >
            <span className={cn('w-7 h-7 rounded-md flex items-center justify-center', method === m.key ? 'bg-accent-neural/10' : 'bg-bg-elevated/50')}>{m.icon}</span>
            <div>
              <div className="font-medium">{m.label}</div>
              <div className="text-[12px] text-text-muted">{m.desc}</div>
            </div>
          </button>
        ))}
      </div>
    </>
  )
}
