import { useEffect } from 'react'
import { useNavigate, useLocation } from '@tanstack/react-router'
import { useLayoutStore } from '@/stores/layout'

export function useKeyboardShortcuts() {
  const navigate = useNavigate()
  const location = useLocation()
  const { toggleSidebar, toggleDetail, toggleBottom } = useLayoutStore()

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Ignore if typing in input/textarea
      const target = e.target as HTMLElement
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
        return
      }

      const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0
      const mod = isMac ? e.metaKey : e.ctrlKey

      // Layout toggles
      if (mod && e.key === 'b' && !e.shiftKey) {
        e.preventDefault()
        toggleSidebar()
        return
      }
      if (mod && e.key === 'j') {
        e.preventDefault()
        toggleBottom()
        return
      }
      if (mod && e.key === '\\') {
        e.preventDefault()
        toggleDetail()
        return
      }

      // Navigation
      if (mod && e.shiftKey && e.key === 'P') {
        e.preventDefault()
        // TODO: toggle command palette
        return
      }
      if (mod && e.key === 'p' && !e.shiftKey) {
        e.preventDefault()
        navigate({ to: '/wiki' })
        return
      }
      if (mod && e.key >= '1' && e.key <= '6') {
        e.preventDefault()
        const routes = ['/', '/wiki', '/ingest', '/raw', '/status', '/settings']
        const idx = parseInt(e.key) - 1
        if (routes[idx]) navigate({ to: routes[idx] })
        return
      }

      // Global search shortcut — jump to wiki page
      if (e.key === '/' && !mod) {
        e.preventDefault()
        if (location.pathname !== '/wiki') {
          navigate({ to: '/wiki' })
        }
        // Focus search input after navigation (next tick)
        setTimeout(() => {
          const input = document.querySelector('input[placeholder*="搜索"]') as HTMLInputElement
          input?.focus()
        }, 50)
        return
      }

      // Escape closes mobile panels
      if (e.key === 'Escape') {
        if (window.innerWidth <= 768) {
          const { sidebarOpen, detailOpen, bottomOpen } = useLayoutStore.getState()
          if (sidebarOpen) toggleSidebar()
          if (detailOpen) toggleDetail()
          if (bottomOpen) toggleBottom()
        }
      }
    }

    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [navigate, location.pathname, toggleSidebar, toggleDetail, toggleBottom])
}
