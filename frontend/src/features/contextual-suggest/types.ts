import type { QueryResponse } from '@/types/chat'

export type ContextualSuggestPhase =
  | 'disabled'
  | 'idle'
  | 'observing'
  | 'scheduled'
  | 'in_flight'
  | 'cooldown'
  | 'suppressed'
  | 'error'

export type SuppressReason =
  | 'disabled'
  | 'content_too_short'
  | 'context_too_short'
  | 'same_signature'
  | 'small_delta'
  | 'not_growing'
  | 'cooldown'
  | 'in_flight'
  | 'duplicate_sources'
  | 'duplicate_answer'

export interface ContextualSuggestCandidate {
  pageSlug: string
  pageTitle: string
  content: string
  cursorContext: string
  existingLinks: string[]
  signature: string
  fingerprint: string
  contentLength: number
  createdAt: number
}

export interface ContextualSuggestState {
  phase: ContextualSuggestPhase
  answer: string
  error: string | null
  reason?: SuppressReason
}

export interface ContextualSuggestConfig {
  debounceMs: number
  cooldownMs: number
  noResultCooldownMs: number
  minContentLength: number
  minContextLength: number
  minDeltaChars: number
  minDeltaRatio: number
  recentMemorySize: number
}

export interface SuggestionRecord {
  candidateSignature: string
  candidateFingerprint: string
  answerFingerprint: string
  sourceSignature: string
  answer: string
  relatedPages: QueryResponse['related_pages']
  createdAt: number
}

export interface PolicyDecision {
  action: 'ignore' | 'schedule' | 'suppress' | 'defer'
  delayMs: number
  reason?: SuppressReason
}
