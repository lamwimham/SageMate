import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'
import { useWikiTabsStore } from '@/stores/wikiTabs'

function WikiLink({ slug, display, exists }: { slug: string; display: string; exists: boolean }) {
  const openPage = useWikiTabsStore((s) => s.openPage)

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    console.log('[WikiLink] clicked, opening slug:', slug, 'display:', display)
    openPage(slug, display)
  }

  const handleAuxClick = (e: React.MouseEvent) => {
    // Middle mouse button (button === 1) — prevent opening in new tab
    if (e.button === 1) {
      e.preventDefault()
      e.stopPropagation()
      openPage(slug, display)
    }
  }

  return (
    <a
      href={`/wiki/${slug}`}
      onClick={handleClick}
      onMouseDown={handleAuxClick}
      className={exists ? 'wiki-link' : 'wiki-link wiki-link-red'}
      title={exists ? display : '页面尚未创建'}
    >
      {display}
    </a>
  )
}

export function MarkdownRenderer({ content, existingSlugs, pageMap, prefixMap }: { content: string; existingSlugs?: string[]; pageMap?: Record<string, string>; prefixMap?: Record<string, string> }) {
  const slugSet = new Set(existingSlugs ?? [])

  // Strip YAML frontmatter (remove ALL frontmatter blocks at the start)
  let body = content
  while (body.match(/^---\s*\n[\s\S]*?\n---\s*\n/)) {
    body = body.replace(/^---\s*\n[\s\S]*?\n---\s*\n/, '')
  }

  // Pre-process wiki links: [[slug]] -> markdown link [slug](/wiki/slug)
  // We use a special prefix on the href so we can identify wikilinks in the renderer
  const processed = body.replace(/\[\[([^\]]+)\]\]/g, (_match, raw) => {
    // Resolve: exact slug match -> exact title match -> prefix title match -> fallback to raw
    let resolvedSlug = raw
    let exists = slugSet.has(raw)
    if (!exists && pageMap) {
      const mapped = pageMap[raw]
      if (mapped) {
        resolvedSlug = mapped
        exists = slugSet.has(mapped)
      }
    }
    if (!exists && prefixMap) {
      const mapped = prefixMap[raw]
      if (mapped) {
        resolvedSlug = mapped
        exists = slugSet.has(mapped)
      }
    }
    // Use a special href prefix that we can identify in the link renderer
    // Use #__WIKILINK__ prefix so react-markdown doesn't strip it as invalid URL
    // If pages data hasn't loaded yet (slugSet is empty), default to 'exists' to avoid red flicker
    const status = (exists || slugSet.size === 0) ? 'exists' : 'missing'
    return `[${raw}](#__WIKILINK__${status}:${resolvedSlug})`
  })

  // Custom link component that intercepts wikilink anchors
  // ReactMarkdown passes `href` as the URL prop
  const LinkComponent = (props: any) => {
    const { node, href, children, ...rest } = props
    if (href && href.startsWith('#__WIKILINK__')) {
      const match = href.match(/^#__WIKILINK__(exists|missing):(.+)$/)
      if (match) {
        const exists = match[1] === 'exists'
        const slug = match[2]
        const display = typeof children === 'string' ? children : slug
        return <WikiLink slug={slug} display={display} exists={exists} />
      }
    }
    // Regular link
    return <a href={href} {...rest}>{children}</a>
  }

  return (
    <div className="markdown-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          a: LinkComponent,
        }}
      >
        {processed}
      </ReactMarkdown>
    </div>
  )
}
