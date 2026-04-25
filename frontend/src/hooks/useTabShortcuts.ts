import { useEffect, useCallback, useRef } from 'react'
import { useWikiTabsStore } from '@/stores/wikiTabs'

/**
 * useTabShortcuts — Wiki 标签页键盘快捷键管理
 * 
 * 使用命令模式注册快捷键，支持：
 * - Cmd+W: 关闭当前标签
 * - Cmd+T: 新建标签
 * - Cmd+Tab: 下一个标签
 * - Cmd+Shift+Tab: 上一个标签
 * - Cmd+Shift+T: 恢复最近关闭
 */
export function useTabShortcuts() {
  const store = useWikiTabsStore
  const handlerRef = useRef<((e: KeyboardEvent) => void) | null>(null)

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0
    const modKey = isMac ? e.metaKey : e.ctrlKey

    if (!modKey) return

    // Cmd+Shift+T: 恢复最近关闭（优先级最高，最先匹配）
    if (e.shiftKey && e.key === 'T') {
      e.preventDefault()
      const { restoreTab } = store.getState()
      restoreTab()
      return
    }

    // Cmd+T: 新建标签
    if (e.key === 't' && !e.shiftKey) {
      e.preventDefault()
      const { openNote } = store.getState()
      openNote()
      return
    }

    // Cmd+W: 关闭当前标签
    if (e.key === 'w') {
      e.preventDefault()
      const state = store.getState()
      if (!state.activeKey) return

      const isDirty = state.isDirty(state.activeKey)
      if (isDirty) {
        // Dirty tab — let UI handle confirmation via custom event
        window.dispatchEvent(
          new CustomEvent('wiki-tab-close-request', { detail: { key: state.activeKey } })
        )
      } else {
        state.closeTab(state.activeKey, true)
      }
      return
    }

    // Cmd+Tab / Cmd+Shift+Tab: 切换标签
    if (e.key === 'Tab') {
      e.preventDefault()
      const { activateTabByIndex } = store.getState()
      activateTabByIndex(e.shiftKey ? -1 : 1)
      return
    }
  }, [store])

  useEffect(() => {
    handlerRef.current = handleKeyDown
    window.addEventListener('keydown', handleKeyDown)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      handlerRef.current = null
    }
  }, [handleKeyDown])

  return null
}
