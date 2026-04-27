import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { chatRepo } from '@/api/repositories'
import { useWikiQAStore } from '@/stores/wikiQA'
import type { AgentChatStreamEvent, QueryResponse } from '@/types/chat'
import { createContextualCandidate } from '@/features/contextual-suggest/context'
import { ContextualSuggestMemory } from '@/features/contextual-suggest/memory'
import { ContextualSuggestPolicy, DEFAULT_CONTEXTUAL_SUGGEST_CONFIG } from '@/features/contextual-suggest/policy'
import type {
  ContextualSuggestCandidate,
  ContextualSuggestState,
  SuppressReason,
} from '@/features/contextual-suggest/types'

interface UseContextualSuggestOptions {
  enabled: boolean
  pageSlug: string
  pageTitle: string
  content: string
  cursorOffset: number
}

interface InFlightRequest {
  requestId: number
  candidate: ContextualSuggestCandidate
  abort: AbortController
}

const config = DEFAULT_CONTEXTUAL_SUGGEST_CONFIG

function nextMessageId() {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `contextual_${Date.now()}_${Math.random().toString(36).slice(2)}`
}

export function useContextualSuggest({
  enabled,
  pageSlug,
  pageTitle,
  content,
  cursorOffset,
}: UseContextualSuggestOptions) {
  const [state, setState] = useState<ContextualSuggestState>({
    phase: enabled ? 'idle' : 'disabled',
    answer: '',
    error: null,
  })

  const addMessage = useWikiQAStore((s) => s.addMessage)
  const updateMessage = useWikiQAStore((s) => s.updateMessage)
  const appendToMessage = useWikiQAStore((s) => s.appendToMessage)

  const memoryRef = useRef<ContextualSuggestMemory | null>(null)
  if (!memoryRef.current) {
    memoryRef.current = new ContextualSuggestMemory(config.recentMemorySize)
  }

  const policyRef = useRef<ContextualSuggestPolicy | null>(null)
  if (!policyRef.current) {
    policyRef.current = new ContextualSuggestPolicy(memoryRef.current, config)
  }

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const inFlightRef = useRef<InFlightRequest | null>(null)
  const pendingCandidateRef = useRef<ContextualSuggestCandidate | null>(null)
  const requestIdRef = useRef(0)
  const enabledSessionRef = useRef(false)
  const baselineKeyRef = useRef('')

  const candidate = useMemo(
    () => createContextualCandidate({
      pageSlug,
      pageTitle,
      content,
      cursorOffset,
      minContextLength: config.minContextLength,
    }),
    [content, cursorOffset, pageSlug, pageTitle]
  )

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const stopAll = useCallback(() => {
    clearTimer()
    inFlightRef.current?.abort.abort()
    inFlightRef.current = null
    pendingCandidateRef.current = null
  }, [clearTimer])

  const startRequest = useCallback(async (requestCandidate: ContextualSuggestCandidate) => {
    if (inFlightRef.current) {
      pendingCandidateRef.current = requestCandidate
      setState((prev) => ({ ...prev, phase: 'observing', reason: 'in_flight' }))
      return
    }

    clearTimer()
    const requestId = requestIdRef.current + 1
    requestIdRef.current = requestId
    const abort = new AbortController()
    inFlightRef.current = { requestId, candidate: requestCandidate, abort }
    memoryRef.current?.markRequested(requestCandidate)
    setState({ phase: 'in_flight', answer: '', error: null })

    let answer = ''
    let messageStarted = false
    let messageId = ''
    let relatedPages: QueryResponse['related_pages'] = []
    let visibleSuggestion = false
    let suppressReason: SuppressReason | undefined

    const ensureMessageStarted = () => {
      if (messageStarted) return
      messageStarted = true
      messageId = nextMessageId()
      addMessage({
        id: messageId,
        role: 'assistant',
        content: '',
        contentType: 'contextual_suggestion',
        timestamp: Date.now(),
        related_pages: relatedPages || [],
        isPending: true,
      })
    }

    const finishRequest = (hasVisibleSuggestion: boolean) => {
      inFlightRef.current = null
      policyRef.current?.enterCooldown(hasVisibleSuggestion)

      const pending = pendingCandidateRef.current
      pendingCandidateRef.current = null
      if (!pending) return

      const decision = policyRef.current?.evaluate({
        enabled,
        candidate: pending,
        now: Date.now(),
        isInFlight: false,
      })

      if (decision?.action === 'schedule' || decision?.action === 'defer') {
        timerRef.current = setTimeout(() => {
          void startRequest(pending)
        }, decision.delayMs)
        setState((prev) => ({ ...prev, phase: decision.reason === 'cooldown' ? 'cooldown' : 'scheduled', reason: decision.reason }))
      }
    }

    try {
      const payload = {
        channel: 'web' as const,
        user_id: 'wiki-editor',
        content_type: 'text' as const,
        text: requestCandidate.cursorContext,
        raw_data: {
          intent: 'contextual_suggest',
          page_slug: requestCandidate.pageSlug,
          page_title: requestCandidate.pageTitle,
          cursor_context: requestCandidate.cursorContext,
          full_content: requestCandidate.content.slice(-8000),
          existing_links: requestCandidate.existingLinks,
          recent_suggestion_slugs: memoryRef.current?.getRecentSourceSlugs() || [],
        },
      }

      for await (const event of chatRepo.chatStream(payload, abort.signal)) {
        if (requestId !== requestIdRef.current) return
        const e = event as AgentChatStreamEvent

        if (e.type === 'status') {
          setState((prev) => ({ ...prev, phase: 'in_flight' }))
        } else if (e.type === 'sources') {
          relatedPages = e.sources || []
          if (memoryRef.current?.hasSeenSources(relatedPages)) {
            suppressReason = 'duplicate_sources'
            abort.abort()
            setState({ phase: 'suppressed', answer: '', error: null, reason: suppressReason })
            return
          }
          if (messageStarted) {
            updateMessage(messageId, { related_pages: relatedPages })
          }
        } else if (e.type === 'token') {
          answer += e.token
          if (answer.trim()) {
            ensureMessageStarted()
            appendToMessage(messageId, e.token)
          }
        } else if (e.type === 'done') {
          const finalAnswer = (e.answer || answer).trim()
          relatedPages = e.related_pages || relatedPages || []

          if (!finalAnswer) {
            setState({ phase: 'cooldown', answer: '', error: null })
            return
          }

          if (!messageStarted && memoryRef.current?.hasSimilarAnswer(finalAnswer)) {
            suppressReason = 'duplicate_answer'
            setState({ phase: 'suppressed', answer: '', error: null, reason: suppressReason })
            return
          }

          visibleSuggestion = true
          memoryRef.current?.rememberSuggestion({
            candidate: requestCandidate,
            answer: finalAnswer,
            relatedPages,
          })

          if (messageStarted) {
            updateMessage(messageId, {
              content: finalAnswer,
              related_pages: relatedPages,
              isPending: false,
            })
          } else {
            addMessage({
              id: nextMessageId(),
              role: 'assistant',
              content: finalAnswer,
              contentType: 'contextual_suggestion',
              timestamp: Date.now(),
              related_pages: relatedPages,
              isPending: false,
            })
          }

          setState({ phase: 'cooldown', answer: finalAnswer, error: null })
          return
        } else if (e.type === 'error') {
          setState({ phase: 'error', answer: '', error: e.message })
          return
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setState({ phase: 'error', answer: '', error: (err as Error).message })
      } else if (suppressReason) {
        setState({ phase: 'suppressed', answer: '', error: null, reason: suppressReason })
      }
    } finally {
      finishRequest(visibleSuggestion)
    }
  }, [addMessage, appendToMessage, clearTimer, enabled, updateMessage])

  const scheduleCandidate = useCallback((nextCandidate: ContextualSuggestCandidate, delayMs: number, reason?: SuppressReason) => {
    clearTimer()
    timerRef.current = setTimeout(() => {
      void startRequest(nextCandidate)
    }, delayMs)
    setState((prev) => ({
      ...prev,
      phase: reason === 'cooldown' ? 'cooldown' : 'scheduled',
      reason,
      error: null,
    }))
  }, [clearTimer, startRequest])

  useEffect(() => {
    if (!enabled) {
      enabledSessionRef.current = false
      baselineKeyRef.current = ''
      return
    }

    const baselineKey = `${candidate.pageSlug}:${candidate.pageTitle}`
    if (!enabledSessionRef.current || baselineKeyRef.current !== baselineKey) {
      enabledSessionRef.current = true
      baselineKeyRef.current = baselineKey
      pendingCandidateRef.current = null
      clearTimer()
      memoryRef.current?.markRequested(candidate)
      setState({ phase: 'idle', answer: '', error: null })
    }
  }, [candidate, clearTimer, enabled])

  useEffect(() => {
    clearTimer()

    const decision = policyRef.current?.evaluate({
      enabled,
      candidate,
      now: Date.now(),
      isInFlight: Boolean(inFlightRef.current),
    })

    if (!decision || decision.action === 'ignore') {
      if (!enabled) {
        stopAll()
        setState({ phase: 'disabled', answer: '', error: null, reason: 'disabled' })
      } else {
        setState((prev) => ({ ...prev, phase: 'idle', error: null, reason: decision?.reason }))
      }
      return
    }

    if (decision.action === 'suppress') {
      setState((prev) => ({ ...prev, phase: 'suppressed', error: null, reason: decision.reason }))
      return
    }

    if (decision.action === 'defer') {
      pendingCandidateRef.current = candidate
      if (!inFlightRef.current) {
        scheduleCandidate(candidate, decision.delayMs, decision.reason)
      } else {
        setState((prev) => ({ ...prev, phase: 'observing', error: null, reason: decision.reason }))
      }
      return
    }

    scheduleCandidate(candidate, decision.delayMs, decision.reason)
  }, [candidate, clearTimer, enabled, scheduleCandidate, stopAll])

  useEffect(() => stopAll, [stopAll])

  return {
    ...state,
    cancel: stopAll,
    isActive: state.phase !== 'idle' && state.phase !== 'disabled',
  }
}
