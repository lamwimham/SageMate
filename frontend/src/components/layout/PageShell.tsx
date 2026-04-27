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
import logoUrl from '@/assets/logo_sagemate.svg'

/** Resize handle for DetailPanel */
function DetailResizeHandle({ width, onResize, onResizeStart, onResizeEnd, style }: { width: number; onResize: (w: number) => void; onResizeStart?: () => void; onResizeEnd?: () => void; style?: React.CSSProperties }) {
  const isDragging = useRef(false)
  const startX = useRef(0)
  const startW = useRef(0)

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    isDragging.current = true
    startX.current = e.clientX
    startW.current = width
    onResizeStart?.()
    e.preventDefault()
  }, [width, onResizeStart])

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.current) return
      const delta = startX.current - e.clientX // drag left = increase width
      const newW = Math.max(180, Math.min(500, startW.current + delta))
      onResize(newW)
    }
    const handleMouseUp = () => {
      if (isDragging.current) {
        isDragging.current = false
        onResizeEnd?.()
      }
    }
    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [onResize, onResizeEnd])

  return (
    <div
      className="absolute top-0 bottom-0 z-50 w-[6px] -ml-[3px] cursor-col-resize group flex items-center justify-center"
      onMouseDown={handleMouseDown}
      style={style}
    >
      <div className="w-[2px] h-8 rounded-full transition-colors bg-text-muted/0 group-hover:bg-text-muted/50" />
    </div>
  )
}

export function PageShell({ children }: { children: ReactNode }) {
  useKeyboardShortcuts()
  const { sidebarOpen, detailOpen, bottomOpen } = useLayoutStore()
  const { detailPanelContent } = useLayoutContext()

  // Detail panel width state
  const [detailWidth, setDetailWidth] = useState(300)
  const [isResizing, setIsResizing] = useState(false)

  const handleDetailResize = useCallback((w: number) => {
    setDetailWidth(w)
  }, [])

  const handleResizeStart = useCallback(() => {
    setIsResizing(true)
  }, [])

  const handleResizeEnd = useCallback(() => {
    setIsResizing(false)
  }, [])

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
        className="relative overflow-hidden"
        style={{
          display: 'grid',
          gridTemplateColumns: sidebarOpen
            ? showDetail
              ? `260px 1fr ${detailWidth}px`
              : '260px 1fr'
            : showDetail
              ? `1fr ${detailWidth}px`
              : '1fr',
          transition: isResizing ? 'none' : 'grid-template-columns 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        {sidebarOpen && <Sidebar />}

        {/* Main: flex column with content + bottom panel */}
        <main className={cn('overflow-hidden flex flex-col min-h-0 relative', 'bg-bg-deep')}>
          {/* Background logo watermark */}
          <div
            className="absolute inset-0 pointer-events-none z-0"
            style={{
              backgroundImage: `url(${logoUrl})`,
              backgroundRepeat: 'no-repeat',
              backgroundPosition: 'center',
              backgroundSize: '240px auto',
              opacity: 0.2,
            }}
          />
          {/* Content area — flexes to fill available space */}
          <div className="flex-1 min-h-0 overflow-hidden relative z-10" style={{ display: 'flex', flexDirection: 'column' }}>
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

        {/* Detail Panel Resize Handle */}
        {showDetail && (
          <DetailResizeHandle
            width={detailWidth}
            onResize={handleDetailResize}
            onResizeStart={handleResizeStart}
            onResizeEnd={handleResizeEnd}
            style={{ right: `${detailWidth}px` }}
          />
        )}

        {showDetail && <DetailPanel />}
      </div>
    </div>
  )
}
