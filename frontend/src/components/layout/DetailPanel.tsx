import { useLayoutContext } from '@/layout/LayoutContext'
import { PageDetailPanel } from './detail-panels/PageDetailPanel'

/**
 * DetailPanel 容器 — 只负责渲染，内容由各页面通过 usePageLayout 声明
 * 新增页面无需修改此文件
 */
export function DetailPanel() {
  const { detailPanelContent } = useLayoutContext()

  return (
    <aside className="bg-bg-surface border-l border-border-subtle overflow-hidden flex flex-col" aria-label="详情面板">
      {detailPanelContent ?? <PageDetailPanel />}
    </aside>
  )
}
