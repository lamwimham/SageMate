import { CompileTaskSidebar } from './CompileTaskSidebar'

export function BottomPanel() {
  return (
    <aside
      className="overflow-hidden flex flex-col h-full"
      aria-label="底部面板"
    >
      <CompileTaskSidebar />
    </aside>
  )
}
