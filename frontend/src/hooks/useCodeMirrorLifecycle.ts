/**
 * useCodeMirrorLifecycle — CodeMirror 编辑器的内存治理 Hook
 *
 * 职责：
 * 1. 将 CodeMirror 实例注册到 MemoryGovernor
 * 2. 组件卸载时强制销毁实例，释放语法树、decorations、历史栈
 * 3. 非活跃标签页自动冻结（保留内容但释放编辑器内存）
 *
 * 设计模式：资源池 + 生命周期绑定
 */

import { useEffect, useRef, useCallback } from 'react'
import { MemoryGovernor } from '@/lib/memory-governor'

interface UseCodeMirrorLifecycleOptions {
  /** 标签/页面唯一标识 */
  tabKey: string
  /** 当前内容（用于冻结时保存） */
  content: string
  /** 内容变化回调 */
  onContentChange?: (value: string) => void
}

export function useCodeMirrorLifecycle({ tabKey, content }: UseCodeMirrorLifecycleOptions) {
  const cmViewRef = useRef<any>(null)
  const contentRef = useRef(content)
  contentRef.current = content

  const setView = useCallback((view: any) => {
    cmViewRef.current = view
  }, [])

  useEffect(() => {
    // 注册到内存治理中心
    MemoryGovernor.register({
      key: `cm-${tabKey}`,
      type: 'codemirror',
      estimatedBytes: 30 * 1024 * 1024, // 30MB 估算
      createdAt: Date.now(),
      lastActiveAt: Date.now(),
      freezable: true,
      dispose: () => {
        const view = cmViewRef.current
        if (view) {
          // 强制销毁 CodeMirror 内部状态
          view.destroy?.()
          cmViewRef.current = null
        }
      },
      freeze: () => {
        // 冻结：销毁编辑器但保留内容
        const view = cmViewRef.current
        if (view) {
          view.destroy?.()
          cmViewRef.current = null
        }
      },
      thaw: () => {
        // 解冻：由组件重新挂载时自动重建
        // 这里不需要做额外操作，React 重新渲染会创建新实例
      },
    })

    return () => {
      MemoryGovernor.dispose(`cm-${tabKey}`)
    }
  }, [tabKey])

  // 标签活跃时 touch
  useEffect(() => {
    MemoryGovernor.touch(`cm-${tabKey}`)
  }, [tabKey, content])

  return { cmViewRef, setView, view: cmViewRef.current }
}
