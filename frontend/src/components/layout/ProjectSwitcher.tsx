import { useState, useRef, useEffect } from 'react'
import { useProjectStore } from '@/stores/project'
import { Input } from '@/components/ui/Input'
import { Modal } from '@/components/ui/Modal'
import { cn } from '@/lib/utils'

export function ProjectSwitcher() {
  const { projects, activeProjectId, isLoading, loadProjects, setActiveProject, addProject, removeProject } = useProjectStore()
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [newName, setNewName] = useState('')
  const [newRootPath, setNewRootPath] = useState('')
  const [error, setError] = useState('')
  const dropdownRef = useRef<HTMLDivElement>(null)

  const activeProject = projects.find((p) => p.id === activeProjectId)

  // Load projects on mount
  useEffect(() => {
    loadProjects()
  }, [])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleCreate = async () => {
    const trimmed = newName.trim()
    if (!trimmed) return
    setError('')
    try {
      await addProject(trimmed, newRootPath)
      setNewName('')
      setNewRootPath('')
      setModalOpen(false)
      setDropdownOpen(false)
    } catch (err: any) {
      setError(err.message || '创建失败')
    }
  }

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    await removeProject(id)
    setDropdownOpen(false)
  }

  const handleSwitch = async (id: string) => {
    await setActiveProject(id)
    setDropdownOpen(false)
  }

  return (
    <>
      <div className="relative" ref={dropdownRef}>
        <button
          onClick={() => setDropdownOpen(!dropdownOpen)}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs text-text-muted hover:text-text-primary hover:bg-bg-elevated/60 transition cursor-pointer"
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="text-text-muted">
            <rect x="1" y="1" width="10" height="10" rx="2" stroke="currentColor" strokeWidth="1.2" />
            <path d="M4 4h4M4 6h4M4 8h2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
          </svg>
          <span className="max-w-[120px] truncate">
            {isLoading ? '加载中...' : (activeProject?.name ?? 'Default')}
          </span>
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
              {projects.length === 0 && (
                <div className="px-3 py-2 text-xs text-text-muted">暂无项目</div>
              )}
              {projects.map((project) => (
                <div
                  key={project.id}
                  onClick={() => handleSwitch(project.id)}
                  className={cn(
                    'flex items-center justify-between px-3 py-1.5 text-xs cursor-pointer transition group',
                    project.id === activeProjectId
                      ? 'text-accent-neural bg-accent-neural/10'
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

      <Modal open={modalOpen} onClose={() => { setModalOpen(false); setNewName(''); setNewRootPath(''); setError('') }} title="新建知识库项目" size="sm">
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
            {error && <p className="text-xs text-red-400">{error}</p>}
          </div>
          <div className="flex flex-col gap-2">
            <label className="text-xs text-text-muted font-medium">知识库目录（可选）</label>
            <Input
              placeholder="留空则使用默认应用目录，或输入本机绝对路径"
              value={newRootPath}
              onChange={(e) => setNewRootPath(e.target.value)}
            />
            <p className="text-[11px] text-text-muted">会在该目录下创建 raw/ 与 wiki/ 子目录，不会删除已有文件。</p>
          </div>
          <div className="flex justify-end gap-2">
            <button
              onClick={() => { setModalOpen(false); setNewName(''); setNewRootPath(''); setError('') }}
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
    </>
  )
}
