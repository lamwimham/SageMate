import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { useLayoutContext } from '@/layout/LayoutContext'
import { useLayoutStore } from '@/stores/layout'
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts'
import { TopBar } from './TopBar'
import { ActivityBar } from './ActivityBar'
import { Sidebar } from './Sidebar'
import { DetailPanel } from './DetailPanel'
import { BottomPanel } from './BottomPanel'

export function PageShell({ children }: { children: ReactNode }) {
  useKeyboardShortcuts()
  const { sidebarOpen, detailOpen, bottomOpen } = useLayoutStore()
  const { detailPanelContent } = useLayoutContext()

  // 只有当用户打开 detail 且当前页面注册了 detail 内容时才显示
  const showDetail = detailOpen && !!detailPanelContent

  return (
    <div
      className="h-screen overflow-hidden"
      style={{
        display: 'grid',
        gridTemplateColumns: '48px 1fr',
        gridTemplateRows: 'auto 1fr',
      }}
    >
      {/* Row 1, Col 1-2: TopBar (spans all) */}
      <div className="col-span-2">
        <TopBar />
      </div>

      {/* Row 2, Col 1: Activity Bar */}
      <ActivityBar />

      {/* Row 2, Col 2: Inner workspace (Sidebar + Main + Detail) */}
      <div
        className="overflow-hidden"
        style={{
          display: 'grid',
          gridTemplateColumns: sidebarOpen
            ? showDetail
              ? '260px 1fr 300px'
              : '260px 1fr'
            : showDetail
              ? '1fr 300px'
              : '1fr',
          transition: 'grid-template-columns 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        {sidebarOpen && <Sidebar />}

        {/* Main: flex column with content + bottom panel */}
        <main className={cn('overflow-hidden flex flex-col min-h-0', 'bg-bg-deep')}>
          {/* Content area — flexes to fill available space */}
          <div className="flex-1 min-h-0 overflow-hidden" style={{ display: 'flex', flexDirection: 'column' }}>
            {children}
          </div>

          {/* Bottom panel — sits inside main, only occupies its own height */}
          {bottomOpen && (
            <div
              className="border-t border-border-subtle bg-bg-surface flex-shrink-0"
              style={{ height: '200px' }}
            >
              <BottomPanel />
            </div>
          )}
        </main>

        {showDetail && <DetailPanel />}
      </div>
    </div>
  )
}
