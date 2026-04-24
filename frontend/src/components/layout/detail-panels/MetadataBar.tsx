// ============================================================
// MetadataBar — 可折叠的页面属性面板
// ============================================================

import { useState, useCallback } from 'react'
import { cn } from '@/lib/utils'

export interface PageMetadata {
  title: string
  category: string
  tags: string[]
  sources: string[]
  created_at: string
  updated_at: string
}

interface MetadataBarProps {
  metadata: PageMetadata
  onChange: (metadata: Partial<PageMetadata>) => void
  categories: string[]
}

export function MetadataBar({ metadata, onChange, categories }: MetadataBarProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  const handleTitleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      onChange({ title: e.target.value })
    },
    [onChange]
  )

  const handleCategoryChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      onChange({ category: e.target.value })
    },
    [onChange]
  )

  const handleAddTag = useCallback(
    (tag: string) => {
      if (tag && !metadata.tags.includes(tag)) {
        onChange({ tags: [...metadata.tags, tag] })
      }
    },
    [metadata.tags, onChange]
  )

  const handleRemoveTag = useCallback(
    (tag: string) => {
      onChange({ tags: metadata.tags.filter((t) => t !== tag) })
    },
    [metadata.tags, onChange]
  )

  // Collapsed summary line
  const summaryText = `${metadata.category} · ${metadata.tags.join(', ')}`.trim()

  return (
    <div className="border-b border-border-subtle bg-[#16162a]">
      {/* Collapsed Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-2 flex items-center justify-between text-xs text-text-muted hover:text-text-primary transition"
      >
        <div className="flex items-center gap-2">
          <span className="text-sm">📋</span>
          <span className="truncate">{summaryText || '属性'}</span>
        </div>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          className={cn('w-3.5 h-3.5 transition-transform duration-200', isExpanded && 'rotate-180')}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {/* Expanded Form */}
      {isExpanded && (
        <div className="px-4 pb-3 space-y-3 text-xs animate-fade-up">
          {/* Title */}
          <div>
            <label className="block text-[10px] uppercase tracking-wider text-text-muted mb-1">
              标题
            </label>
            <input
              type="text"
              value={metadata.title}
              onChange={handleTitleChange}
              className="w-full bg-[#1a1a2e] border border-border-subtle rounded px-2 py-1 text-text-primary focus:outline-none focus:border-accent-neural/50"
            />
          </div>

          {/* Category */}
          <div>
            <label className="block text-[10px] uppercase tracking-wider text-text-muted mb-1">
              分类
            </label>
            <select
              value={metadata.category}
              onChange={handleCategoryChange}
              className="w-full bg-[#1a1a2e] border border-border-subtle rounded px-2 py-1 text-text-primary focus:outline-none focus:border-accent-neural/50"
            >
              {categories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>

          {/* Tags */}
          <div>
            <label className="block text-[10px] uppercase tracking-wider text-text-muted mb-1">
              标签
            </label>
            <div className="flex flex-wrap gap-1.5">
              {metadata.tags.map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-accent-neural/10 text-accent-neural text-[11px]"
                >
                  {tag}
                  <button
                    onClick={() => handleRemoveTag(tag)}
                    className="hover:text-red-400 transition"
                  >
                    ×
                  </button>
                </span>
              ))}
              <TagInput onAdd={handleAddTag} />
            </div>
          </div>

          {/* Read-only timestamps */}
          <div className="grid grid-cols-2 gap-2 text-[10px] text-text-muted pt-1">
            <div>
              创建 {new Date(metadata.created_at).toLocaleDateString('zh-CN')}
            </div>
            <div>
              更新 {new Date(metadata.updated_at).toLocaleDateString('zh-CN')}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function TagInput({ onAdd }: { onAdd: (tag: string) => void }) {
  const [value, setValue] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const tag = value.trim()
    if (tag) {
      onAdd(tag)
      setValue('')
    }
  }

  return (
    <form onSubmit={handleSubmit} className="inline-flex">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="+ 添加"
        className="w-16 bg-transparent border border-dashed border-border-subtle rounded px-2 py-0.5 text-[11px] text-text-primary placeholder-text-muted focus:outline-none focus:border-accent-neural/50"
      />
    </form>
  )
}
