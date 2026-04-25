import { useEffect } from 'react'
import { usePageLayout } from '@/hooks/usePageLayout'
import { WikiSidebar } from '@/components/layout/sidebars/WikiSidebar'
import { WikiChatPanel } from '@/components/layout/detail-panels/WikiQAPanel'
import { WikiTabBar } from '@/components/wiki/WikiTabBar'
import { WikiOverview } from '@/components/wiki/WikiOverview'
import { NoteEditor } from '@/components/wiki/NoteEditor'
import { WikiPageContent } from '@/components/wiki/WikiPageContent'
import { useWikiTabsStore } from '@/stores/wikiTabs'

export default function WikiIndex() {
  usePageLayout({
    sidebar: <WikiSidebar />,
    detailPanel: <WikiChatPanel />,
  })

  const { tabs, activeKey, openOverview } = useWikiTabsStore()

  // Open overview by default on mount
  useEffect(() => {
    if (tabs.length === 0) {
      openOverview()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const activeTab = tabs.find((t) => t.key === activeKey)

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Tab Bar */}
      <WikiTabBar />

      {/* Tab Content — overflow handled by each component internally */}
      <div className="flex-1 overflow-hidden min-h-0">
        {activeTab?.type === 'overview' && (
          <div className="p-4 sm:p-6 h-full overflow-y-auto">
            <div className="mb-5">
              <h1 className="text-xl font-bold tracking-tight text-text-primary">知识库概览</h1>
              <p className="text-sm mt-1 text-text-tertiary">本地优先的持久化知识网络 · 文件即真相</p>
            </div>
            <div className="page-content">
              <WikiOverview />
            </div>
          </div>
        )}

        {activeTab?.type === 'note' && (
          <NoteEditor key={activeTab.key} tabKey={activeTab.key} title={activeTab.title} />
        )}

        {activeTab?.type === 'page' && activeTab.slug && (
          <div className="h-full">
            <WikiPageContent key={activeTab.slug} slug={activeTab.slug} />
          </div>
        )}

        {/* Empty state — all tabs closed */}
        {!activeTab && (
          <div className="flex items-center justify-center h-full text-text-muted">
            <div className="text-center">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-10 h-10 mx-auto mb-3 opacity-40">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
              </svg>
              <p className="text-sm">选择左侧页面，或点击上方 ＋ 新建标签页</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
