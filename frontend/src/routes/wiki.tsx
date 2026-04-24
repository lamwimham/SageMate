import { createFileRoute } from '@tanstack/react-router'
import WikiIndex from '@/views/WikiIndex'

export const Route = createFileRoute('/wiki')({
  component: WikiIndex,
})
