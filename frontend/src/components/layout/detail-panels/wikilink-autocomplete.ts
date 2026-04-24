// ============================================================
// Wikilink Autocomplete — CodeMirror 6 自定义补全扩展
// ============================================================

import {
  autocompletion,
  CompletionContext,
  CompletionResult,
  Completion,
} from '@codemirror/autocomplete'
import { StateEffect, StateField } from '@codemirror/state'
import { Decoration, DecorationSet, EditorView } from '@codemirror/view'

// ── Wikilink Completion Source ─────────────────────────────────

interface WikiPageCompletion {
  slug: string
  title: string
  category: string
  summary: string
  isLinked: boolean
}

export function wikilinkAutocomplete(pages: WikiPageCompletion[]) {
  return autocompletion({
    override: [wikilinkCompletionSource(pages)],
    activateOnTyping: true,
    defaultKeymap: true,
  })
}

function wikilinkCompletionSource(pages: WikiPageCompletion[]) {
  return (context: CompletionContext): CompletionResult | null => {
    const cursor = context.pos
    const textBefore = context.state.doc.sliceString(0, cursor)
    
    // Match [[  or [[some-text
    const match = textBefore.match(/\[\[([^\]]*)$/)
    if (!match) return null
    
    const query = match[1].toLowerCase()
    const start = cursor - match[0].length
    
    // Filter and sort pages
    const completions: Completion[] = pages
      .filter((p) => {
        if (query.length === 0) return true
        return (
          p.title.toLowerCase().includes(query) ||
          p.slug.toLowerCase().includes(query) ||
          p.category.toLowerCase().includes(query)
        )
      })
      .sort((a, b) => {
        // Exact match first, then starts with, then includes
        const aExact = a.slug === query || a.title.toLowerCase() === query ? 0 : 1
        const bExact = b.slug === query || b.title.toLowerCase() === query ? 0 : 1
        if (aExact !== bExact) return aExact - bExact
        
        const aStarts = a.title.toLowerCase().startsWith(query) ? 0 : 1
        const bStarts = b.title.toLowerCase().startsWith(query) ? 0 : 1
        if (aStarts !== bStarts) return aStarts - bStarts
        
        return 0
      })
      .slice(0, 8) // Limit to 8 items
      .map((p) => ({
        label: p.title,
        detail: p.category,
        info: p.summary || p.slug,
        type: p.isLinked ? 'variable' : 'text',
        apply: (view: EditorView, _completion: Completion, from: number, _to: number) => {
          const insert = `[[${_completion.label}]]`
          view.dispatch({
            changes: { from, to: cursor, insert },
            selection: { anchor: from + insert.length },
          })
        },
      }))
    
    if (completions.length === 0) return null
    
    return {
      from: start,
      options: completions,
      validFor: /^\[\[[\w\-\u4e00-\u9fa5]*$/,
    }
  }
}

// ── Wikilink Decoration (highlighting in editor) ───────────────

const wikilinkHighlightEffect = StateEffect.define<{ ranges: { from: number; to: number }[] }>()

const wikilinkHighlightField = StateField.define<DecorationSet>({
  create() {
    return Decoration.none
  },
  update(highlights, tr) {
    highlights = highlights.map(tr.changes)
    for (const effect of tr.effects) {
      if (effect.is(wikilinkHighlightEffect)) {
        highlights = Decoration.set(
          effect.value.ranges.map((range) =>
            Decoration.mark({ class: 'cm-wikilink' }).range(range.from, range.to)
          )
        )
      }
    }
    return highlights
  },
  provide: (f) => EditorView.decorations.from(f),
})

function highlightWikilinks() {
  return EditorView.updateListener.of((update) => {
    if (update.docChanged || update.viewportChanged) {
      const highlights: { from: number; to: number }[] = []
      const text = update.state.doc.toString()
      const regex = /\[\[[^\]]+\]\]/g
      let match
      
      while ((match = regex.exec(text)) !== null) {
        highlights.push({ from: match.index, to: match.index + match[0].length })
      }
      
      update.view.dispatch({
        effects: wikilinkHighlightEffect.of({ ranges: highlights }),
      })
    }
  })
}

export function wikilinkHighlight() {
  return [
    wikilinkHighlightField,
    highlightWikilinks(),
  ]
}
