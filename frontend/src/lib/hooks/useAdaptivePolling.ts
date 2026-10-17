"use client"

import { useCallback, useEffect, useRef, useState } from "react"

export type AdaptivePollContext = {
  signal: AbortSignal
}

type UseAdaptivePollingOptions<TResult> = {
  enabled?: boolean
  poll: (context: AdaptivePollContext) => Promise<TResult>
  getProgress?: (result: TResult) => unknown
  isTerminal?: (result: TResult) => boolean
  initialDelayMs?: number
  maxDelayMs?: number
  backoffMultiplier?: number
  jitterRatio?: number
  timeoutMs?: number
  resetKey?: unknown
  onError?: (error: unknown) => void
}

type AdaptivePollingState = {
  isPolling: boolean
  isTerminal: boolean
  timedOut: boolean
  error: unknown
  refresh: () => void
}

const UNSET_PROGRESS = Symbol("unset-progress")

function isDocumentVisible() {
  return typeof document === "undefined" || document.visibilityState === "visible"
}

function nextDelay(
  initialDelayMs: number,
  maxDelayMs: number,
  multiplier: number,
  attempt: number,
  jitterRatio: number,
) {
  const base = Math.min(maxDelayMs, initialDelayMs * multiplier ** Math.max(0, attempt))
  if (jitterRatio <= 0) return Math.round(base)
  const jitter = base * jitterRatio
  return Math.round(Math.max(0, base - jitter + Math.random() * jitter * 2))
}

/**
 * Poll a single resource without overlapping requests or continuing work in a
 * hidden tab. Repeated unchanged results back off; a changed progress value
 * resets the delay to keep active work responsive.
 */
export function useAdaptivePolling<TResult>(
  options: UseAdaptivePollingOptions<TResult>,
): AdaptivePollingState {
  const {
    enabled = true,
    poll,
    getProgress,
    isTerminal,
    initialDelayMs = 1_000,
    maxDelayMs = 30_000,
    backoffMultiplier = 1.75,
    jitterRatio = 0.15,
    timeoutMs,
    resetKey,
    onError,
  } = options
  const [visible, setVisible] = useState(isDocumentVisible)
  const [refreshVersion, setRefreshVersion] = useState(0)
  const [state, setState] = useState<Omit<AdaptivePollingState, "refresh">>({
    isPolling: false,
    isTerminal: false,
    timedOut: false,
    error: null,
  })
  const callbacksRef = useRef({ poll, getProgress, isTerminal, onError })
  const runtimeRef = useRef<{
    controller: AbortController | null
    inFlight: boolean
    pendingRun: (() => void) | null
  }>({ controller: null, inFlight: false, pendingRun: null })

  callbacksRef.current = { poll, getProgress, isTerminal, onError }

  const refresh = useCallback(() => {
    setRefreshVersion((current) => current + 1)
  }, [])

  useEffect(() => {
    if (typeof document === "undefined") return
    const handleVisibilityChange = () => setVisible(isDocumentVisible())
    document.addEventListener("visibilitychange", handleVisibilityChange)
    return () => document.removeEventListener("visibilitychange", handleVisibilityChange)
  }, [])

  useEffect(() => {
    if (!enabled || !visible) {
      setState((current) => ({ ...current, isPolling: false }))
      return
    }

    let disposed = false
    let stopped = false
    let timer: number | null = null
    let deadlineTimer: number | null = null
    let attempt = 0
    let previousProgress: unknown = UNSET_PROGRESS
    const startedAt = Date.now()
    const runtime = runtimeRef.current

    const clearTimers = () => {
      if (timer !== null) window.clearTimeout(timer)
      if (deadlineTimer !== null) window.clearTimeout(deadlineTimer)
      timer = null
      deadlineTimer = null
    }

    const stopForTimeout = () => {
      if (disposed || stopped) return
      stopped = true
      runtime.controller?.abort()
      setState((current) => ({
        ...current,
        isPolling: false,
        isTerminal: false,
        timedOut: true,
      }))
    }

    const schedule = (delayMs: number, run: () => void) => {
      if (disposed || stopped) return
      if (timeoutMs !== undefined && Date.now() - startedAt + delayMs >= timeoutMs) {
        stopForTimeout()
        return
      }
      timer = window.setTimeout(run, delayMs)
    }

    const run = () => {
      if (disposed || stopped) return
      if (timeoutMs !== undefined && Date.now() - startedAt >= timeoutMs) {
        stopForTimeout()
        return
      }

      if (runtime.inFlight) {
        runtime.controller?.abort()
        runtime.pendingRun = run
        return
      }

      const controller = new AbortController()
      runtime.inFlight = true
      runtime.controller = controller
      setState({ isPolling: true, isTerminal: false, timedOut: false, error: null })

      void (async () => {
        try {
          const result = await callbacksRef.current.poll({ signal: controller.signal })
          if (disposed || stopped || controller.signal.aborted) return

          if (callbacksRef.current.isTerminal?.(result)) {
            stopped = true
            setState({ isPolling: false, isTerminal: true, timedOut: false, error: null })
            return
          }

          const progress = callbacksRef.current.getProgress?.(result)
          const progressed = previousProgress === UNSET_PROGRESS || !Object.is(previousProgress, progress)
          previousProgress = progress
          attempt = progressed ? 0 : attempt + 1
          setState({ isPolling: false, isTerminal: false, timedOut: false, error: null })
          schedule(
            nextDelay(initialDelayMs, maxDelayMs, backoffMultiplier, attempt, jitterRatio),
            run,
          )
        } catch (error) {
          if (disposed || stopped || controller.signal.aborted) return
          attempt += 1
          callbacksRef.current.onError?.(error)
          setState({ isPolling: false, isTerminal: false, timedOut: false, error })
          schedule(
            nextDelay(initialDelayMs, maxDelayMs, backoffMultiplier, attempt, jitterRatio),
            run,
          )
        } finally {
          if (runtime.controller !== controller) return
          runtime.controller = null
          runtime.inFlight = false
          const pendingRun = runtime.pendingRun
          runtime.pendingRun = null
          pendingRun?.()
        }
      })()
    }

    if (timeoutMs !== undefined) {
      deadlineTimer = window.setTimeout(stopForTimeout, timeoutMs)
    }
    run()

    return () => {
      disposed = true
      clearTimers()
      if (runtime.pendingRun === run) {
        runtime.pendingRun = null
      }
      runtime.controller?.abort()
    }
  }, [
    backoffMultiplier,
    enabled,
    initialDelayMs,
    jitterRatio,
    maxDelayMs,
    refreshVersion,
    resetKey,
    timeoutMs,
    visible,
  ])

  return { ...state, refresh }
}
