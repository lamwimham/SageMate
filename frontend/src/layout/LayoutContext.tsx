import { createContext, useContext, useState, type ReactNode } from 'react'

export interface LayoutContextValue {
  /** Sidebar 内容 — 页面自己声明 */
  sidebarContent: ReactNode | null
  /** DetailPanel 内容 — 页面自己声明 */
  detailPanelContent: ReactNode | null
  setSidebarContent: (v: ReactNode | null) => void
  setDetailPanelContent: (v: ReactNode | null) => void
}

const LayoutContext = createContext<LayoutContextValue | null>(null)

export function LayoutProvider({ children }: { children: ReactNode }) {
  const [sidebarContent, setSidebarContent] = useState<ReactNode | null>(null)
  const [detailPanelContent, setDetailPanelContent] = useState<ReactNode | null>(null)

  return (
    <LayoutContext.Provider
      value={{
        sidebarContent,
        detailPanelContent,
        setSidebarContent,
        setDetailPanelContent,
      }}
    >
      {children}
    </LayoutContext.Provider>
  )
}

export function useLayoutContext() {
  const ctx = useContext(LayoutContext)
  if (!ctx) throw new Error('useLayoutContext must be used within LayoutProvider')
  return ctx
}
