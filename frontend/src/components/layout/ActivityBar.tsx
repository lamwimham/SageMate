import { Link, useLocation } from '@tanstack/react-router'
import { cn } from '@/lib/utils'

interface NavItem {
  id: string
  path: string
  icon: string
  label: string
}

// Top section nav items
const TOP_ITEMS: NavItem[] = [
  { id: 'wiki', path: '/wiki', icon: 'M4 3h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zM8 7h6M8 10h6M5 7h.01M5 10h.01', label: '知识库' },
  { id: 'ingest', path: '/ingest', icon: 'M12 5v12M5 12h14', label: '摄入' },
  { id: 'raw', path: '/raw', icon: 'M14 2H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M8 13h8M8 17h8M8 9h2', label: '原始' },
  { id: 'status', path: '/status', icon: 'M22 12h-4l-3 9L9 3l-3 9H2', label: '状态' },
]

// Bottom section nav items (pinned to bottom)
const BOTTOM_ITEMS: NavItem[] = [
  { id: 'settings', path: '/settings', icon: 'M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z', label: '设置' },
]

function NavIcon({ item, isActive }: { item: NavItem; isActive: boolean }) {
  return (
    <Link
      to={item.path}
      className={cn(
        'w-10 h-10 flex items-center justify-center rounded-lg transition-all duration-150 cursor-pointer group relative',
        isActive
          ? 'text-text-primary bg-bg-elevated'
          : 'text-text-muted hover:text-text-secondary hover:bg-bg-elevated/50'
      )}
      aria-label={item.label}
      title={item.label}
    >
      <svg
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d={item.icon} />
      </svg>
      {/* Active indicator */}
      {isActive && (
        <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-accent-primary" />
      )}
      {/* Tooltip */}
      <div className="absolute left-full ml-2 px-2 py-1 bg-bg-elevated border border-border-subtle rounded-md text-xs text-text-primary whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition z-50 shadow-lg">
        {item.label}
      </div>
    </Link>
  )
}

export function ActivityBar() {
  const location = useLocation()

  return (
    <aside
      className="flex flex-col items-center bg-bg-void border-r border-border-subtle py-2 z-20 overflow-hidden"
      aria-label="活动栏"
    >
      {/* Top nav items */}
      <div className="flex flex-col items-center gap-1 w-full">
        {TOP_ITEMS.map((item) => (
          <NavIcon key={item.id} item={item} isActive={location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path))} />
        ))}
      </div>

      {/* Spacer pushes bottom items down */}
      <div className="flex-1" />

      {/* Bottom nav items */}
      <div className="flex flex-col items-center gap-1 pt-2 border-t border-border-subtle/30 w-full">
        {BOTTOM_ITEMS.map((item) => (
          <NavIcon key={item.id} item={item} isActive={location.pathname === item.path} />
        ))}
      </div>
    </aside>
  )
}
