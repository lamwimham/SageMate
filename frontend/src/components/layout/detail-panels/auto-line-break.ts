/**
 * CodeMirror 6 自动换行扩展
 * 
 * Markdown 的规范：单换行 `\n` 会被渲染为空格，需要 `  \n`（两个空格+换行）才能换行。
 * 用户在编辑器按回车，本意就是另起一行。此插件自动在回车前插入两个空格，
 * 确保预览模式下正确换行。
 */
import { ViewPlugin, EditorView } from '@codemirror/view'

export const autoLineBreak = ViewPlugin.fromClass(
  class {
    private handler: (e: KeyboardEvent) => void
    private view: EditorView

    constructor(view: EditorView) {
      this.view = view
      this.handler = (e: KeyboardEvent) => {
        if (e.key !== 'Enter') return
        if (e.ctrlKey || e.metaKey || e.altKey) return

        const { state } = this.view
        const changes: Array<{ from: number; insert: string }> = []
        
        for (const range of state.selection.ranges) {
          if (range.empty) {
            // 防重检测：检查光标前两个字符是否已经是两个空格
            const textBeforeCursor = state.doc.sliceString(range.head - 2, range.head)
            if (textBeforeCursor === '  ') continue

            const line = state.doc.lineAt(range.head)
            const textBefore = line.text.slice(0, range.head - line.from)

            // 有实际内容，且末尾还没有两个空格
            if (textBefore.trim().length > 0 && !textBefore.endsWith('  ')) {
              changes.push({ from: range.head, insert: '  ' })
            }
          }
        }
        
        if (changes.length > 0) {
          this.view.dispatch({ changes })
        }
      }

      // 绑定在 contentDOM 上，捕获阶段触发
      this.view.contentDOM.addEventListener('keydown', this.handler, true)
    }

    destroy() {
      this.view.contentDOM.removeEventListener('keydown', this.handler, true)
    }
  }
)
