import { createFileRoute } from '@tanstack/react-router'
import Status from '@/views/Status'

export const Route = createFileRoute('/status')({
  component: Status,
})
