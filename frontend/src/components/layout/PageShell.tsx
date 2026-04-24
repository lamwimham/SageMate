import type { ReactNode } from 'react'
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
        gridTemplateRows: 'auto 1fr' + (bottomOpen ? ' 200px' : ''),
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
        <main className="bg-bg-deep overflow-hidden flex flex-col min-h-0">
          {children}
        </main>
        {showDetail && <DetailPanel />}
      </div>

      {/* Row 3, Col 1-2: Bottom Panel (spans all) */}
      {bottomOpen && <div className="col-span-2"><BottomPanel /></div>}
    </div>
  )
}
