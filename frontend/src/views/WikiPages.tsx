import { useState } from 'react'
import { Link, useSearch } from '@tanstack/react-router'
import { Search, Zap } from 'lucide-react'
import { usePages, useSearch as useWikiSearch, useWikiQuery } from '@/hooks/useWiki'
import { MarkdownRenderer } from '@/components/markdown/MarkdownRenderer'
import { Badge } from '@/components/ui/Badge'
import { Input } from '@/components/ui/Input'
import { Modal } from '@/components/ui/Modal'
import { EmptyState } from '@/components/ui/EmptyState'

function CategoryBadge({ category }: { category: string }) {
  return (
    <Badge variant={(category as never) || 'default'}>
      {category}
    </Badge>
  )
}

export default function WikiPages() {
  const search = useSearch({ from: '/wiki' })
  const [q, setQ] = useState((search as { q?: string }).q || '')
  const [queryValue, setQueryValue] = useState((search as { q?: string }).q || '')

  const { data: pages } = usePages()
  const { data: searchResults } = useWikiSearch(queryValue)

  const displayed = queryValue ? searchResults : pages

  const handleSearch = () => {
    setQueryValue(q)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch()
  }

  // Query modal state
  const [queryModalOpen, setQueryModalOpen] = useState(false)
  const [question, setQuestion] = useState('')
  const [queryResult, setQueryResult] = useState('')
  const [querySources, setQuerySources] = useState<string[]>([])
  const wikiQuery = useWikiQuery()

  const handleQuery = async () => {
    if (!question.trim()) return
    setQueryResult('')
    setQuerySources([])
    const res = await wikiQuery.mutateAsync({ question: question.trim() })
    setQueryResult(res.answer)
    setQuerySources(res.sources)
  }

  return (
    <div className="p-4 sm:p-6 h-full overflow-y-auto">
      <div className="mb-5 animate-fade-up">
        <h1 className="text-xl font-bold tracking-tight text-text-primary">知识库</h1>
        <p className="text-sm mt-0.5 text-text-tertiary">浏览、搜索与深度查询所有 Wiki 页面</p>
      </div>

      {/* Search */}
      <div className="card p-5 mb-5 animate-fade-up stagger-1">
        <div className="flex flex-col sm:flex-row gap-3">
          <Input
            icon={<Search size={20} />}
            placeholder="搜索关键词，或输入问题让 AI 基于知识库回答..."
            className="py-3"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <div className="flex gap-2">
            <button onClick={handleSearch} className="btn btn-secondary" style={{ padding: '10px 20px' }}>
              搜索
            </button>
            <button onClick={() => { setQueryModalOpen(true); setQuestion(q) }} className="btn btn-primary flex items-center gap-1.5" style={{ padding: '10px 20px' }}>
              <Zap size={15} /> 智能问答
            </button>
          </div>
        </div>
      </div>

      {/* Results */}
      {queryValue && (
        <div className="mb-5 text-sm flex items-center justify-between animate-fade-up stagger-3">
          <span className="text-text-tertiary">
            “<span className="font-medium text-text-primary">{queryValue}</span>” 的搜索结果 · 共 {displayed?.length ?? 0} 条
          </span>
          <button onClick={() => { setQ(''); setQueryValue(''); }} className="text-xs font-medium text-text-muted">
            清除搜索
          </button>
        </div>
      )}

      {/* Pages Grid */}
      <div className="animate-fade-up stagger-3">
        {displayed && displayed.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {displayed.map((page) => (
              <Link
                key={page.slug}
                to="/wiki/$slug"
                params={{ slug: page.slug }}
                className="card card-glow group flex flex-col p-0 overflow-hidden"
              >
                <div className="p-5 flex-1">
                  <div className="flex items-center justify-between mb-3">
                    <CategoryBadge category={page.category} />
                    {'updated_at' in page && page.updated_at && (
                      <span className="text-xs font-mono text-text-muted">
                        {new Date(page.updated_at).toLocaleDateString('zh-CN')}
                      </span>
                    )}
                  </div>
                  <h2 className="text-base font-bold mb-2 line-clamp-1 transition group-hover:text-accent-neural text-text-primary tracking-tight">
                    {page.title}
                  </h2>
                  <p className="text-sm line-clamp-3 text-text-tertiary">
                    {'summary' in page ? page.summary : 'snippet' in page ? page.snippet : '暂无摘要'}
                  </p>
                </div>
                <div className="px-5 py-3 flex items-center justify-between border-t border-border-subtle bg-white/[0.015]">
                  <span className="text-xs font-mono text-text-muted">
                    {'word_count' in page && page.word_count ? `${page.word_count} 字` : 'score' in page ? `相关度: ${(page as {score:number}).score.toFixed(2)}` : ''}
                  </span>
                  <span className="text-xs font-medium transition-transform group-hover:translate-x-1 text-accent-neural">
                    阅读 →
                  </span>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <EmptyState
            icon="🔍"
            title="未找到相关页面"
            description="尝试其他关键词，或摄入新文档来丰富知识库"
            action={{ to: '/ingest', label: '摄入新文档' }}
          />
        )}
      </div>

      {/* Query Modal */}
      <Modal
        open={queryModalOpen}
        onClose={() => setQueryModalOpen(false)}
        title={<span className="flex items-center gap-2"><Zap size={18} className="text-accent-neural" /> 智能问答</span>}
        size="lg"
      >
              <div className="flex gap-2 mb-4">
                <input
                  type="text"
                  placeholder="输入你的问题..."
                  className="input flex-1"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleQuery()}
                />
                <button
                  onClick={handleQuery}
                  disabled={wikiQuery.isPending || !question.trim()}
                  className="btn btn-primary disabled:opacity-50"
                >
                  {wikiQuery.isPending ? '思考中...' : '提问'}
                </button>
              </div>

              {wikiQuery.isPending && (
                <div className="flex items-center gap-3 py-8 text-text-muted animate-pulse">
                  <div className="w-5 h-5 border-2 border-accent-neural border-t-transparent rounded-full animate-spin" />
                  AI 正在基于知识库推理中...
                </div>
              )}

              {queryResult && (
                <div className="space-y-4 animate-fade-up">
                  <div className="card p-5">
                    <div className="text-xs font-semibold uppercase tracking-wider mb-3 text-text-muted">回答</div>
                    <div className="markdown-body text-sm">
                      <MarkdownRenderer content={queryResult} />
                    </div>
                  </div>
                  {querySources.length > 0 && (
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-wider mb-2 text-text-muted">参考来源</div>
                      <div className="flex flex-wrap gap-2">
                        {querySources.map((slug) => (
                          <Link
                            key={slug}
                            to="/wiki/$slug"
                            params={{ slug }}
                            className="badge bg-accent-neural/10 text-accent-neural hover:bg-accent-neural/20 transition"
                          >
                            {slug}
                          </Link>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
      </Modal>
    </div>
  )
}
