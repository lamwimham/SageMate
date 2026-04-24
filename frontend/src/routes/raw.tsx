import { createFileRoute } from '@tanstack/react-router'
import RawFiles from '@/views/RawFiles'

export const Route = createFileRoute('/raw')({
  component: RawFiles,
})
