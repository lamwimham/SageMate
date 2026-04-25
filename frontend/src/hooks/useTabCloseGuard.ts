import { useEffect, useRef } from 'react'
import { useWikiTabsStore } from '@/stores/wikiTabs'

/**
 * useTabCloseGuard — 让编辑器组件注册"保存并关闭"能力
 *
 * 用法：
 * ```tsx
 * function MyEditor({ tabKey }: { tabKey: string }) {
 *   const [content, setContent] = useState('')
 *   const [hasChanges, setHasChanges] = useState(false)
 *
 *   useTabCloseGuard({
 *     tabKey,
 *     isDirty: hasChanges,
 *     onSave: async () => {
 *       await saveToServer(content)
 *     },
 *   })
 *
 *   // ... editor UI
 * }
 * ```
 */
interface UseTabCloseGuardOptions {
  /** Tab key to guard */
  tabKey: string
  /** Whether the tab has unsaved changes */
  isDirty: boolean
  /** Save handler — called when user chooses "save & close" */
  onSave: () => Promise<void>
}

export function useTabCloseGuard({ tabKey, isDirty, onSave }: UseTabCloseGuardOptions) {
  const onSaveRef = useRef(onSave)
  onSaveRef.current = onSave

  // Register/unregister dirty state — use getState() to avoid re-render triggers
  useEffect(() => {
    const { registerDirty, unregisterDirty } = useWikiTabsStore.getState()
    if (isDirty) {
      registerDirty(tabKey)
    } else {
      unregisterDirty(tabKey)
    }
    return () => {
      useWikiTabsStore.getState().unregisterDirty(tabKey)
    }
  }, [tabKey, isDirty])

  // Register save handler — use getState() to avoid re-render triggers
  useEffect(() => {
    const { registerSaveHandler } = useWikiTabsStore.getState()
    const handler = () => onSaveRef.current()
    registerSaveHandler(tabKey, handler)
    return () => {
      useWikiTabsStore.getState().unregisterSaveHandler(tabKey)
    }
  }, [tabKey])
}
