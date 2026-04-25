import { useState, useRef, useCallback, useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useWikiTabsStore, type WikiTab } from '@/stores/wikiTabs'
import { useNoteContentStore } from '@/stores/noteContent'
import { invalidatePageCache } from '@/hooks/useWiki'
import { useTabShortcuts } from '@/hooks/useTabShortcuts'
import { TabItem } from './TabItem'
import { TabContextMenu } from './TabContextMenu'

/**
 * Wiki Tab Bar — 浏览器风格标签栏
 * 
 * 设计模式：
 * - 组合模式：TabItem / TabContextMenu / TabOverflow 组合
 * - 策略模式：关闭确认流程
 * - 观察者模式：键盘快捷键 + 自定义事件
 * 
 * 交互：
 * - 单击激活、双击重命名、中键关闭
 * - 右键菜单：关闭/其他/左侧/右侧/恢复
 * - 快捷键：Cmd+W/T/Tab/Shift+Tab/Shift+T
 * - 溢出标签收进下拉框
 */

type TabCloseStrategy = 'save-and-close' | 'force-close' | 'cancel'

interface CloseState {
  keys: string[]
  index: number
  isBatch: boolean
}

export function WikiTabBar() {
  const qc = useQueryClient()
  const {
    tabs, activeKey, activateTab, closeTab, closeAll, closeOther, closeLeft, closeRight,
    restoreTab, openNote, isDirty, updateTabTitle, getSaveHandler,
    unregisterDirty, unregisterSaveHandler, recentlyClosed,
  } = useWikiTabsStore()

  // Register keyboard shortcuts (command pattern)
  useTabShortcuts()

  // --- Close confirmation queue (strategy pattern) ---
  const [closeState, setCloseState] = useState<CloseState>({ keys: [], index: 0, isBatch: false })

  // --- Inline editing ---
  const [editingKey, setEditingKey] = useState<string | null>(null)

  // --- Overflow dropdown ---
  const [showOverflow, setShowOverflow] = useState(false)
  const tabBarRef = useRef<HTMLDivElement>(null)
  const tabsContainerRef = useRef<HTMLDivElement>(null)
  const [visibleCount, setVisibleCount] = useState(tabs.length)

  // --- Context menu ---
  const [contextMenu, setContextMenu] = useState<{ tab: WikiTab; x: number; y: number } | null>(null)

  // --- Measure overflow ---
  useEffect(() => {
    const container = tabsContainerRef.current
    const tabBar = tabBarRef.current
    if (!container || !tabBar) return

    const measure = () => {
      const tabBarWidth = tabBar.clientWidth
      const actionsWidth = 80
      const availableWidth = Math.max(0, tabBarWidth - actionsWidth)
      const tabElements = container.querySelectorAll('.browser-tab')
      let count = 0
      let usedWidth = 0
      const gap = 1

      for (const tab of Array.from(tabElements)) {
        const tabWidth = (tab as HTMLElement).offsetWidth
        if (usedWidth + tabWidth + (count > 0 ? gap : 0) <= availableWidth) {
          usedWidth += tabWidth + (count > 0 ? gap : 0)
          count++
        } else {
          break
        }
      }
      setVisibleCount(Math.min(count, tabs.length))
    }

    const rafId = requestAnimationFrame(measure)
    const timeoutId = setTimeout(measure, 50)
    const ro = new ResizeObserver(measure)
    ro.observe(tabBar)

    return () => {
      cancelAnimationFrame(rafId)
      clearTimeout(timeoutId)
      ro.disconnect()
    }
  }, [tabs.length, activeKey])

  // --- Listen for close requests from keyboard shortcuts ---
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail as { key: string }
      if (detail?.key && isDirty(detail.key)) {
        setCloseState({ keys: [detail.key], index: 0, isBatch: false })
      }
    }
    window.addEventListener('wiki-tab-close-request', handler)
    return () => window.removeEventListener('wiki-tab-close-request', handler)
  }, [isDirty])

  // --- Tab operations ---
  const handleTabClick = (tab: WikiTab) => {
    activateTab(tab.key)
    setShowOverflow(false)
    setContextMenu(null)
  }

  const handleTabRename = useCallback((key: string, newTitle: string) => {
    updateTabTitle(key, newTitle)
  }, [updateTabTitle])

  const handleClose = (e: React.MouseEvent, key: string) => {
    e.stopPropagation()
    if (isDirty(key)) {
      setCloseState({ keys: [key], index: 0, isBatch: false })
    } else {
      doClose(key)
    }
  }

  const handleAuxClick = (e: React.MouseEvent, key: string) => {
    if (e.button === 1) { // middle click
      e.preventDefault()
      e.stopPropagation()
      if (isDirty(key)) {
        setCloseState({ keys: [key], index: 0, isBatch: false })
      } else {
        doClose(key)
      }
    }
  }

  const handleContextMenu = (e: React.MouseEvent, tab: WikiTab) => {
    e.preventDefault()
    setContextMenu({ tab, x: e.clientX, y: e.clientY })
  }

  /** Actually perform close cleanup */
  const doClose = (key: string) => {
    const noteStore = useNoteContentStore.getState()
    noteStore.clearContent(key)
    unregisterSaveHandler(key)
    unregisterDirty(key)
    invalidatePageCache(qc, key)
    closeTab(key, true)
  }

  /** Advance close queue */
  const advanceQueue = () => {
    const { keys, index, isBatch } = closeState
    const nextIndex = index + 1
    if (nextIndex >= keys.length) {
      if (isBatch) {
        const { tabs: remainingTabs } = useWikiTabsStore.getState()
        for (const tab of remainingTabs) {
          doClose(tab.key)
        }
      }
      setCloseState({ keys: [], index: 0, isBatch: false })
    } else {
      setCloseState((s) => ({ ...s, index: nextIndex }))
    }
  }

  const handleSaveAndClose = async () => {
    const key = closeState.keys[closeState.index]
    const handler = getSaveHandler(key)
    if (handler) {
      try {
        await handler()
      } catch {
        return
      }
    }
    doClose(key)
    advanceQueue()
  }

  const handleForceClose = () => {
    const key = closeState.keys[closeState.index]
    doClose(key)
    advanceQueue()
  }

  const handleCancelClose = () => {
    setCloseState({ keys: [], index: 0, isBatch: false })
  }

  // --- Batch close operations ---
  const handleBatchClose = (keys: string[]) => {
    const dirtyKeys = keys.filter((k) => isDirty(k))
    if (dirtyKeys.length > 0) {
      setCloseState({ keys: dirtyKeys, index: 0, isBatch: true })
    } else {
      for (const key of keys) {
        doClose(key)
      }
    }
  }

  const handleBatchCloseOther = (exceptKey: string) => {
    const otherKeys = tabs.filter((t) => t.key !== exceptKey).map((t) => t.key)
    handleBatchClose(otherKeys)
  }

  const handleBatchCloseLeft = (key: string) => {
    const idx = tabs.findIndex((t) => t.key === key)
    if (idx <= 0) return
    const leftKeys = tabs.slice(0, idx).map((t) => t.key)
    handleBatchClose(leftKeys)
  }

  const handleBatchCloseRight = (key: string) => {
    const idx = tabs.findIndex((t) => t.key === key)
    if (idx === -1 || idx >= tabs.length - 1) return
    const rightKeys = tabs.slice(idx + 1).map((t) => t.key)
    handleBatchClose(rightKeys)
  }

  // --- Visible vs overflow ---
  const visibleTabs = tabs.slice(0, visibleCount)
  const overflowTabs = tabs.slice(visibleCount)
  const hasOverflow = overflowTabs.length > 0

  // --- Current confirm tab ---
  const currentConfirmKey = closeState.keys[closeState.index]
  const currentConfirmTab = currentConfirmKey ? tabs.find((t) => t.key === currentConfirmKey) : null

  // --- Empty state ---
  if (tabs.length === 0) {
    return (
      <div className="tab-bar bg-bg-surface border-b border-border-subtle" ref={tabBarRef}>
        <div className="tab-bar__tabs-area" ref={tabsContainerRef} />
        <div className="tab-bar__actions">
          <button onClick={openNote} className="tab-bar__icon-btn tab-bar__add-btn" title="新建笔记 (Cmd+T)">
            +
          </button>
        </div>
      </div>
    )
  }

  return (
    <>
      <div className="tab-bar bg-bg-surface border-b border-border-subtle" ref={tabBarRef}>
        {/* Tabs container */}
        <div className="tab-bar__tabs-area" ref={tabsContainerRef}>
          {visibleTabs.map((tab) => (
            <TabItem
              key={tab.key}
              tab={tab}
              isActive={tab.key === activeKey}
              isDirty={isDirty(tab.key)}
              onClick={handleTabClick}
              onClose={handleClose}
              onAuxClick={handleAuxClick}
              onContextMenu={handleContextMenu}
              onRename={handleTabRename}
            />
          ))}
        </div>

        {/* Right side actions */}
        <div className="tab-bar__actions">
          {/* Overflow dropdown */}
          {hasOverflow && (
            <div className="relative">
              <button
                onClick={() => setShowOverflow(!showOverflow)}
                className="tab-bar__icon-btn"
                title={`${overflowTabs.length} 个隐藏标签`}
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5">
                  <polyline points="6 9 12 15 18 9" />
                </svg>
                <span className="tab-bar__overflow-badge">{overflowTabs.length}</span>
              </button>

              {showOverflow && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowOverflow(false)} />
                  <div className="tab-overflow-dropdown">
                    {overflowTabs.map((tab) => (
                      <div
                        key={tab.key}
                        onClick={() => handleTabClick(tab)}
                        className={`tab-overflow-item${tab.key === activeKey ? ' tab-overflow-item--active' : ''}`}
                      >
                        <span className="tab-overflow-item__title">{tab.title}</span>
                        {isDirty(tab.key) && <span className="tab-overflow-item__dot" />}
                        <span
                          onClick={(e) => {
                            e.stopPropagation()
                            handleClose(e, tab.key)
                            if (tabs.length <= 1) setShowOverflow(false)
                          }}
                          className="tab-overflow-item__close"
                        >
                          ×
                        </span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}

          <button onClick={openNote} className="tab-bar__icon-btn tab-bar__add-btn" title="新建笔记 (Cmd+T)">
            +
          </button>
        </div>
      </div>

      {/* Context Menu */}
      {contextMenu && (
        <TabContextMenu
          tab={contextMenu.tab}
          tabIndex={tabs.findIndex((t) => t.key === contextMenu.tab.key)}
          totalTabs={tabs.length}
          x={contextMenu.x}
          y={contextMenu.y}
          onClose={() => setContextMenu(null)}
          onCloseTab={() => {
            handleClose(new MouseEvent('click') as any, contextMenu.tab.key)
            setContextMenu(null)
          }}
          onCloseOther={() => {
            handleBatchCloseOther(contextMenu.tab.key)
            setContextMenu(null)
          }}
          onCloseLeft={() => {
            handleBatchCloseLeft(contextMenu.tab.key)
            setContextMenu(null)
          }}
          onCloseRight={() => {
            handleBatchCloseRight(contextMenu.tab.key)
            setContextMenu(null)
          }}
          onRestore={restoreTab}
          canRestore={recentlyClosed.length > 0}
        />
      )}

      {/* Close Confirmation Modal */}
      {currentConfirmTab && (
        <CloseConfirmModal
          tabTitle={currentConfirmTab.title}
          currentIndex={closeState.index + 1}
          totalCount={closeState.keys.length}
          onSaveAndClose={handleSaveAndClose}
          onForceClose={handleForceClose}
          onCancel={handleCancelClose}
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
