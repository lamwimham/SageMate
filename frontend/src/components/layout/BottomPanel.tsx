import { useLayoutStore } from '@/stores/layout'

export function BottomPanel() {
  const { bottomOpen } = useLayoutStore()

  if (!bottomOpen) return null

  return (
    <aside
      className="bg-bg-surface border-t border-border-subtle overflow-hidden"
      aria-label="底部面板"
    >
      <div className="p-4 text-text-muted text-sm">
        Bottom panel content goes here
      </div>
    </aside>
  )
}
