import { useEffect } from 'react'
import { useNavigate } from '@tanstack/react-router'

// Redirect to /wiki for backward compatibility
export default function Wiki() {
  const navigate = useNavigate()
  useEffect(() => {
    navigate({ to: '/wiki', replace: true })
  }, [navigate])
  return null
}
