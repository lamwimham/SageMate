import { useLayoutStore } from '@/stores/layout'
import { ProjectSwitcher } from './ProjectSwitcher'
import { cn } from '@/lib/utils'

export function TopBar() {
  const { sidebarOpen, detailOpen, toggleSidebar, toggleDetail } = useLayoutStore()

  return (
    <header className="h-9 bg-bg-void flex items-center px-3 gap-3 shrink-0">
      {/* Spacer — left */}
      <div className="flex-1" />

      {/* Project Switcher — centered */}
      <ProjectSwitcher />

      {/* Spacer — right */}
      <div className="flex-1" />

      {/* Layout Controls */}
      <LayoutControls
        sidebarOpen={sidebarOpen}
        detailOpen={detailOpen}
        onToggleSidebar={toggleSidebar}
        onToggleDetail={toggleDetail}
      />
    </header>
  )
}

function LayoutControls({
  sidebarOpen,
  detailOpen,
  onToggleSidebar,
  onToggleDetail,
}: {
  sidebarOpen: boolean
  detailOpen: boolean
  onToggleSidebar: () => void
  onToggleDetail: () => void
}) {
  return (
    <div className="flex items-center gap-1">
      <button
        onClick={onToggleSidebar}
        className={cn(
          'w-7 h-7 flex items-center justify-center rounded-md transition-all duration-200 cursor-pointer',
          sidebarOpen ? 'text-accent-neural bg-accent-neural/10' : 'text-text-muted hover:text-text-secondary hover:bg-bg-elevated/50'
        )}
        title="切换侧边栏"
        aria-label="切换侧边栏"
      >
        <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
          <rect x="1" y="1" width="14" height="14" rx="2" />
          <line x1="5" y1="1" x2="5" y2="15" />
        </svg>
      </button>

      <button
        onClick={onToggleDetail}
        className={cn(
          'w-7 h-7 flex items-center justify-center rounded-md transition-all duration-200 cursor-pointer',
          detailOpen ? 'text-accent-neural bg-accent-neural/10' : 'text-text-muted hover:text-text-secondary hover:bg-bg-elevated/50'
        )}
        title="切换详情面板"
        aria-label="切换详情面板"
      >
        <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
          <rect x="1" y="1" width="14" height="14" rx="2" />
          <line x1="11" y1="1" x2="11" y2="15" />
        </svg>
      </button>
    </div>
  )
}
