import { useState, useRef, useCallback, useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useWikiTabsStore, type WikiTab } from '@/stores/wikiTabs'
import { useNoteContentStore } from '@/stores/noteContent'
import { invalidatePageCache } from '@/hooks/useWiki'

/**
 * Wiki Tab Bar — 浏览器风格标签栏
 * - 固定高度，横向滚动
 * - 右侧 + 按钮新建笔记
 * - 页签多时显示 "关闭全部" 按钮
 * - 双击任何标签标题可内联编辑
 * - 关闭时检查未保存状态：逐个弹窗提示（保存并关闭 / 直接关闭 / 取消）
 */
export function WikiTabBar() {
  const qc = useQueryClient()
  const { tabs, activeKey, activateTab, closeTab, closeAll, openNote, openOverview, isDirty, updateTabTitle, getSaveHandler, unregisterDirty, unregisterSaveHandler } = useWikiTabsStore()

  /** Queue of dirty tab keys waiting for user confirmation */
  const [confirmQueue, setConfirmQueue] = useState<string[]>([])
  /** Index of current tab being confirmed */
  const [confirmIndex, setConfirmIndex] = useState(0)
  /** Whether we're in the middle of a close-all sequence */
  const [isClosingAll, setIsClosingAll] = useState(false)

  const [editingKey, setEditingKey] = useState<string | null>(null)
  const [editingTitle, setEditingTitle] = useState('')
  const editRef = useRef<HTMLInputElement>(null)
  const focusTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleTabClick = (tab: WikiTab) => {
    activateTab(tab.key)
  }

  const handleTabDoubleClick = (tab: WikiTab) => {
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

  /** Close a single tab — if dirty, show confirmation modal */
  const handleClose = (e: React.MouseEvent, key: string) => {
    e.stopPropagation()
    if (isDirty(key)) {
      setConfirmQueue([key])
      setConfirmIndex(0)
      setIsClosingAll(false)
    } else {
      doClose(key)
    }
  }

  /** Actually perform close cleanup */
  const doClose = (key: string) => {
    const noteStore = useNoteContentStore.getState()
    noteStore.clearContent(key)
    unregisterSaveHandler(key)
    unregisterDirty(key)
    // 清除 React Query 缓存，释放内存
    invalidatePageCache(qc, key)
    closeTab(key)
  }

  /** Close all — build queue of dirty tabs and confirm one by one */
  const handleCloseAll = () => {
    const dirtyKeys = closeAll()
    if (dirtyKeys.length > 0) {
      setConfirmQueue(dirtyKeys)
      setConfirmIndex(0)
      setIsClosingAll(true)
    }
  }

  /** Handle "Save & Close" for current confirmation */
  const handleSaveAndClose = async () => {
    const key = confirmQueue[confirmIndex]
    const handler = getSaveHandler(key)
    if (handler) {
      try {
        await handler()
      } catch {
        // Save failed — stay on this modal, let user retry or force close
        return
      }
    }
    doClose(key)
    advanceQueue()
  }

  /** Handle "Close Without Saving" for current confirmation */
  const handleForceClose = () => {
    const key = confirmQueue[confirmIndex]
    doClose(key)
    advanceQueue()
  }

  /** Move to next item in queue, or finish */
  const advanceQueue = () => {
    const nextIndex = confirmIndex + 1
    if (nextIndex >= confirmQueue.length) {
      // All done — close remaining clean tabs if this was close-all
      if (isClosingAll) {
        const { tabs: remainingTabs } = useWikiTabsStore.getState()
        for (const tab of remainingTabs) {
          doClose(tab.key)
        }
      }
      setConfirmQueue([])
      setConfirmIndex(0)
      setIsClosingAll(false)
    } else {
      setConfirmIndex(nextIndex)
    }
  }

  /** Cancel current sequence */
  const handleCancel = () => {
    setConfirmQueue([])
    setConfirmIndex(0)
    setIsClosingAll(false)
  }

  const showCloseAllBtn = tabs.length >= 3

  // Current tab being confirmed
  const currentConfirmKey = confirmQueue[confirmIndex]
  const currentConfirmTab = currentConfirmKey ? tabs.find((t) => t.key === currentConfirmKey) : null

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
      </div>
    )
  }

  return (
    <>
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
                <span className="browser-tab__title">{tab.title || ' '}</span>
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
      </div>

      {/* Confirmation Modal — one at a time for each dirty tab */}
      {currentConfirmTab && (
        <CloseConfirmModal
          tabTitle={currentConfirmTab.title}
          currentIndex={confirmIndex + 1}
          totalCount={confirmQueue.length}
          onSaveAndClose={handleSaveAndClose}
          onForceClose={handleForceClose}
          onCancel={handleCancel}
        />
      )}
    </>
  )
}

function CloseConfirmModal({
  tabTitle,
  currentIndex,
  totalCount,
  onSaveAndClose,
  onForceClose,
  onCancel,
}: {
  tabTitle: string
  currentIndex: number
  totalCount: number
  onSaveAndClose: () => void
  onForceClose: () => void
  onCancel: () => void
}) {
  const [isSaving, setIsSaving] = useState(false)

  const handleSave = async () => {
    setIsSaving(true)
    await onSaveAndClose()
    setIsSaving(false)
  }

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        {/* Header with X button */}
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-text-primary">
            未保存的更改
            {totalCount > 1 && (
              <span className="text-text-muted font-normal ml-1">
                ({currentIndex}/{totalCount})
              </span>
            )}
          </h3>
          <button
            onClick={onCancel}
            className="text-text-muted hover:text-text-primary transition p-1"
            title="取消"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <p className="modal-text mb-6">
          "<span className="modal-highlight">{tabTitle}</span>" 有未保存的更改，您希望如何处理？
        </p>

        <div className="modal-actions">
          <button
            className="modal-btn modal-btn--cancel"
            onClick={onCancel}
            disabled={isSaving}
          >
            取消
          </button>
          <button
            className="modal-btn modal-btn--danger"
            onClick={onForceClose}
            disabled={isSaving}
          >
            直接关闭
          </button>
          <button
            className="modal-btn modal-btn--primary"
            onClick={handleSave}
            disabled={isSaving}
          >
            {isSaving ? '保存中...' : '保存并关闭'}
          </button>
        </div>
      </div>
    </div>
  )
}
