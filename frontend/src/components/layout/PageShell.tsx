import type { ReactNode, useRef, useState, useCallback, useEffect } from 'react'
import { cn } from '@/lib/utils'
import { useLayoutContext } from '@/layout/LayoutContext'
import { useLayoutStore } from '@/stores/layout'
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts'
import { TopBar } from './TopBar'
import { ActivityBar } from './ActivityBar'
import { Sidebar } from './Sidebar'
import { DetailPanel } from './DetailPanel'
import { BottomPanel } from './BottomPanel'

/** Resizable panel handle — invisible hit area that expands on hover */
function ResizeHandle({
  onResize,
  min = 180,
  max = 500,
  direction = 'horizontal',
}: {
  onResize: (delta: number) => void
  min?: number
  max?: number
  direction?: 'horizontal' | 'vertical'
}) {
  const [isDragging, setIsDragging] = useState(false)
  const startPosRef = useRef(0)

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsDragging(true)
    startPosRef.current = direction === 'horizontal' ? e.clientX : e.clientY
  }, [direction])

  useEffect(() => {
    if (!isDragging) return
    const handleMouseMove = (e: MouseEvent) => {
      const current = direction === 'horizontal' ? e.clientX : e.clientY
      const delta = current - startPosRef.current
      startPosRef.current = current
      onResize(delta)
    }
    const handleMouseUp = () => setIsDragging(false)
    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging, direction, onResize])

  const isHorizontal = direction === 'horizontal'

  return (
    <div
      className={cn(
        'group relative z-50 flex items-center justify-center',
        isHorizontal
          ? 'w-[4px] -mx-[2px] cursor-col-resize hover:w-[12px] hover:-mx-[6px]'
          : 'h-[4px] -my-[2px] cursor-row-resize hover:h-[12px] hover:-my-[6px]',
        'transition-all duration-150 ease-out',
        isDragging && (isHorizontal ? 'w-[12px] -mx-[6px]' : 'h-[12px] -my-[6px]')
      )}
      onMouseDown={handleMouseDown}
    >
      {/* Visual indicator line — visible on hover/drag */}
      <div
        className={cn(
          'rounded-full transition-opacity duration-150',
          isHorizontal ? 'h-8 w-[2px]' : 'w-8 h-[2px]',
          'bg-accent-neural/0 group-hover:bg-accent-neural/40',
          isDragging && 'bg-accent-neural/60'
        )}
      />
    </div>
  )
}

export function PageShell({ children }: { children: ReactNode }) {
  useKeyboardShortcuts()
  const { sidebarOpen, detailOpen, bottomOpen } = useLayoutStore()
  const { detailPanelContent } = useLayoutContext()

  // 只有当用户打开 detail 且当前页面注册了 detail 内容时才显示
  const showDetail = detailOpen && !!detailPanelContent

  // Resizable widths (px)
  const [sidebarWidth, setSidebarWidth] = useState(260)
  const [detailWidth, setDetailWidth] = useState(300)
  const [bottomHeight, setBottomHeight] = useState(200)

  const handleSidebarResize = useCallback((delta: number) => {
    setSidebarWidth((w) => Math.max(180, Math.min(500, w + delta)))
  }, [])

  const handleDetailResize = useCallback((delta: number) => {
    setDetailWidth((w) => Math.max(180, Math.min(500, w - delta)))
  }, [])

  const handleBottomResize = useCallback((delta: number) => {
    setBottomHeight((h) => Math.max(120, Math.min(600, h - delta)))
  }, [])

  return (
    <div
      className="h-screen overflow-hidden"
      style={{
        display: 'grid',
        gridTemplateColumns: '48px 1fr',
        gridTemplateRows: 'auto 1fr' + (bottomOpen ? ` ${bottomHeight}px` : ''),
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
              ? `${sidebarWidth}px 1fr ${detailWidth}px`
              : `${sidebarWidth}px 1fr`
            : showDetail
              ? `1fr ${detailWidth}px`
              : '1fr',
          transition: 'grid-template-columns 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        {sidebarOpen && (
          <>
            <Sidebar />
            {showDetail && <ResizeHandle onResize={handleSidebarResize} />}
          </>
        )}
        <main className={cn('overflow-hidden flex flex-col min-h-0', 'bg-bg-deep')}>
          {children}
        </main>
        {showDetail && (
          <>
            <ResizeHandle onResize={handleDetailResize} />
            <DetailPanel />
          </>
        )}
      </div>

      {/* Row 3, Col 1-2: Bottom Panel (spans all) */}
      {bottomOpen && (
        <div className="col-span-2" style={{ display: 'grid', gridTemplateRows: '1fr' }}>
          <div style={{ position: 'relative' }}>
            <ResizeHandle direction="vertical" onResize={handleBottomResize} />
            <BottomPanel />
          </div>
        </div>
      )}
    </div>
  )
}
