import { cn } from '@/lib/utils'

type FileKind = 'pdf' | 'docx' | 'markdown' | 'image' | 'default'

const FILE_ICONS: Record<FileKind, {
  svg: React.ReactNode
  className: string
}> = {
  pdf: {
    className: 'text-accent-danger',
    svg: (
      <>
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <path d="M9 15h6" />
      </>
    ),
  },
  docx: {
    className: 'text-cat-entity',
    svg: (
      <>
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
      </>
    ),
  },
  markdown: {
    className: 'text-accent-neural',
    svg: (
      <>
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <path d="M10 13l-2 2 2 2" />
        <path d="M14 13l2 2-2 2" />
      </>
    ),
  },
  image: {
    className: 'text-accent-warm',
    svg: (
      <>
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
        <circle cx="8.5" cy="8.5" r="1.5" />
        <polyline points="21 15 16 10 5 21" />
      </>
    ),
  },
  default: {
    className: 'text-text-muted',
    svg: (
      <>
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
      </>
    ),
  },
}

function resolveKind(ext: string, mime: string): FileKind {
  if (ext === '.pdf') return 'pdf'
  if (ext === '.docx') return 'docx'
  if (['.md', '.markdown'].includes(ext)) return 'markdown'
  if (['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'].includes(ext) || mime?.startsWith('image/')) return 'image'
  return 'default'
}

// ── Public API ────────────────────────────────────────────────

export function FileIcon({ ext, mime, size = 'sm' }: { ext: string; mime?: string; size?: 'xs' | 'sm' | 'md' }) {
  const kind = resolveKind(ext, mime || '')
  const { svg, className } = FILE_ICONS[kind]

  const sizes = {
    xs: 'w-3.5 h-3.5',
    sm: 'w-4 h-4',
    md: 'w-5 h-5',
  }

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn(sizes[size], className)}
    >
      {svg}
    </svg>
  )
}
