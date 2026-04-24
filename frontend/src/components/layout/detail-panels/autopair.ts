// ============================================================
// Auto-Pair Engine v3 — 配置驱动 + 策略模式
// ============================================================
// Design Patterns:
// - Strategy:    Each pairing behavior encapsulated as a strategy
// - Chain of Resp: Rules match by priority, short-circuit on success
// - Configuration-driven: Pluggable rule tables (OCP compliant)
// - Factory:     createAutoPairExtension() builds CM extension
// ============================================================

import { EditorView, keymap } from '@codemirror/view'
import { closeBrackets } from '@codemirror/autocomplete'

// ── Types ──────────────────────────────────────────────────────

interface PairStrategy {
  id: string
  trigger: string
  pair: string
  cursorOffset: number
  /** Custom handler (overrides default behavior) */
  customHandler?: (view: EditorView) => boolean | null
}

interface LinePrefixStrategy {
  id: string
  prefix: string
  append: string
  /** Max consecutive repeats (e.g. # max 6) */
  maxRepeat?: number
}

// ── Configuration Tables (Immutable by default) ────────────────

let inlinePairs: PairStrategy[] = [
  { id: 'backtick',   trigger: '`',  pair: '``',  cursorOffset: 1 },
  { id: 'asterisk',   trigger: '*',  pair: '**',  cursorOffset: 1 },
  { id: 'underscore', trigger: '_',  pair: '__',  cursorOffset: 1 },
  { id: 'tilde',      trigger: '~',  pair: '~~',  cursorOffset: 1 },
  { id: 'pipe',       trigger: '|',  pair: '|',   cursorOffset: 1 },
]

let linePrefixes: LinePrefixStrategy[] = [
  { id: 'heading',    prefix: '#', append: ' ', maxRepeat: 6 },
  { id: 'list_dash',  prefix: '-', append: ' ' },
  { id: 'quote',      prefix: '>', append: ' ' },
  { id: 'list_plus',  prefix: '+', append: ' ' },
  { id: 'list_star',  prefix: '*', append: ' ' },
]

// ── Extension Factory ──────────────────────────────────────────

/** Create auto-pair extension (brackets + Markdown rules) */
export function createAutoPairExtension() {
  return [
    // 1. Native bracket/quote closing (fastest, covers () [] {} "")
    closeBrackets(),

    // 2. Inline pair keymap — Strategy dispatch
    keymap.of(
      inlinePairs.map((rule) => ({
        key: rule.trigger,
        run: (view: EditorView) => {
          if (rule.customHandler) {
            const result = rule.customHandler(view)
            if (result !== null) return result
          }
          return handleInlinePair(view, rule)
        },
      }))
    ),

    // 3. Line prefix keymap — Strategy dispatch
    keymap.of(
      linePrefixes.map((rule) => ({
        key: rule.prefix,
        run: (view: EditorView) => handleLinePrefix(view, rule),
      }))
    ),
  ]
}

// ── Strategy: Inline Pair ──────────────────────────────────────

/**
 * Strategy: Wrap or pair inline symbols
 * Logic:
 *  1. Selection exists → wrap it
 *  2. Char after cursor matches → smart skip
 *  3. Normal → insert pair, center cursor
 */
function handleInlinePair(view: EditorView, rule: PairStrategy): boolean {
  const { state } = view
  const { from } = state.selection.main

  // 1. Selection → wrap
  if (!state.selection.main.empty) {
    const selected = state.sliceDoc(state.selection.main.from, state.selection.main.to)
    const wrapped = `${rule.trigger}${selected}${rule.trigger}`
    view.dispatch({
      changes: { from: state.selection.main.from, to: state.selection.main.to, insert: wrapped },
      selection: { anchor: state.selection.main.from + wrapped.length },
    })
    return true
  }

  // 2. Char after cursor matches → skip
  const charAfter = state.sliceDoc(from, from + 1)
  if (charAfter === rule.trigger) {
    view.dispatch({ selection: { anchor: from + 1 } })
    return true
  }

  // 3. Normal → insert pair
  view.dispatch({
    changes: { from, insert: rule.pair },
    selection: { anchor: from + rule.cursorOffset },
  })
  return true
}

// ── Strategy: Line Prefix ──────────────────────────────────────

/**
 * Strategy: Handle line-start prefixes
 * Logic:
 *  1. Heading upgrade (# → ## → ###) — if maxRepeat set
 *  2. Block if text exists (not at line start)
 *  3. Empty line → insert prefix + append
 */
function handleLinePrefix(view: EditorView, rule: LinePrefixStrategy): boolean {
  const { state } = view
  const { from } = state.selection.main
  const line = state.doc.lineAt(from)
  const textBefore = line.text.slice(0, from - line.from)
  const trimmed = textBefore.trim()

  // 1. Heading/Prefix upgrade logic
  if (rule.maxRepeat && isOnlyPrefix(trimmed, rule.prefix)) {
    return handlePrefixUpgrade(view, rule, trimmed, line)
  }

  // 2. Block if not at line start
  if (trimmed !== '') {
    return false
  }

  // 3. Empty line → insert prefix + append
  const newText = rule.prefix + rule.append
  view.dispatch({
    changes: { from, insert: newText },
    selection: { anchor: from + newText.length },
  })
  return true
}

/** Check if string consists ONLY of the prefix character */
function isOnlyPrefix(text: string, prefix: string): boolean {
  return text.length > 0 && text.split('').every((c) => c === prefix)
}

/** Handle prefix upgrade (e.g. # → ##) */
function handlePrefixUpgrade(
  view: EditorView,
  rule: LinePrefixStrategy,
  trimmed: string,
  line: { from: number }
): boolean {
  const count = trimmed.length

  if (count >= rule.maxRepeat!) {
    // Max level reached — don't consume the key, let CM insert it as normal char
    return false
  }

  // Upgrade: replace existing prefix with (count+1) prefix + append
  const newText = rule.prefix.repeat(count + 1) + rule.append
  view.dispatch({
    changes: { from: line.from, to: line.from + trimmed.length, insert: newText },
    selection: { anchor: line.from + newText.length },
  })
  return true
}

// ── Registry (Runtime Extension) ───────────────────────────────

/** Register a new inline pair rule */
export function registerInlinePair(strategy: PairStrategy): void {
  inlinePairs = [...inlinePairs, strategy]
}

/** Register a new line prefix rule */
export function registerLinePrefix(strategy: LinePrefixStrategy): void {
  linePrefixes = [...linePrefixes, strategy]
}

/** Reset rules to defaults (useful for testing) */
export function resetRules(): void {
  inlinePairs = [
    { id: 'backtick',   trigger: '`',  pair: '``',  cursorOffset: 1 },
    { id: 'asterisk',   trigger: '*',  pair: '**',  cursorOffset: 1 },
    { id: 'underscore', trigger: '_',  pair: '__',  cursorOffset: 1 },
    { id: 'tilde',      trigger: '~',  pair: '~~',  cursorOffset: 1 },
    { id: 'pipe',       trigger: '|',  pair: '|',   cursorOffset: 1 },
  ]
  linePrefixes = [
    { id: 'heading',    prefix: '#', append: ' ', maxRepeat: 6 },
    { id: 'list_dash',  prefix: '-', append: ' ' },
    { id: 'quote',      prefix: '>', append: ' ' },
    { id: 'list_plus',  prefix: '+', append: ' ' },
    { id: 'list_star',  prefix: '*', append: ' ' },
  ]
}
