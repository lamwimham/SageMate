import { useEffect, useRef } from 'react'
import type { WikiTab } from '@/stores/wikiTabs'

interface TabContextMenuProps {
  tab: WikiTab
  tabIndex: number
  totalTabs: number
  x: number
  y: number
  onClose: () => void
  onCloseTab: () => void
  onCloseOther: () => void
  onCloseLeft: () => void
  onCloseRight: () => void
  onRestore?: () => void
  canRestore: boolean
}

/**
 * TabContextMenu — 标签右键菜单
 * 支持操作：关闭、关闭其他、关闭左侧、关闭右侧、恢复最近关闭
 */
export function TabContextMenu({
  tab,
  tabIndex,
  totalTabs,
  x,
  y,
  onClose,
  onCloseTab,
  onCloseOther,
  onCloseLeft,
  onCloseRight,
  onRestore,
  canRestore,
}: TabContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null)

  // Adjust position if menu would go off-screen
  useEffect(() => {
    const menu = menuRef.current
    if (!menu) return
    const rect = menu.getBoundingClientRect()
    const adjustedX = x + rect.width > window.innerWidth ? x - rect.width : x
    const adjustedY = y + rect.height > window.innerHeight ? y - rect.height : y
    menu.style.left = `${adjustedX}px`
    menu.style.top = `${adjustedY}px`
  }, [x, y])

  // Close on outside click or Escape
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    const keyHandler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('mousedown', handler)
    document.addEventListener('keydown', keyHandler)
    return () => {
      document.removeEventListener('mousedown', handler)
      document.removeEventListener('keydown', keyHandler)
    }
  }, [onClose])

  const MenuItem = ({
    label,
    shortcut,
    onClick,
    disabled = false,
    danger = false,
  }: {
    label: string
    shortcut?: string
    onClick: () => void
    disabled?: boolean
    danger?: boolean
  }) => (
    <button
      className={`context-menu-item${danger ? ' context-menu-item--danger' : ''}`}
      onClick={onClick}
      disabled={disabled}
    >
      <span>{label}</span>
      {shortcut && <span className="context-menu-item__shortcut">{shortcut}</span>}
    </button>
  )

  return (
    <div
      ref={menuRef}
      className="context-menu"
      style={{ position: 'fixed', zIndex: 1000 }}
    >
      <MenuItem
        label="关闭标签"
        shortcut="Cmd+W"
        onClick={onCloseTab}
        danger
      />
      {totalTabs > 1 && (
        <MenuItem
          label="关闭其他"
          onClick={onCloseOther}
          disabled={totalTabs === 1}
        />
      )}
      {tabIndex > 0 && (
        <MenuItem
          label="关闭左侧"
          onClick={onCloseLeft}
          disabled={tabIndex === 0}
        />
      )}
      {tabIndex < totalTabs - 1 && (
        <MenuItem
          label="关闭右侧"
          onClick={onCloseRight}
          disabled={tabIndex >= totalTabs - 1}
        />
      )}

      <div className="context-menu-divider" />

      {canRestore && (
        <MenuItem
          label="恢复最近关闭"
          shortcut="Cmd+Shift+T"
          onClick={onRestore!}
        />
      )}
    </div>
  )
}
