import { useLayoutContext } from '@/layout/LayoutContext'
import { CompileTaskSidebar } from './CompileTaskSidebar'

/**
 * Sidebar 容器 — 只负责渲染，内容由各页面通过 usePageLayout 声明
 * 新增页面无需修改此文件
 */
export function Sidebar() {
  const { sidebarContent } = useLayoutContext()

  return (
    <aside className="bg-bg-surface border-r border-border-subtle overflow-hidden flex flex-col" aria-label="侧边栏">
      <div className="flex-1 overflow-y-auto min-h-0">
        {sidebarContent ?? (
          <div className="flex flex-col items-center justify-center p-6 h-full">
            <div className="text-2xl mb-2 opacity-40">📚</div>
            <p className="text-xs text-text-muted text-center">此页面无边栏内容</p>
          </div>
        )}
      </div>
      <CompileTaskSidebar />
    </aside>
  )
}
