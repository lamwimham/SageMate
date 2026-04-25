import { useState, useRef, useCallback, useEffect } from 'react'
import { useWikiTabsStore, type WikiTab } from '@/stores/wikiTabs'
import { useNoteContentStore } from '@/stores/noteContent'

/**
 * Wiki Tab Bar — 浏览器风格标签栏
 * - 固定高度，横向滚动
 * - 右侧 + 按钮新建笔记
 * - 页签多时显示 "关闭全部" 按钮
 * - 双击任何标签标题可内联编辑
 * - 关闭时检查未保存状态
 */
export function WikiTabBar() {
  const { tabs, activeKey, activateTab, closeTab, closeAll, openNote, openOverview, isDirty, updateTabTitle } = useWikiTabsStore()
  const [showCloseConfirm, setShowCloseConfirm] = useState<string | null>(null)
  const [showCloseAllConfirm, setShowCloseAllConfirm] = useState(false)
  const [editingKey, setEditingKey] = useState<string | null>(null)
  const [editingTitle, setEditingTitle] = useState('')
  const editRef = useRef<HTMLInputElement>(null)
  const focusTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleTabClick = (tab: WikiTab) => {
    activateTab(tab.key)
  }

  const handleTabDoubleClick = (tab: WikiTab) => {
    // Allow renaming all tab types
    setEditingKey(tab.key)
    setEditingTitle(tab.title)
    if (focusTimerRef.current) clearTimeout(focusTimerRef.current)
    focusTimerRef.current = setTimeout(() => editRef.current?.focus(), 0)
  }

  useEffect(() => {
    return () => {
      if (focusTimerRef.current) clearTimeout(focusTimerRef.current)
    }
  }, [])

  const handleEditCommit = useCallback(() => {
    if (editingKey && editingTitle.trim()) {
      updateTabTitle(editingKey, editingTitle.trim())
    }
    setEditingKey(null)
    setEditingTitle('')
  }, [editingKey, editingTitle, updateTabTitle])

  const handleEditKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleEditCommit()
    }
    if (e.key === 'Escape') {
      setEditingKey(null)
      setEditingTitle('')
    }
  }

  const handleClose = (e: React.MouseEvent, key: string) => {
    e.stopPropagation()
    if (isDirty(key)) {
      setShowCloseConfirm(key)
    } else {
      closeTab(key)
    }
  }

  const handleForceClose = (key: string) => {
    const { unregisterDirty } = useWikiTabsStore.getState()
    useNoteContentStore.getState().clearContent(key)
    unregisterDirty(key)
    closeTab(key)
    setShowCloseConfirm(null)
  }

  const handleCloseAll = () => {
    const dirtyKeys = closeAll()
    if (dirtyKeys.length > 0) {
      setShowCloseAllConfirm(true)
    }
  }

  const handleForceCloseAll = () => {
    const { tabs: allTabs, unregisterDirty } = useWikiTabsStore.getState()
    const noteStore = useNoteContentStore.getState()
    for (const tab of allTabs) {
      unregisterDirty(tab.key)
      noteStore.clearContent(tab.key)
    }
    closeAll()
    setShowCloseAllConfirm(false)
  }

  const showCloseAllBtn = tabs.length >= 3

  if (tabs.length === 0) {
    return (
      <div className="tab-bar bg-bg-surface border-b border-border-subtle">
        <div className="tab-bar__actions">
          <button onClick={openOverview} className="tab-bar__icon-btn" title="打开概览">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
              <line x1="3" y1="9" x2="21" y2="9" />
              <line x1="9" y1="21" x2="9" y2="9" />
            </svg>
          </button>
          <button onClick={openNote} className="tab-bar__icon-btn tab-bar__add-btn" title="新建笔记">
            +
          </button>
        </div>
        <div className="tab-bar__rail" />

        {showCloseAllConfirm && (
          <CloseAllConfirmModal
            onForceClose={handleForceCloseAll}
            onCancel={() => setShowCloseAllConfirm(false)}
          />
        )}
      </div>
    )
  }

  return (
    <div className="tab-bar bg-bg-surface border-b border-border-subtle">
      <div className="tab-bar__rail" />
      {tabs.map((tab) => {
        const isActive = tab.key === activeKey
        const dirty = isDirty(tab.key)
        const isEditing = editingKey === tab.key

        return (
          <button
            key={tab.key}
            onClick={() => handleTabClick(tab)}
            onDoubleClick={() => handleTabDoubleClick(tab)}
            className={`browser-tab${isActive ? ' browser-tab--active' : ''}`}
            title="双击重命名"
          >
            {isEditing ? (
              <input
                ref={editRef}
                value={editingTitle}
                onChange={(e) => setEditingTitle(e.target.value)}
                onBlur={handleEditCommit}
                onKeyDown={handleEditKeyDown}
                className="browser-tab__title-input"
                onClick={(e) => e.stopPropagation()}
              />
            ) : (
              <span className="browser-tab__title">{tab.title || ' '}</span>
            )}

            {dirty && !isEditing && <span className="browser-tab__dirty-dot" title="未保存" />}
            <span
              onClick={(e) => handleClose(e, tab.key)}
              className="browser-tab__close"
            >
              ×
            </span>
          </button>
        )
      })}

      {/* Right side actions */}
      <div className="tab-bar__actions">
        <button onClick={openNote} className="tab-bar__icon-btn tab-bar__add-btn" title="新建笔记">
          +
        </button>
        {showCloseAllBtn && (
          <button onClick={handleCloseAll} className="tab-bar__icon-btn" title="关闭全部">
            ×
          </button>
        )}
      </div>

      {/* Single tab close confirmation */}
      {showCloseConfirm && (
        <CloseConfirmModal
          tabTitle={tabs.find((t) => t.key === showCloseConfirm)?.title || ''}
          onForceClose={() => handleForceClose(showCloseConfirm)}
          onCancel={() => setShowCloseConfirm(null)}
        />
      )}

      {/* Close all confirmation */}
      {showCloseAllConfirm && (
        <CloseAllConfirmModal
          onForceClose={handleForceCloseAll}
          onCancel={() => setShowCloseAllConfirm(false)}
        />
      )}
    </div>
  )
}

function CloseConfirmModal({ tabTitle, onForceClose, onCancel }: {
  tabTitle: string
  onForceClose: () => void
  onCancel: () => void
}) {
  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        <p className="modal-text">
          "<span className="modal-highlight">{tabTitle}</span>" 尚未保存，确定关闭吗？
        </p>
        <div className="modal-actions">
          <button className="modal-btn modal-btn--cancel" onClick={onCancel}>取消</button>
          <button className="modal-btn modal-btn--danger" onClick={onForceClose}>关闭</button>
        </div>
      </div>
    </div>
  )
}

function CloseAllConfirmModal({ onForceClose, onCancel }: {
  onForceClose: () => void
  onCancel: () => void
}) {
  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        <p className="modal-text">
          有<span className="modal-highlight">未保存</span>的标签页，确定关闭全部吗？
        </p>
        <div className="modal-actions">
          <button className="modal-btn modal-btn--cancel" onClick={onCancel}>取消</button>
          <button className="modal-btn modal-btn--danger" onClick={onForceClose}>关闭全部</button>
        </div>
      </div>
    </div>
  )
}
