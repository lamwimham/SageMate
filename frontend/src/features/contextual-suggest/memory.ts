import type { QueryResponse } from '@/types/chat'
import { normalizeForCompare, simpleHash } from './context'
import type { ContextualSuggestCandidate, SuggestionRecord } from './types'

export class ContextualSuggestMemory {
  private lastRequested: ContextualSuggestCandidate | null = null
  private lastShown: SuggestionRecord | null = null
  private recent: SuggestionRecord[] = []

  constructor(private readonly maxSize: number) {}

  getLastRequested(): ContextualSuggestCandidate | null {
    return this.lastRequested
  }

  getLastShown(): SuggestionRecord | null {
    return this.lastShown
  }

  markRequested(candidate: ContextualSuggestCandidate): void {
    this.lastRequested = candidate
  }

  rememberSuggestion(params: {
    candidate: ContextualSuggestCandidate
    answer: string
    relatedPages: QueryResponse['related_pages']
  }): SuggestionRecord {
    const record: SuggestionRecord = {
      candidateSignature: params.candidate.signature,
      candidateFingerprint: params.candidate.fingerprint,
      answerFingerprint: fingerprintAnswer(params.answer),
      sourceSignature: fingerprintSources(params.relatedPages),
      answer: params.answer,
      relatedPages: params.relatedPages,
      createdAt: Date.now(),
    }

    this.lastShown = record
    this.recent = [record, ...this.recent].slice(0, this.maxSize)
    return record
  }

  hasSeenCandidate(candidate: ContextualSuggestCandidate): boolean {
    return this.recent.some((item) => item.candidateSignature === candidate.signature)
  }

  hasSeenSources(relatedPages: QueryResponse['related_pages']): boolean {
    const sourceSignature = fingerprintSources(relatedPages)
    if (!sourceSignature) return false
    return this.recent.some((item) => item.sourceSignature === sourceSignature)
  }

  hasSimilarAnswer(answer: string): boolean {
    const fingerprint = fingerprintAnswer(answer)
    if (!fingerprint) return false
    return this.recent.some((item) => item.answerFingerprint === fingerprint)
  }

  getRecentSourceSlugs(limit = 16): string[] {
    const seen = new Set<string>()
    for (const item of this.recent) {
      for (const page of item.relatedPages || []) {
        if (page.slug) seen.add(page.slug)
        if (seen.size >= limit) return Array.from(seen)
      }
    }
    return Array.from(seen)
  }
}

export function fingerprintAnswer(answer: string): string {
  const normalized = normalizeForCompare(answer).slice(0, 600)
  return normalized ? simpleHash(normalized) : ''
}

export function fingerprintSources(relatedPages: QueryResponse['related_pages'] = []): string {
  const slugs = relatedPages.map((page) => page.slug).filter(Boolean).sort()
  return slugs.length ? simpleHash(slugs.join('|')) : ''
}
