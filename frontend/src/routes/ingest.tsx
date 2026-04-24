import { createFileRoute } from '@tanstack/react-router'
import Ingest from '@/views/Ingest'

export const Route = createFileRoute('/ingest')({
  component: Ingest,
})
