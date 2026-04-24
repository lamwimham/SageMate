// ============================================================
// Auto-Pair Engine — Markdown 符号自动补全与智能跳过
// ============================================================
// 设计原则:
// - 策略模式: 每种补全行为独立封装
// - 责任链: 规则按优先级匹配，短路退出
// - 配置驱动: 规则可插拔，符合开闭原则
// - 性能优先: 使用 CodeMirror keymap，零延迟响应
// ============================================================

import { EditorView, keymap } from '@codemirror/view'
import { closeBrackets } from '@codemirror/autocomplete'

// ── 规则定义 ───────────────────────────────────────────────────

interface PairRule {
  trigger: string
  pair: string           // 完整插入内容 (如 `` `` ``)
  cursorOffset: number   // 光标在 pair 中的偏移 (从 trigger 起点算)
  contextCheck?: (view: EditorView) => boolean
}

// ── 引擎工厂 ───────────────────────────────────────────────────

/** 创建自动补全扩展 (包含括号闭合 + Markdown 特定规则) */
export function createAutoPairExtension() {
  return [
    // 1. 原生括号/引号闭合 (性能最优)
    closeBrackets(),
    
    // 2. Markdown 特定配对
    keymap.of([
      { key: '`', run: (v) => handleInlinePair(v, { trigger: '`', pair: '``', cursorOffset: 1 }) },
      { key: '*', run: (v) => handleInlinePair(v, { trigger: '*', pair: '**', cursorOffset: 1 }) },
      { key: '~', run: (v) => handleTildePair(v) }, // 特殊处理删除线
    ]),
    
    // 3. 行首前缀补全
    keymap.of([
      { key: '#', run: (v) => handleLinePrefix(v, '#', ' ') },
      { key: '-', run: (v) => handleLinePrefix(v, '-', ' ') },
      { key: '>', run: (v) => handleLinePrefix(v, '>', ' ') },
      { key: '+', run: (v) => handleLinePrefix(v, '+', ' ') },
    ]),
  ]
}

// ── 策略执行器 ─────────────────────────────────────────────────

/**
 * 策略 1: 行内符号配对 (`` ` ``, `**`)
 */
function handleInlinePair(view: EditorView, rule: PairRule): boolean {
  const { state } = view
  const { from } = state.selection.main
  
  // 1. 有选中文本 -> 包裹
  if (!state.selection.main.empty) {
    const selected = state.sliceDoc(state.selection.main.from, state.selection.main.to)
    const wrapped = `${rule.trigger}${selected}${rule.trigger}`
    view.dispatch({
      changes: { from: state.selection.main.from, to: state.selection.main.to, insert: wrapped },
      selection: { anchor: state.selection.main.from + wrapped.length },
    })
    return true
  }

  // 2. 右侧已是配对符 -> 智能跳过
  const charAfter = state.sliceDoc(from, from + 1)
  if (charAfter === rule.trigger) {
    view.dispatch({ selection: { anchor: from + 1 } })
    return true
  }

  // 3. 正常配对 -> 插入 pair，光标置中
  view.dispatch({
    changes: { from, insert: rule.pair },
    selection: { anchor: from + rule.cursorOffset },
  })
  return true
}

/**
 * 策略 1.1: 删除线特殊处理 (~ -> ~~ -> ~~~~)
 */
function handleTildePair(view: EditorView): boolean {
  const { state } = view
  const { from } = state.selection.main
  const charBefore = state.sliceDoc(from - 1, from)
  const charAfter = state.sliceDoc(from, from + 1)

  if (!state.selection.main.empty) {
    const selected = state.sliceDoc(state.selection.main.from, state.selection.main.to)
    view.dispatch({
      changes: { from: state.selection.main.from, to: state.selection.main.to, insert: `~~${selected}~~` },
      selection: { anchor: state.selection.main.from + `~~${selected}~~`.length },
    })
    return true
  }

  // 如果前面紧挨着 ~，且后面不是 ~，则触发 ~~~~ 删除线
  if (charBefore === '~' && charAfter !== '~') {
    view.dispatch({
      changes: { from, insert: '~~' },
      selection: { anchor: from + 2 },
    })
    return true
  }

  // 如果后面是 ~，跳过
  if (charAfter === '~') {
    view.dispatch({ selection: { anchor: from + 1 } })
    return true
  }

  // 否则插入 ~~
  view.dispatch({
    changes: { from, insert: '~~' },
    selection: { anchor: from + 1 },
  })
  return true
}

/**
 * 策略 2: 行首前缀补全
 */
function handleLinePrefix(view: EditorView, prefix: string, append: string): boolean {
  const { state } = view
  const { from } = state.selection.main
  const line = state.doc.lineAt(from)
  const textBefore = line.text.slice(0, from - line.from)
  
  // 必须在行首（允许前导空白用于缩进）
  if (textBefore.trim() !== '' && textBefore.length > 0) {
    // 特殊: 如果已经在 `- ` 后面，允许继续 `- ` 创建新列表
    if (!textBefore.endsWith('- ') && !textBefore.endsWith('* ') && !textBefore.endsWith('+ ') && !textBefore.endsWith('> ')) {
      return false
    }
  }

  // 处理连续 # (## -> ### )
  if (prefix === '#' && textBefore.startsWith('#')) {
    const currentLevel = textBefore.length
    if (currentLevel < 6) {
      // 追加 # 并加空格
      view.dispatch({
        changes: { from, insert: append },
        selection: { anchor: from + append.length },
      })
      return true
    }
    return false
  }

  // 普通行首追加空格
  view.dispatch({
    changes: { from, insert: append },
    selection: { anchor: from + append.length },
  })
  return true
}
