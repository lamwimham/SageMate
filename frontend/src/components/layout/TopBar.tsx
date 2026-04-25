import { useState, useRef, useEffect } from 'react'
import { useProjectStore } from '@/stores/project'
import { useLayoutStore } from '@/stores/layout'
import { Input } from '@/components/ui/Input'
import { Modal } from '@/components/ui/Modal'
import { cn } from '@/lib/utils'

export function TopBar() {
  const { projects, activeProjectId, setActiveProject, addProject, removeProject } = useProjectStore()
  const { sidebarOpen, detailOpen, toggleSidebar, toggleDetail } = useLayoutStore()
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [newName, setNewName] = useState('')
  const dropdownRef = useRef<HTMLDivElement>(null)

  const activeProject = projects.find((p) => p.id === activeProjectId)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleCreate = () => {
    const trimmed = newName.trim()
    if (!trimmed) return
    addProject(trimmed)
    setNewName('')
    setModalOpen(false)
    setDropdownOpen(false)
  }

  const handleDelete = (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    removeProject(id)
    setDropdownOpen(false)
  }

  return (
    <header className="h-9 bg-bg-void flex items-center px-3 gap-3 shrink-0">
      {/* Spacer — left */}
      <div className="flex-1" />

      {/* Project Switcher — centered */}
      <div className="relative" ref={dropdownRef}>
        <button
          onClick={() => setDropdownOpen(!dropdownOpen)}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs text-text-muted hover:text-text-primary hover:bg-bg-elevated/60 transition cursor-pointer"
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="text-text-muted">
            <rect x="1" y="1" width="10" height="10" rx="2" stroke="currentColor" strokeWidth="1.2" />
            <path d="M4 4h4M4 6h4M4 8h2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
          </svg>
          <span className="max-w-[120px] truncate">{activeProject?.name ?? 'Default'}</span>
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" className="opacity-60">
            <path d="M2.5 4l2.5 2.5L7.5 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>

        {dropdownOpen && (
          <div className="absolute top-full left-0 mt-1 w-64 bg-bg-surface border border-border-subtle rounded-lg shadow-xl z-50 overflow-hidden animate-fade-up">
            <div className="px-3 py-2 text-[12px] uppercase tracking-wider text-text-muted font-medium border-b border-border-subtle">
              知识库项目
            </div>
            <div className="max-h-48 overflow-y-auto py-1">
              {projects.map((project) => (
                <div
                  key={project.id}
                  onClick={() => {
                    setActiveProject(project.id)
                    setDropdownOpen(false)
                  }}
                  className={cn(
                    'flex items-center justify-between px-3 py-1.5 text-xs cursor-pointer transition group',
                    project.id === activeProjectId
                      ? 'text-accent-primary bg-accent-primary/10'
                      : 'text-text-secondary hover:text-text-primary hover:bg-bg-elevated'
                  )}
                >
                  <span className="truncate">{project.name}</span>
                  {project.id !== 'default' && (
                    <button
                      onClick={(e) => handleDelete(project.id, e)}
                      className="text-text-muted hover:text-red-400 transition cursor-pointer px-1"
                    >
                      ×
                    </button>
                  )}
                </div>
              ))}
            </div>
            <div className="border-t border-border-subtle px-3 py-2">
              <button
                onClick={() => { setModalOpen(true); setDropdownOpen(false) }}
                className="w-full text-xs text-accent-primary hover:text-accent-secondary transition cursor-pointer"
              >
                + 新建项目
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Spacer — right */}
      <div className="flex-1" />

      {/* Control Icons (right side) */}
      <div className="flex items-center gap-1">
        <button
          onClick={toggleSidebar}
          className={cn(
            'w-7 h-7 flex items-center justify-center rounded-md transition-all duration-200 cursor-pointer',
            sidebarOpen ? 'text-accent-neural bg-accent-neural/10' : 'text-text-muted hover:text-text-secondary hover:bg-bg-elevated/50'
          )}
          title="切换侧边栏"
          aria-label="切换侧边栏"
        >
          <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
            <rect x="1" y="1" width="14" height="14" rx="2" />
            <line x1="5" y1="1" x2="5" y2="15" />
          </svg>
        </button>

        <button
          onClick={toggleDetail}
          className={cn(
            'w-7 h-7 flex items-center justify-center rounded-md transition-all duration-200 cursor-pointer',
            detailOpen ? 'text-accent-neural bg-accent-neural/10' : 'text-text-muted hover:text-text-secondary hover:bg-bg-elevated/50'
          )}
          title="切换详情面板"
          aria-label="切换详情面板"
        >
          <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4">
            <rect x="1" y="1" width="14" height="14" rx="2" />
            <line x1="11" y1="1" x2="11" y2="15" />
          </svg>
        </button>
      </div>

      {/* New Project Modal */}
      <Modal open={modalOpen} onClose={() => { setModalOpen(false); setNewName('') }} title="新建知识库项目" size="sm">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <label className="text-xs text-text-muted font-medium">项目名称</label>
            <Input
              placeholder="输入项目名称..."
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
              autoFocus
            />
          </div>
          <div className="flex justify-end gap-2">
            <button
              onClick={() => { setModalOpen(false); setNewName('') }}
              className="px-4 py-2 text-xs text-text-muted hover:text-text-primary transition cursor-pointer"
            >
              取消
            </button>
            <button
              onClick={handleCreate}
              disabled={!newName.trim()}
              className="px-4 py-2 text-xs bg-accent-primary text-white rounded-lg hover:bg-accent-secondary transition disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
            >
              创建
            </button>
          </div>
        </div>
      </Modal>
    </header>
  )
}
