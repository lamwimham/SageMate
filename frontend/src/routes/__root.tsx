import { createRootRoute, Outlet } from '@tanstack/react-router'
import { LayoutProvider } from '@/layout/LayoutContext'
import { PageShell } from '@/components/layout/PageShell'

export const Route = createRootRoute({
  component: () => (
    <LayoutProvider>
      <PageShell>
        <Outlet />
      </PageShell>
    </LayoutProvider>
  ),
})
