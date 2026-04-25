/**
 * CodeMirror 6 Live Preview Plugin
 * 
 * 使用 @codemirror/lang-markdown 的语法树来识别 Markdown 元素，
 * 根据光标位置动态创建装饰。
 * 
 * 两类渲染逻辑：
 * 1. 封闭符号（`**bold**`, `` `code` ``, `*italic*`）：
 *    - 光标在符号内 → 编辑态（显示原始符号）
 *    - 光标离开 → 预览态（隐藏符号，渲染格式化内容）
 * 
 * 2. 开放符号（`#` 标题）：
 *    - 光标在该行任何位置（含行尾） → 显示 # 符号和标题文字
 *    - 光标离开该行 → 隐藏 # 符号，只显示标题文字（h1-h6 效果）
 */

import { ViewPlugin, ViewUpdate, Decoration, EditorView, DecorationSet } from '@codemirror/view'
import { syntaxTree } from '@codemirror/language'
import { Range, Text } from '@codemirror/state'

// ── Node Type Names ─────────────────────────────────────────────

const HEADING_TYPES = ['ATXHeading1', 'ATXHeading2', 'ATXHeading3', 'ATXHeading4', 'ATXHeading5', 'ATXHeading6']

const INLINE_TYPES: Record<string, { className: string; openerLen: number; closerLen: number }> = {
  InlineCode:       { className: 'live-preview--code',   openerLen: 1, closerLen: 1 },
  StrongEmphasis:   { className: 'live-preview--bold',   openerLen: 2, closerLen: 2 },
  Emphasis:         { className: 'live-preview--italic', openerLen: 1, closerLen: 1 },
  Strikethrough:    { className: 'live-preview--strike', openerLen: 2, closerLen: 2 },
}

const BLOCKQUOTE_MARKER = 'BlockquoteMarker'

// ── Decorator Helpers ──────────────────────────────────────────

function hideRange(from: number, to: number): Range<Decoration> {
  return Decoration.replace({ inclusive: true }).range(from, to)
}

function markRange(from: number, to: number, className: string): Range<Decoration> {
  return Decoration.mark({ class: className, inclusive: true }).range(from, to)
}

// ── Cursor Detection ───────────────────────────────────────────

/**
 * 检查光标是否在标题所在行
 * 只要在同行（含行尾），就视为"在标题内" → 显示 # 符号
 */
function cursorInHeadingLine(doc: Text, cursorPos: number, headingFrom: number): boolean {
  return doc.lineAt(cursorPos).number === doc.lineAt(headingFrom).number
}

/**
 * 检查光标是否在封闭符号节点内
 */
function cursorInInlineNode(cursorPos: number, from: number, to: number): boolean {
  return cursorPos >= from && cursorPos <= to
}

// ── Decorator Builder ──────────────────────────────────────────

function buildDecorations(view: EditorView): Range<Decoration>[] {
  const decorations: Range<Decoration>[] = []
  const { state } = view
  const doc = state.doc
  const cursorPos = state.selection.main.head
  const tree = syntaxTree(state)

  tree.iterate({
    enter: (node) => {
      const type = node.name
      const from = node.from
      const to = node.to

      // ── Headings ──────────────────────────────────────────────
      if (HEADING_TYPES.includes(type)) {
        const level = parseInt(type.replace('ATXHeading', ''), 10)
        const cursorInLine = cursorInHeadingLine(doc, cursorPos, from)

        if (!cursorInLine) {
          // 光标不在该行 → 隐藏 # 和空格
          const text = doc.sliceString(from, Math.min(to, from + 10))
          let contentStart = from
          for (let i = 0; i < text.length; i++) {
            if (text[i] !== '#' && text[i] !== ' ' && text[i] !== '\t') {
              contentStart = from + i
              break
            }
          }

          if (contentStart > from) {
            decorations.push(hideRange(from, contentStart))
          }
          if (to > contentStart) {
            decorations.push(markRange(contentStart, to, `live-preview--heading-${level}`))
          }
        } else {
          // 光标在该行 → 整行作为标题样式（显示 #）
          decorations.push(markRange(from, to, `live-preview--heading-${level}`))
        }

        return false
      }

      // ── Inline Elements ───────────────────────────────────────
      if (type in INLINE_TYPES) {
        const config = INLINE_TYPES[type]
        const cursorInNode = cursorInInlineNode(cursorPos, from, to)

        if (!cursorInNode) {
          const contentFrom = from + config.openerLen
          const contentTo = to - config.closerLen

          if (contentFrom < contentTo) {
            decorations.push(hideRange(from, from + config.openerLen))
            decorations.push(hideRange(to - config.closerLen, to))
            decorations.push(markRange(contentFrom, contentTo, config.className))
          }
        }

        return false
      }

      // ── Blockquote ────────────────────────────────────────────
      if (type === BLOCKQUOTE_MARKER) {
        const line = doc.lineAt(from)
        const cursorInLine = cursorPos >= line.from && cursorPos <= line.to

        if (!cursorInLine) {
          // Determine end of marker to hide ("> " or just ">")
          let hideTo = to
          if (to < line.to && doc.sliceString(to, to + 1) === ' ') {
            hideTo = to + 1
          }
          
          // Hide the marker
          decorations.push(hideRange(from, hideTo))
          
          // Style the line wrapper for border/background
          decorations.push(Decoration.line({ class: 'live-preview--blockquote' }).range(line.from, line.from))
          
          // Style the text content
          if (hideTo < line.to) {
            decorations.push(markRange(hideTo, line.to, 'live-preview--blockquote-text'))
          }
        }
        return false
      }

      return true
    }
  })

  return decorations
}

// ── View Plugin ────────────────────────────────────────────────

class LivePreviewState {
  decorations: DecorationSet

  constructor(view: EditorView) {
    this.decorations = Decoration.set(buildDecorations(view), true)
  }

  update(update: ViewUpdate) {
    if (update.docChanged || update.selectionSet) {
      this.decorations = Decoration.set(buildDecorations(update.view), true)
    }
  }
}

export const livePreviewPlugin = ViewPlugin.fromClass(LivePreviewState, {
  decorations: v => v.decorations,
})
