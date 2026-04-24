import { create } from 'zustand'

interface LayoutState {
  sidebarOpen: boolean
  detailOpen: boolean
  bottomOpen: boolean
  activeNav: string
  toggleSidebar: () => void
  toggleDetail: () => void
  toggleBottom: () => void
  setActiveNav: (nav: string) => void
}

export const useLayoutStore = create<LayoutState>((set) => ({
  sidebarOpen: true,
  detailOpen: true,
  bottomOpen: false,
  activeNav: 'dashboard',
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  toggleDetail: () => set((s) => ({ detailOpen: !s.detailOpen })),
  toggleBottom: () => set((s) => ({ bottomOpen: !s.bottomOpen })),
  setActiveNav: (nav) => set({ activeNav: nav }),
}))
