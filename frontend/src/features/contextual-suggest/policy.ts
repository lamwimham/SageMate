import { changedEnough } from './context'
import type { ContextualSuggestCandidate, ContextualSuggestConfig, PolicyDecision } from './types'
import { ContextualSuggestMemory } from './memory'

export const DEFAULT_CONTEXTUAL_SUGGEST_CONFIG: ContextualSuggestConfig = {
  debounceMs: 2200,
  cooldownMs: 18000,
  noResultCooldownMs: 8000,
  minContentLength: 80,
  minContextLength: 40,
  minDeltaChars: 120,
  minDeltaRatio: 0.18,
  recentMemorySize: 24,
}

export class ContextualSuggestPolicy {
  private cooldownUntil = 0

  constructor(
    private readonly memory: ContextualSuggestMemory,
    private readonly config: ContextualSuggestConfig = DEFAULT_CONTEXTUAL_SUGGEST_CONFIG
  ) {}

  evaluate(params: {
    enabled: boolean
    candidate: ContextualSuggestCandidate
    now: number
    isInFlight: boolean
  }): PolicyDecision {
    const { enabled, candidate, now, isInFlight } = params

    if (!enabled) return { action: 'ignore', delayMs: 0, reason: 'disabled' }
    if (candidate.content.trim().length < this.config.minContentLength) {
      return { action: 'ignore', delayMs: 0, reason: 'content_too_short' }
    }
    if (candidate.cursorContext.length < this.config.minContextLength) {
      return { action: 'ignore', delayMs: 0, reason: 'context_too_short' }
    }

    const lastRequested = this.memory.getLastRequested()
    if (lastRequested && candidate.contentLength <= lastRequested.contentLength) {
      return { action: 'suppress', delayMs: 0, reason: 'not_growing' }
    }

    if (lastRequested?.signature === candidate.signature || this.memory.hasSeenCandidate(candidate)) {
      return { action: 'suppress', delayMs: 0, reason: 'same_signature' }
    }

    if (lastRequested && !changedEnough(
      lastRequested.cursorContext,
      candidate.cursorContext,
      this.config.minDeltaChars,
      this.config.minDeltaRatio
    )) {
      return { action: 'suppress', delayMs: 0, reason: isInFlight ? 'in_flight' : 'small_delta' }
    }

    if (isInFlight) {
      return { action: 'defer', delayMs: this.config.debounceMs, reason: 'in_flight' }
    }

    if (now < this.cooldownUntil) {
      return { action: 'defer', delayMs: this.cooldownUntil - now + this.config.debounceMs, reason: 'cooldown' }
    }

    return { action: 'schedule', delayMs: this.config.debounceMs }
  }

  enterCooldown(hasVisibleSuggestion: boolean): void {
    const cooldown = hasVisibleSuggestion ? this.config.cooldownMs : this.config.noResultCooldownMs
    this.cooldownUntil = Date.now() + cooldown
  }

  getCooldownRemaining(now = Date.now()): number {
    return Math.max(0, this.cooldownUntil - now)
  }
}
