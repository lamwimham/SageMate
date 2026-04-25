/**
 * MemoryGovernor — 前端内存治理中心
 *
 * 职责：
 * 1. 统一管理重量级资源的创建/销毁（CodeMirror 实例、大数组、DOM 节点）
 * 2. 实施容量上限策略（编辑器实例数、缓存大小）
 * 3. 提供可观测性（内存占用估算、资源分布）
 *
 * 设计模式：单例 + 注册表 + 策略模式
 */

export interface ResourceHandle {
  key: string
  type: 'codemirror' | 'query-cache' | 'dom-tree' | 'blob'
  /** 估算内存占用 (bytes) */
  estimatedBytes: number
  /** 创建时间 */
  createdAt: number
  /** 最后活跃时间 */
  lastActiveAt: number
  /** 释放回调 */
  dispose: () => void
  /** 是否可冻结（非活跃时转入冻结池而非直接销毁） */
  freezable: boolean
  /** 冻结回调（保存状态到轻量存储） */
  freeze?: () => void
  /** 解冻回调（从轻量存储恢复） */
  thaw?: () => void
}

interface GovernorConfig {
  /** 最大活跃 CodeMirror 实例数 */
  maxActiveEditors: number
  /** 最大冻结 CodeMirror 实例数 */
  maxFrozenEditors: number
  /** 单个编辑器估算内存上限 (bytes) */
  maxEditorBytes: number
}

const DEFAULT_CONFIG: GovernorConfig = {
  maxActiveEditors: 3,
  maxFrozenEditors: 5,
  maxEditorBytes: 50 * 1024 * 1024, // 50MB
}

class MemoryGovernorImpl {
  private registry = new Map<string, ResourceHandle>()
  private config: GovernorConfig
  private frozenKeys = new Set<string>()

  constructor(config: Partial<GovernorConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config }
  }

  /** 注册资源，如果超限则按策略回收 */
  register(handle: ResourceHandle): void {
    // 如果同名资源已存在，先销毁旧的
    const existing = this.registry.get(handle.key)
    if (existing) {
      this.dispose(handle.key)
    }

    // 按类型实施容量策略
    if (handle.type === 'codemirror') {
      this.enforceEditorQuota()
    }

    this.registry.set(handle.key, handle)
  }

  /** 标记资源活跃（更新 lastActiveAt） */
  touch(key: string): void {
    const handle = this.registry.get(key)
    if (handle) {
      handle.lastActiveAt = Date.now()
      if (this.frozenKeys.has(key)) {
        this.frozenKeys.delete(key)
        handle.thaw?.()
      }
    }
  }

  /** 释放指定资源 */
  dispose(key: string): void {
    const handle = this.registry.get(key)
    if (!handle) return

    this.frozenKeys.delete(key)
    try {
      handle.dispose()
    } catch (e) {
      console.warn(`[MemoryGovernor] dispose error for ${key}:`, e)
    }
    this.registry.delete(key)
  }

  /** 冻结资源（非活跃时保留状态但不占内存） */
  freeze(key: string): void {
    const handle = this.registry.get(key)
    if (!handle || !handle.freezable || this.frozenKeys.has(key)) return

    handle.freeze?.()
    this.frozenKeys.add(key)
  }

  /** 获取当前内存估算 */
  getMemoryReport(): { totalBytes: number; byType: Record<string, number>; count: number } {
    let totalBytes = 0
    const byType: Record<string, number> = {}

    for (const handle of this.registry.values()) {
      totalBytes += handle.estimatedBytes
      byType[handle.type] = (byType[handle.type] || 0) + handle.estimatedBytes
    }

    return { totalBytes, byType, count: this.registry.size }
  }

  /** 按 LRU 策略回收编辑器实例 */
  private enforceEditorQuota(): void {
    const editors = Array.from(this.registry.values())
      .filter((h) => h.type === 'codemirror' && !this.frozenKeys.has(h.key))
      .sort((a, b) => a.lastActiveAt - b.lastActiveAt)

    const frozenEditors = Array.from(this.registry.values())
      .filter((h) => h.type === 'codemirror' && this.frozenKeys.has(h.key))

    // 活跃池超限：最老的转入冻结池
    while (editors.length > this.config.maxActiveEditors) {
      const oldest = editors.shift()
      if (oldest) this.freeze(oldest.key)
    }

    // 冻结池超限：最老的直接销毁
    while (frozenEditors.length > this.config.maxFrozenEditors) {
      const oldest = frozenEditors.shift()
      if (oldest) this.dispose(oldest.key)
    }
  }

  /** 清空所有资源（页面卸载时） */
  disposeAll(): void {
    for (const key of this.registry.keys()) {
      this.dispose(key)
    }
  }
}

export const MemoryGovernor = new MemoryGovernorImpl()

/** 开发环境暴露到 window 方便调试 */
if (typeof window !== 'undefined' && import.meta.env.DEV) {
  (window as any).__MEMORY_GOVERNOR__ = MemoryGovernor
}
