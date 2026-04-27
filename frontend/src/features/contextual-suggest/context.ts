import type { ContextualSuggestCandidate } from './types'

const SIGNATURE_CONTEXT_CHARS = 360
const FINGERPRINT_CONTEXT_CHARS = 900

export function normalizeForCompare(value: string): string {
  return value
    .toLowerCase()
    .replace(/\[\[([^\]]+)\]\]/g, '$1')
    .replace(/[`*_#>\-\d.()[\]{}:;,.!?，。！？、：；（）【】《》]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

export function simpleHash(value: string): string {
  let hash = 2166136261
  for (let i = 0; i < value.length; i += 1) {
    hash ^= value.charCodeAt(i)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0).toString(36)
}

export function extractCursorContext(content: string, cursorOffset: number, minContextLength: number): string {
  const cursor = Math.max(0, Math.min(cursorOffset, content.length))
  const before = content.slice(0, cursor)
  const after = content.slice(cursor)
  const paragraphStart = Math.max(before.lastIndexOf('\n\n'), before.lastIndexOf('\r\n\r\n'), 0)
  const paragraphEndRel = after.search(/\n\s*\n/)
  const paragraphEnd = paragraphEndRel >= 0 ? cursor + paragraphEndRel : content.length
  const paragraph = content.slice(paragraphStart, paragraphEnd).trim()

  if (paragraph.length >= minContextLength) {
    return paragraph.slice(-1200)
  }

  const start = Math.max(0, cursor - 700)
  const end = Math.min(content.length, cursor + 500)
  return content.slice(start, end).trim()
}

export function extractExistingLinks(content: string): string[] {
  return Array.from(content.matchAll(/\[\[([^\]]+)\]\]/g), (m) => m[1])
}

export function createContextualCandidate(params: {
  pageSlug: string
  pageTitle: string
  content: string
  cursorOffset: number
  minContextLength: number
}): ContextualSuggestCandidate {
  const cursorContext = extractCursorContext(params.content, params.cursorOffset, params.minContextLength)
  const normalizedContext = normalizeForCompare(cursorContext)
  const signatureContext = normalizedContext.slice(-SIGNATURE_CONTEXT_CHARS)
  const fingerprintContext = normalizedContext.slice(-FINGERPRINT_CONTEXT_CHARS)
  const pageSlug = params.pageSlug || params.pageTitle || 'untitled'

  return {
    pageSlug,
    pageTitle: params.pageTitle || pageSlug,
    content: params.content,
    cursorContext,
    existingLinks: extractExistingLinks(params.content),
    signature: `${pageSlug}:${simpleHash(signatureContext)}`,
    fingerprint: simpleHash(`${pageSlug}:${fingerprintContext}`),
    contentLength: params.content.length,
    createdAt: Date.now(),
  }
}

export function changedEnough(previous: string | null, next: string, minChars: number, minRatio: number): boolean {
  if (!previous) return true
  if (previous === next) return false

  const shared = commonPrefixLength(previous, next)
  const delta = Math.abs(next.length - previous.length) + Math.max(previous.length, next.length) - shared
  const ratio = delta / Math.max(next.length, previous.length, 1)
  return delta >= minChars || ratio >= minRatio
}

function commonPrefixLength(a: string, b: string): number {
  const max = Math.min(a.length, b.length)
  let i = 0
  while (i < max && a[i] === b[i]) i += 1
  return i
}
