import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'
import { useWikiTabsStore } from '@/stores/wikiTabs'

function WikiLink({ slug, exists }: { slug: string; exists: boolean }) {
  const openPage = useWikiTabsStore((s) => s.openPage)

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    openPage(slug, slug)
  }

  return (
    <a
      href={`/wiki/${slug}`}
      onClick={handleClick}
      className={exists ? 'wiki-link' : 'wiki-link wiki-link-red'}
      title={exists ? undefined : '页面尚未创建'}
    >
      {slug}
    </a>
  )
}

export function MarkdownRenderer({ content, existingSlugs }: { content: string; existingSlugs?: string[] }) {
  const slugSet = new Set(existingSlugs ?? [])

  // Strip YAML frontmatter (remove ALL frontmatter blocks at the start)
  let body = content
  while (body.match(/^---\s*\n[\s\S]*?\n---\s*\n/)) {
    body = body.replace(/^---\s*\n[\s\S]*?\n---\s*\n/, '')
  }

  // Pre-process wiki links: [[slug]] -> <WIKILINK:slug>
  const processed = body.replace(/\[\[([^\]]+)\]\]/g, '<WIKILINK:$1>')

  const parts: (string | React.ReactNode)[] = []
  const regex = /<WIKILINK:([^>]+)>/g
  let lastIndex = 0
  let match

  while ((match = regex.exec(processed)) !== null) {
    if (match.index > lastIndex) {
      parts.push(processed.slice(lastIndex, match.index))
    }
    const slug = match[1]
    parts.push(<WikiLink key={slug + match.index} slug={slug} exists={slugSet.has(slug)} />)
    lastIndex = regex.lastIndex
  }
  if (lastIndex < processed.length) {
    parts.push(processed.slice(lastIndex))
  }

  return (
    <div className="markdown-body">
      {parts.map((part, i) =>
        typeof part === 'string' ? (
          <ReactMarkdown
            key={i}
            remarkPlugins={[remarkGfm, remarkBreaks, remarkMath]}
            rehypePlugins={[rehypeKatex]}
          >
            {part}
          </ReactMarkdown>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </div>
  )
}
