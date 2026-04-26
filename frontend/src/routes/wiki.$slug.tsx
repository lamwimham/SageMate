import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useEffect } from 'react'
import { useWikiTabsStore } from '@/stores/wikiTabs'

// wiki/$slug — redirect to /wiki and open the page in a tab
function WikiSlugRedirect() {
  const navigate = useNavigate()
  const openPage = useWikiTabsStore((s) => s.openPage)
  const { slug } = Route.useParams()

  useEffect(() => {
    // Open the page in wiki tabs
    openPage(slug, slug)
    // Redirect to /wiki (the main wiki view with tabs)
    navigate({ to: '/wiki', replace: true })
  }, [slug, openPage, navigate])

  return null
}

export const Route = createFileRoute('/wiki/$slug')({
  component: WikiSlugRedirect,
})
