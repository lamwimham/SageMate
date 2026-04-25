/**
 * useStoreField — Zustand 字段级订阅 Hook
 *
 * 职责：
 * 1. 只订阅需要的字段，避免整个 store 变化导致重渲染
 * 2. 返回稳定引用（useMemo），避免子组件不必要的重渲染
 * 3. 支持深层路径选择
 *
 * 设计模式：选择器 + 记忆化 + 引用稳定
 */

import { useMemo } from 'react'
import { useShallow } from 'zustand/react/shallow'

/**
 * 多字段选择器 — 返回稳定对象引用
 *
 * 用法：
 *   const { title, content } = usePageStore(
 *     useShallow((s) => ({ title: s.title, content: s.content }))
 *   )
 */
export { useShallow }

/**
 * 深层路径选择器 — 安全访问嵌套字段
 *
 * 用法：
 *   const tags = useDeepField(page, 'meta.tags', [])
 */
export function useDeepField<T>(
  obj: Record<string, any>,
  path: string,
  defaultValue: T
): T {
  return useMemo(() => {
    const parts = path.split('.')
    let current: any = obj
    for (const part of parts) {
      if (current == null) return defaultValue
      current = current[part]
    }
    return current ?? defaultValue
  }, [obj, path, defaultValue])
}
