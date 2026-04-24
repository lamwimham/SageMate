import { useEffect, type ReactNode } from 'react'
import { useLayoutContext } from '@/layout/LayoutContext'

interface PageLayoutConfig {
  sidebar?: ReactNode
  detailPanel?: ReactNode
}

/**
 * 页面级 Layout 注册 Hook
 * 使用方式：在页面组件顶层调用，声明该页面需要的 Sidebar 和 DetailPanel
 * 切换页面时会自动清理上一个页面的 layout
 */
export function usePageLayout(config: PageLayoutConfig) {
  const { setSidebarContent, setDetailPanelContent } = useLayoutContext()

  useEffect(() => {
    setSidebarContent(config.sidebar ?? null)
    setDetailPanelContent(config.detailPanel ?? null)

    return () => {
      setSidebarContent(null)
      setDetailPanelContent(null)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
}
