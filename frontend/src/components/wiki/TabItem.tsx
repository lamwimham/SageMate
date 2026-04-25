import { useRef, useState, useEffect } from 'react'
import type { WikiTab } from '@/stores/wikiTabs'

interface TabItemProps {
  tab: WikiTab
  isActive: boolean
  isDirty: boolean
  onClick: (tab: WikiTab) => void
  onClose: (e: React.MouseEvent, key: string) => void
  onAuxClick: (e: React.MouseEvent, key: string) => void
  onContextMenu: (e: React.MouseEvent, tab: WikiTab) => void
  onRename: (key: string, newTitle: string) => void
}

/**
 * TabItem — 单个标签组件
 * 职责：
 * - 点击激活、中键关闭、右键菜单
 * - 双击内联重命名
 * - 未保存状态指示（圆点）
 */
export function TabItem({
  tab,
  isActive,
  isDirty,
  onClick,
  onClose,
  onAuxClick,
  onContextMenu,
  onRename,
}: TabItemProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editTitle, setEditTitle] = useState(tab.title)
  const inputRef = useRef<HTMLInputElement>(null)
  const focusTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Sync edit title when tab changes
  useEffect(() => {
    setEditTitle(tab.title)
  }, [tab.title, tab.key])

  const handleDoubleClick = () => {
    setIsEditing(true)
    setEditTitle(tab.title)
    if (focusTimerRef.current) clearTimeout(focusTimerRef.current)
    focusTimerRef.current = setTimeout(() => inputRef.current?.focus(), 0)
  }

  const handleEditCommit = () => {
    const trimmed = editTitle.trim()
    if (trimmed && trimmed !== tab.title) {
      onRename(tab.key, trimmed)
    }
    setIsEditing(false)
    setEditTitle(tab.title)
  }

  const handleEditKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleEditCommit()
    }
    if (e.key === 'Escape') {
      setIsEditing(false)
      setEditTitle(tab.title)
    }
  }

  useEffect(() => {
    return () => {
      if (focusTimerRef.current) clearTimeout(focusTimerRef.current)
    }
  }, [])

  return (
    <button
      className={`browser-tab${isActive ? ' browser-tab--active' : ''}`}
      onClick={() => onClick(tab)}
      onDoubleClick={handleDoubleClick}
      onAuxClick={(e) => onAuxClick(e, tab.key)}
      onContextMenu={(e) => onContextMenu(e, tab)}
      title="双击重命名 · 中键关闭"
    >
      {isEditing ? (
        <input
          ref={inputRef}
          value={editTitle}
          onChange={(e) => setEditTitle(e.target.value)}
          onBlur={handleEditCommit}
          onKeyDown={handleEditKeyDown}
          className="browser-tab__title-input"
          onClick={(e) => e.stopPropagation()}
        />
      ) : (
        <span className="browser-tab__title">{tab.title || ' '}</span>
      )}

      {isDirty && !isEditing && <span className="browser-tab__dirty-dot" title="未保存" />}
      <span
        onClick={(e) => onClose(e, tab.key)}
        className="browser-tab__close"
      >
        ×
      </span>
    </button>
  )
}
