import { useThemeStore } from '@/stores/theme'
import { cn } from '@/lib/utils'

export function ThemeToggle({ className }: { className?: string }) {
  const { mode, resolved, setMode } = useThemeStore()

  return (
    <div className={cn('flex items-center justify-between p-3 rounded-xl bg-bg-elevated/50 border border-border-subtle/60', className)}>
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg flex items-center justify-center bg-accent-neural/8 border border-accent-neural/15">
          {resolved === 'dark' ? (
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 text-accent-neural">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          ) : (
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 text-accent-growth">
              <circle cx="12" cy="12" r="5" />
              <line x1="12" y1="1" x2="12" y2="3" />
              <line x1="12" y1="21" x2="12" y2="23" />
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
              <line x1="1" y1="12" x2="3" y2="12" />
              <line x1="21" y1="12" x2="23" y2="12" />
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
            </svg>
          )}
        </div>
        <div>
          <div className="text-sm font-medium text-text-primary">
            {resolved === 'dark' ? '深色模式' : '浅色模式'}
          </div>
          <div className="text-xs text-text-muted">
            当前: {mode === 'system' ? '跟随系统' : mode === 'dark' ? '深色' : '浅色'}
          </div>
        </div>
      </div>
      <button
        onClick={() => setMode(resolved === 'dark' ? 'light' : 'dark')}
        className="px-3 py-1.5 text-xs font-medium rounded-lg bg-accent-neural/10 text-accent-neural hover:bg-accent-neural/15 transition cursor-pointer"
      >
        {resolved === 'dark' ? '切换浅色' : '切换深色'}
      </button>
    </div>
  )
}
