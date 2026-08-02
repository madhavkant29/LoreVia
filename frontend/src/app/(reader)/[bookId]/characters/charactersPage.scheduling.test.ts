import { afterEach, describe, expect, it, vi } from "vitest"

import { scheduleIdleWork, scheduleTrackedTimeout } from "./charactersPage.scheduling"

describe("characters page scheduling helpers", () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it("tracks timeout ids and removes them after firing", () => {
    vi.useFakeTimers()
    const ids = new Set<number>()
    const callback = vi.fn()

    scheduleTrackedTimeout(ids, callback, 100)
    expect(ids.size).toBe(1)

    vi.advanceTimersByTime(100)
    expect(callback).toHaveBeenCalledTimes(1)
    expect(ids.size).toBe(0)
  })

  it("cancels fallback idle work", () => {
    vi.useFakeTimers()
    const callback = vi.fn()
    const mutableWindow = window as unknown as {
      requestIdleCallback?: typeof window.requestIdleCallback
      cancelIdleCallback?: typeof window.cancelIdleCallback
    }
    const originalRequestIdleCallback = mutableWindow.requestIdleCallback
    const originalCancelIdleCallback = mutableWindow.cancelIdleCallback
    delete mutableWindow.requestIdleCallback
    delete mutableWindow.cancelIdleCallback

    const cancel = scheduleIdleWork(callback, 100)
    cancel()
    vi.advanceTimersByTime(100)

    expect(callback).not.toHaveBeenCalled()
    mutableWindow.requestIdleCallback = originalRequestIdleCallback
    mutableWindow.cancelIdleCallback = originalCancelIdleCallback
  })
})
