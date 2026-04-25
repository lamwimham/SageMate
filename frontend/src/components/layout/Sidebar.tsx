import { useLayoutContext } from '@/layout/LayoutContext'

/**
 * Sidebar 容器 — 只负责渲染，内容由各页面通过 usePageLayout 声明
 * 新增页面无需修改此文件
 */
export function Sidebar() {
  const { sidebarContent } = useLayoutContext()

  return (
    <aside className="bg-bg-surface border-r border-border-subtle overflow-hidden flex flex-col" aria-label="侧边栏">
      {sidebarContent ?? (
        <div className="flex-1 flex flex-col items-center justify-center p-6">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-8 h-8 mb-2 opacity-40 text-text-muted">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
          </svg>
          <p className="text-xs text-text-muted text-center">此页面无边栏内容</p>
        </div>
      )}
    </aside>
  )
}
