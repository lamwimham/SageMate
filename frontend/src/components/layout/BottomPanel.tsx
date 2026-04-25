import { CompileTaskSidebar } from './CompileTaskSidebar'

export function BottomPanel() {
  return (
    <aside
      className="bg-bg-surface border-t border-border-subtle overflow-hidden flex flex-col"
      aria-label="底部面板"
    >
      <CompileTaskSidebar />
    </aside>
  )
}
