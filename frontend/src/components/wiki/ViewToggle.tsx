import { cn } from '@/lib/utils'

interface ViewToggleProps {
  mode: 'edit' | 'preview'
  onToggle: () => void
  className?: string
}

/**
 * 编辑/预览 切换按钮
 * 交互：纯图标，hover 显示提示文字
 */
export function ViewToggle({ mode, onToggle, className }: ViewToggleProps) {
  return (
    <div className={cn('group relative', className)}>
      <button
        onClick={onToggle}
        className="p-1.5 rounded-md text-text-muted hover:text-accent-neural hover:bg-bg-hover transition cursor-pointer"
        aria-label={mode === 'edit' ? '切换预览' : '切换编辑'}
      >
        {mode === 'edit' ? (
          // 预览图标（眼睛）
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
            <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        ) : (
          // 编辑图标（铅笔）
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
            <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
            <path d="m15 5 4 4" />
          </svg>
        )}
      </button>
      {/* Hover Tooltip */}
      <div className="absolute right-0 top-full mt-1 px-2 py-1 text-[10px] bg-bg-elevated border border-border-subtle rounded shadow-sm whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition text-text-muted z-50">
        {mode === 'edit' ? '切换预览' : '切换编辑'}
      </div>
    </div>
  )
}
