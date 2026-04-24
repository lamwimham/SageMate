import { create } from 'zustand'

type ThemeMode = 'dark' | 'light' | 'system'

interface ThemeState {
  mode: ThemeMode
  resolved: 'dark' | 'light'
  setMode: (mode: ThemeMode) => void
}

function resolve(mode: ThemeMode): 'dark' | 'light' {
  if (mode !== 'system') return mode
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(resolved: 'dark' | 'light') {
  document.documentElement.setAttribute('data-theme', resolved)
}

const stored = (localStorage.getItem('theme') as ThemeMode) || 'dark'
const initialResolved = resolve(stored)

// Apply immediately on module load (before React hydration)
applyTheme(initialResolved)

export const useThemeStore = create<ThemeState>((set) => ({
  mode: stored,
  resolved: initialResolved,
  setMode: (mode) => {
    const resolved = resolve(mode)
    localStorage.setItem('theme', mode)
    applyTheme(resolved)
    set({ mode, resolved })
  },
}))

window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
  const { mode } = useThemeStore.getState()
  if (mode === 'system') {
    const resolved = e.matches ? 'dark' : 'light'
    applyTheme(resolved)
    useThemeStore.setState({ resolved })
  }
})
