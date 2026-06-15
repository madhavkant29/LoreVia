"use client"

import { useCallback, useEffect, useMemo, useState } from "react"

import { capture, captureTiming } from "@/lib/analytics/posthog"
import type { OptimisticDraft, SaveState } from "@/types/book"

export type OptimisticSaveOptions<TInput, TResult> = {
  storageKey: string
  save: (input: TInput) => Promise<TResult>
  getDraftId?: (input: TInput) => string
  onSuccess?: (result: TResult, input: TInput) => void
  onError?: (error: unknown, input: TInput) => void
  metricProperties?: Record<string, unknown>
}

export function useOptimisticSave<TInput, TResult>({
  storageKey,
  save,
  getDraftId,
  onSuccess,
  onError,
  metricProperties,
}: OptimisticSaveOptions<TInput, TResult>) {
  const [saveState, setSaveState] = useState<SaveState>("saved")
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null)
  const [pendingDraft, setPendingDraft] = useState<OptimisticDraft<TInput> | null>(() => readDraft<TInput>(storageKey))

  const hasPendingDraft = Boolean(pendingDraft)

  useEffect(() => {
    setPendingDraft(readDraft<TInput>(storageKey))
  }, [storageKey])

  const clearDraft = useCallback(() => {
    setPendingDraft(null)
    try {
      window.localStorage.removeItem(storageKey)
    } catch {
      // local draft persistence is best-effort
    }
  }, [storageKey])

  const persistDraft = useCallback((input: TInput, state: SaveState) => {
    const draft: OptimisticDraft<TInput> = {
      id: getDraftId?.(input) ?? "draft",
      value: input,
      saveState: state,
      updatedAt: new Date().toISOString(),
    }
    setPendingDraft(draft)
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(draft))
    } catch {
      // local draft persistence is best-effort
    }
  }, [getDraftId, storageKey])

  const runSave = useCallback(async (input: TInput, retry = false) => {
    const offline = typeof navigator !== "undefined" && navigator.onLine === false
    if (offline) {
      persistDraft(input, "offline_draft")
      setSaveState("offline_draft")
      return null
    }

    persistDraft(input, retry ? "retrying" : "saving")
    setSaveState(retry ? "retrying" : "saving")
    const startedAt = typeof performance !== "undefined" ? performance.now() : 0
    try {
      const result = await save(input)
      const savedAt = new Date().toISOString()
      clearDraft()
      setLastSavedAt(savedAt)
      setSaveState("saved")
      captureTiming("save_latency_ms", startedAt, { ...metricProperties, save_state: retry ? "retrying" : "saving" })
      onSuccess?.(result, input)
      return result
    } catch (error) {
      persistDraft(input, "error")
      setSaveState("error")
      captureTiming("save_latency_ms", startedAt, { ...metricProperties, save_state: "error" })
      capture("save_failure_count", metricProperties)
      onError?.(error, input)
      return null
    }
  }, [clearDraft, metricProperties, onError, onSuccess, persistDraft, save])

  const retry = useCallback(() => {
    if (!pendingDraft) return Promise.resolve(null)
    return runSave(pendingDraft.value, true)
  }, [pendingDraft, runSave])

  return useMemo(() => ({
    saveState,
    lastSavedAt,
    pendingDraft,
    hasPendingDraft,
    save: runSave,
    retry,
    clearDraft,
  }), [clearDraft, hasPendingDraft, lastSavedAt, pendingDraft, retry, runSave, saveState])
}

function readDraft<TInput>(storageKey: string): OptimisticDraft<TInput> | null {
  try {
    if (typeof window === "undefined") return null
    const raw = window.localStorage.getItem(storageKey)
    if (!raw) return null
    const parsed = JSON.parse(raw) as OptimisticDraft<TInput>
    return parsed && parsed.value ? parsed : null
  } catch {
    return null
  }
}
