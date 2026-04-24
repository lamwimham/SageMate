import { useWikiTabsStore, type WikiTab } from '@/stores/wikiTabs'

/**
 * Wiki Tab Bar — 浏览器风格标签栏
 * 圆角顶部，活动标签与内容区融合
 */
export function WikiTabBar() {
  const { tabs, activeKey, activateTab, closeTab, openOverview } = useWikiTabsStore()

  if (tabs.length === 0) return null

  const handleTabClick = (tab: WikiTab) => {
    activateTab(tab.key)
  }

  const handleClose = (e: React.MouseEvent, key: string) => {
    e.stopPropagation()
    closeTab(key)
  }

  return (
    <div className="tab-bar">
      <div className="tab-bar__rail" />
      {tabs.map((tab) => {
        const isActive = tab.key === activeKey
        return (
          <button
            key={tab.key}
            onClick={() => handleTabClick(tab)}
            className={`browser-tab${isActive ? ' browser-tab--active' : ''}`}
          >
            <span className="browser-tab__icon">
              {tab.type === 'overview' ? '📋' : tab.type === 'note' ? '✏️' : '📄'}
            </span>
            <span className="browser-tab__title">{tab.title}</span>
            <span
              onClick={(e) => handleClose(e, tab.key)}
              className="browser-tab__close"
            >
              ×
            </span>
          </button>
        )
      })}
      {/* Re-open overview button when overview is closed */}
      {!tabs.find((t) => t.key === '__overview') && (
        <button
          onClick={() => openOverview()}
          className="tab-bar__add"
        >
          ＋ 概览
        </button>
      )}
    </div>
  )
}
