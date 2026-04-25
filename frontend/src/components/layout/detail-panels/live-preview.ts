/**
 * CodeMirror 6 Live Preview Plugin
 * 
 * 使用 @codemirror/lang-markdown 的语法树来识别 Markdown 元素，
 * 根据光标位置动态创建装饰。
 * 
 * 渲染策略：
 * - 代码块/列表/分割线：样式始终渲染，符号显隐看光标
 * - 封闭符号（bold/italic/code/strike）：光标在节点内 → 显示原始符号
 * - 开放符号（heading/list mark）：光标在行内 → 显示原始符号
 */

import { ViewPlugin, ViewUpdate, Decoration, EditorView, DecorationSet, WidgetType } from '@codemirror/view'
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

const BLOCKQUOTE_MARKER = 'QuoteMark'
const FENCED_CODE = 'FencedCode'
const CODE_BLOCK = 'CodeBlock'
const THEMATIC_BREAK = 'ThematicBreak'
const BULLET_LIST = 'BulletList'
const ORDERED_LIST = 'OrderedList'
const LIST_ITEM = 'ListItem'
const TASK_MARKER = 'TaskMarker'
const LINK = 'Link'
const IMAGE = 'Image'

// ── Decorator Helpers ──────────────────────────────────────────

class HideWidget extends WidgetType {
  toDOM() { return document.createElement("span") }
}
const hideWidget = new HideWidget()

/** Language tag widget — shows language name above rendered code block */
class LanguageTagWidget extends WidgetType {
  private lang: string
  constructor(lang: string) { super(); this.lang = lang }
  toDOM() {
    const el = document.createElement("span")
    el.className = "live-preview--language-tag"
    el.textContent = this.lang
    return el
  }
  ignoreEvent() { return false }
  eq(other: LanguageTagWidget) { return this.lang === other.lang }
}

function hideRange(from: number, to: number): Range<Decoration> {
  return Decoration.mark({ class: 'cm-hide-text', inclusive: true }).range(from, to)
}

function markRange(from: number, to: number, className: string): Range<Decoration> {
  return Decoration.mark({ class: className, inclusive: true }).range(from, to)
}

// ── Cursor Detection ───────────────────────────────────────────

function cursorInLine(doc: Text, cursorPos: number, lineFrom: number): boolean {
  return doc.lineAt(cursorPos).number === doc.lineAt(lineFrom).number
}

function cursorInRange(cursorPos: number, from: number, to: number): boolean {
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
        const cursorInLine = doc.lineAt(cursorPos).number === doc.lineAt(from).number

        if (!cursorInLine) {
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
          decorations.push(markRange(from, to, `live-preview--heading-${level}`))
        }

        return false
      }

      // ── Inline Elements (bold/italic/code/strike) ─────────────
      if (type in INLINE_TYPES) {
        const config = INLINE_TYPES[type]
        const cursorInNode = cursorInRange(cursorPos, from, to)

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
          let hideTo = to
          if (to < line.to && doc.sliceString(to, to + 1) === ' ') {
            hideTo = to + 1
          }
          
          decorations.push(hideRange(from, hideTo))
          decorations.push(Decoration.line({ class: 'live-preview--blockquote' }).range(line.from, line.from))
          
          if (hideTo < line.to) {
            decorations.push(markRange(hideTo, line.to, 'live-preview--blockquote-text'))
          }
        }
        return false
      }

      // ── Fenced Code Block ─────────────────────────────────────
      if (type === FENCED_CODE) {
        handleFencedCode(node, doc, cursorPos, decorations)
        return false
      }

      // ── Indented Code Block ───────────────────────────────────
      if (type === CODE_BLOCK) {
        const cursorInBlock = cursorInRange(cursorPos, from, to)

        if (!cursorInBlock) {
          let lineFrom = from
          while (lineFrom < to) {
            const line = doc.lineAt(lineFrom)
            const lineEnd = Math.min(line.to, to)
            decorations.push(Decoration.line({ class: 'live-preview--code-block-line' }).range(line.from, line.from))
            if (line.from < lineEnd) {
              decorations.push(markRange(line.from, lineEnd, 'live-preview--code-block-text'))
            }
            lineFrom = line.to + 1
            if (lineFrom >= to) break
          }
        }

        return false
      }

      // ── Thematic Break (---, ***, ___) ────────────────────────
      if (type === THEMATIC_BREAK) {
        const line = doc.lineAt(from)
        const cursorInLine = cursorPos >= line.from && cursorPos <= line.to
        
        // 始终渲染分割线样式
        decorations.push(Decoration.line({ class: 'live-preview--thematic-break' }).range(line.from, line.from))
        
        // 光标离开 → 隐藏原始符号，渲染为真正的 hr
        if (!cursorInLine) {
          decorations.push(hideRange(from, to))
          decorations.push(Decoration.widget({
            widget: new HRWidget(),
            side: 1
          }).range(from))
        }
        
        return false
      }

      // ── Bullet List Markers (-, *, +) ─────────────────────────
      if (type === BULLET_LIST) {
        handleListItems(node, doc, cursorPos, decorations, 'bullet')
        return false
      }

      // ── Ordered List Markers (1., 2., ...) ───────────────────
      if (type === ORDERED_LIST) {
        handleListItems(node, doc, cursorPos, decorations, 'ordered')
        return false
      }

      // ── Task Marker ([x], [ ]) ────────────────────────────────
      if (type === TASK_MARKER) {
        const cursorInMarker = cursorInRange(cursorPos, from, to)
        
        if (!cursorInMarker) {
          decorations.push(hideRange(from, to))
          // Insert checkbox widget
          const isChecked = doc.sliceString(from, to).includes('x')
          decorations.push(Decoration.widget({
            widget: new CheckboxWidget(isChecked),
            side: 1
          }).range(from))
        }
        
        return false
      }

      // ── Link [text](url) ──────────────────────────────────────
      if (type === LINK) {
        handleLinkOrImage(node, doc, cursorPos, decorations, 'link')
        return false
      }

      // ── Image ![alt](url) ─────────────────────────────────────
      if (type === IMAGE) {
        handleLinkOrImage(node, doc, cursorPos, decorations, 'image')
        return false
      }

      // ── Table ─────────────────────────────────────────────────
      if (type === 'Table') {
        handleTable(node, doc, cursorPos, decorations)
        return false
      }

      return true
    }
  })

  return decorations
}

// ── Handlers ────────────────────────────────────────────────────

function handleFencedCode(node: any, doc: Text, cursorPos: number, decorations: Range<Decoration>[]) {
  const { from, to } = node
  const children = node.node.getChildren()
  
  let infoEnd = from
  let contentStart = from
  let contentEnd = to
  let closingMarkStart = -1
  let closingMarkEnd = to
  
  for (const child of children) {
    if (child.name === 'CodeMark') {
      if (infoEnd === from) {
        infoEnd = child.to
        while (infoEnd < to && doc.sliceString(infoEnd, infoEnd + 1) === ' ') {
          infoEnd++
        }
        contentStart = infoEnd
      } else {
        closingMarkStart = child.from
        closingMarkEnd = child.to
        contentEnd = child.from
      }
    }
  }
  
  const hasClosingMark = closingMarkStart >= 0
  const firstLine = doc.lineAt(from)
  const lastLine = hasClosingMark ? doc.lineAt(closingMarkStart) : null
  
  // 判断光标是否在代码块内
  const cursorInFirstLine = cursorInLine(doc, cursorPos, from)
  const cursorInBlock = hasClosingMark
    ? cursorInRange(cursorPos, from, to)
    : cursorInFirstLine
  
  // 提取语言标识
  let lang = ''
  if (infoEnd > from) {
    lang = doc.sliceString(from, infoEnd).trim()
    if (lang.startsWith('```')) {
      lang = lang.substring(3).trim()
    }
  }
  
  // 始终渲染代码块样式
  decorations.push(Decoration.line({ class: 'live-preview--fenced-code-line' }).range(firstLine.from, firstLine.from))
  
  let lineFrom = hasClosingMark ? firstLine.to + 1 : Math.max(contentStart, firstLine.to + 1)
  const limitPos = hasClosingMark ? closingMarkStart : to
  while (lineFrom < limitPos) {
    const line = doc.lineAt(lineFrom)
    const lineEnd = Math.min(line.to, hasClosingMark ? contentEnd : to)
    decorations.push(Decoration.line({ class: 'live-preview--fenced-code-line' }).range(line.from, line.from))
    if (line.from < lineEnd) {
      decorations.push(markRange(line.from, lineEnd, 'live-preview--fenced-code-text'))
    }
    lineFrom = line.to + 1
    if (lineFrom >= limitPos) break
  }
  
  if (hasClosingMark && closingMarkStart >= 0) {
    decorations.push(Decoration.line({ class: 'live-preview--fenced-code-line' }).range(closingMarkStart, closingMarkStart))
  }
        // 光标离开代码块 → 隐藏符号，显示语言标签
        if (!cursorInBlock) {
          // 隐藏开头整行（``` + 语言名）
          decorations.push(hideRange(from, firstLine.to))
          
          // 隐藏结尾整行（``` 可能带空格）
          if (hasClosingMark && closingMarkStart >= 0) {
            // 找到结尾 ``` 行的实际结束位置
            const closingLine = doc.lineAt(closingMarkStart)
            decorations.push(hideRange(closingLine.from, closingLine.to))
          }
    
    if (lang) {
      const widgetPos = hasClosingMark ? firstLine.to + 1 : Math.max(contentStart, firstLine.to + 1)
      decorations.push(Decoration.widget({ 
        widget: new LanguageTagWidget(lang), 
        side: 1 
      }).range(widgetPos))
    }
  }
}

function handleListItems(node: any, doc: Text, cursorPos: number, decorations: Range<Decoration>[], listType: 'bullet' | 'ordered') {
  const { from, to } = node
  const children = node.node.getChildren()
  
  // 遍历所有 ListItem 子节点
  for (const child of children) {
    if (child.name !== LIST_ITEM) continue
    
    const itemFrom = child.from
    const itemTo = child.to
    const cursorInItem = cursorInRange(cursorPos, itemFrom, itemTo)
    
    // 找到列表标记符（ListMark）
    const grandchildren = child.node.getChildren()
    for (const gc of grandchildren) {
      if (gc.name === 'ListMark' || gc.name === 'ListMarker') {
        const markFrom = gc.from
        const markTo = gc.to
        const cursorInMark = cursorInRange(cursorPos, markFrom, markTo)
        
        if (!cursorInMark) {
          // 隐藏列表标记符
          decorations.push(hideRange(markFrom, markTo))
          // 添加列表样式
          const markerText = doc.sliceString(markFrom, markTo)
          const isTaskList = markerText.includes('[')
          const styleClass = isTaskList ? 'live-preview--task-list-item' : `live-preview--list-item-${listType}`
          decorations.push(Decoration.line({ class: styleClass }).range(itemFrom, itemFrom))
        }
        break
      }
    }
  }
}

function handleLinkOrImage(node: any, doc: Text, cursorPos: number, decorations: Range<Decoration>[], kind: 'link' | 'image') {
  const { from, to } = node
  
  if (kind === 'image') {
    const cursorInNode = cursorInRange(cursorPos, from, to)
    
    if (!cursorInNode) {
      // 隐藏 ![alt](url) 整个语法，替换为图片预览
      decorations.push(hideRange(from, to))
      decorations.push(Decoration.widget({
        widget: new ImageWidget(doc.sliceString(from, to)),
        side: 1
      }).range(from))
    }
  } else {
    // Link: hide markdown syntax, show styled link text
    const children = node.node.getChildren()
    let labelFrom = -1
    let labelTo = -1
    let urlFrom = -1
    let urlTo = -1
    
    for (const child of children) {
      if (child.name === 'Label') {
        labelFrom = child.from
        labelTo = child.to
      }
      if (child.name === 'URL' || child.name === 'URLDestination') {
        urlFrom = child.from
        urlTo = child.to
      }
    }
    
    const cursorInNode = cursorInRange(cursorPos, from, to)
    
    if (!cursorInNode && labelFrom > 0) {
      // Hide [ ] and (url), style the label text
      decorations.push(hideRange(from, labelFrom + 1))
      if (urlFrom > 0) {
        decorations.push(hideRange(labelTo, to))
      }
      // Style the link label
      decorations.push(markRange(labelFrom + 1, labelTo - 1, 'live-preview--link'))
    }
  }
}

function handleTable(node: any, doc: Text, cursorPos: number, decorations: Range<Decoration>[]) {
  const { from, to } = node
  
  // Check if cursor is anywhere in the table
  const cursorInTable = cursorInRange(cursorPos, from, to)
  
  if (!cursorInTable) {
    // Hide table syntax markers: | and the delimiter row
    let pos = from
    while (pos < to) {
      const line = doc.lineAt(pos)
      const lineText = doc.sliceString(line.from, line.to)
      
      // Check if this is a delimiter row (|---|---|)
      const isDelimiterRow = /^\s*\|[\s\-:|]+\|?\s*$/.test(lineText)
      
      if (isDelimiterRow) {
        // Hide the entire delimiter row
        decorations.push(hideRange(line.from, line.to))
      } else {
        // Hide | markers on regular rows
        for (let i = 0; i < lineText.length; i++) {
          if (lineText[i] === '|') {
            const absPos = line.from + i
            decorations.push(hideRange(absPos, absPos + 1))
          }
        }
      }
      
      // Style table cells with subtle border
      if (!isDelimiterRow && lineText.includes('|')) {
        decorations.push(Decoration.line({ class: 'live-preview--table-row' }).range(line.from, line.from))
      }
      
      pos = line.to + 1
      if (pos >= to) break
    }
  }
}

// ── Widgets ─────────────────────────────────────────────────────

class HRWidget extends WidgetType {
  toDOM() {
    const el = document.createElement("hr")
    el.className = "live-preview--hr"
    return el
  }
  ignoreEvent() { return true }
  eq() { return true }
}

class CheckboxWidget extends WidgetType {
  private checked: boolean
  constructor(checked: boolean) { super(); this.checked = checked }
  toDOM() {
    const el = document.createElement("input")
    el.type = "checkbox"
    el.checked = this.checked
    el.disabled = true
    el.className = "live-preview--checkbox"
    return el
  }
  ignoreEvent() { return true }
  eq(other: CheckboxWidget) { return this.checked === other.checked }
}

class ImageWidget extends WidgetType {
  private raw: string
  constructor(raw: string) { super(); this.raw = raw }
  toDOM() {
    const el = document.createElement("div")
    el.className = "live-preview--image-placeholder"
    // Extract alt text and URL
    const match = this.raw.match(/!\[([^\]]*)\]\(([^)]+)\)/)
    if (match) {
      const alt = match[1]
      const url = match[2].split(' ')[0] // Remove title if present
      const img = document.createElement("img")
      img.src = url
      img.alt = alt
      img.className = "live-preview--image"
      img.onerror = () => {
        el.textContent = `[图片: ${alt}]`
        el.classList.add('live-preview--image-fallback')
      }
      el.appendChild(img)
    } else {
      el.textContent = "[图片]"
      el.classList.add('live-preview--image-fallback')
    }
    return el
  }
  ignoreEvent() { return true }
  eq(other: ImageWidget) { return this.raw === other.raw }
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
