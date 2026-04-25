import { useState, useRef, useCallback, useEffect } from 'react'
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

/** Resizable bottom panel with drag handle */
function BottomPanelContainer({ bottomOpen }: { bottomOpen: boolean }) {
  const [height, setHeight] = useState(200)
  const [isDragging, setIsDragging] = useState(false)
  const startPosRef = useRef(0)
  const startHeightRef = useRef(0)

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsDragging(true)
    startPosRef.current = e.clientY
    startHeightRef.current = height
  }, [height])

  useEffect(() => {
    if (!isDragging) return
    const handleMouseMove = (e: MouseEvent) => {
      const delta = startPosRef.current - e.clientY // drag up = increase height
      const newHeight = Math.max(120, Math.min(600, startHeightRef.current + delta))
      setHeight(newHeight)
    }
    const handleMouseUp = () => setIsDragging(false)
    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging])

  if (!bottomOpen) return null

  return (
    <div
      className="border-t border-border-subtle flex flex-col bg-bg-surface"
      style={{ height: `${height}px`, flexShrink: 0 }}
    >
      {/* Drag handle */}
      <div
        className={cn(
          'group relative h-[4px] -mt-[4px] cursor-row-resize flex items-center justify-center',
          'hover:h-[8px] hover:-mt-[8px] transition-all duration-150 ease-out',
          isDragging && 'h-[8px] -mt-[8px]'
        )}
        onMouseDown={handleMouseDown}
      >
        {/* Visual indicator */}
        <div
          className={cn(
            'w-12 h-[2px] rounded-full transition-colors duration-150',
            'bg-text-muted/0 group-hover:bg-text-muted/40',
            isDragging && 'bg-text-muted/60'
          )}
        />
      </div>

      {/* Panel content */}
      <div className="flex-1 min-h-0 overflow-hidden">
        <BottomPanel />
      </div>
    </div>
  )
}

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
          <div className="flex-1 min-h-0 overflow-hidden">
            {children}
          </div>

          {/* Bottom panel — sits inside main, only occupies its own height */}
          <BottomPanelContainer bottomOpen={bottomOpen} />
        </main>

        {showDetail && <DetailPanel />}
      </div>
    </div>
  )
}
