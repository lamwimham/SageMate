import { createFileRoute } from '@tanstack/react-router'

// wiki/$slug is now handled by WikiIndex with viewMode='page'
// This route just redirects
export const Route = createFileRoute('/wiki/$slug')({
  component: () => null,
})
