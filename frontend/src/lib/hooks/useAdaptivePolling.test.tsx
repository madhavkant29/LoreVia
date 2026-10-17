// @vitest-environment jsdom

import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useAdaptivePolling } from "./useAdaptivePolling"

describe("useAdaptivePolling", () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    vi.useFakeTimers()
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" })
    container = document.createElement("div")
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
    vi.useRealTimers()
  })

  it("backs off unchanged progress and resets after a progress change", async () => {
    const poll = vi.fn()
      .mockResolvedValueOnce({ progress: 1 })
      .mockResolvedValueOnce({ progress: 1 })
      .mockResolvedValueOnce({ progress: 2 })

    await render(<PollingProbe poll={poll} />)
    await flush()
    expect(poll).toHaveBeenCalledTimes(1)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100)
    })
    expect(poll).toHaveBeenCalledTimes(2)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(200)
    })
    expect(poll).toHaveBeenCalledTimes(3)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100)
    })
    expect(poll).toHaveBeenCalledTimes(4)
  })

  it("pauses while hidden and resumes immediately", async () => {
    const signals: AbortSignal[] = []
    const poll = vi.fn(async ({ signal }: { signal: AbortSignal }) => {
      signals.push(signal)
      return { progress: signals.length }
    })

    await render(<PollingProbe poll={poll} />)
    await flush()
    expect(poll).toHaveBeenCalledTimes(1)

    await act(async () => {
      Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" })
      document.dispatchEvent(new Event("visibilitychange"))
      await flush()
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_000)
    })
    expect(poll).toHaveBeenCalledTimes(1)

    await act(async () => {
      Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" })
      document.dispatchEvent(new Event("visibilitychange"))
      await flush()
    })
    expect(poll).toHaveBeenCalledTimes(2)
    expect(signals).toHaveLength(2)
  })

  it("aborts an in-flight request before starting a reset resource", async () => {
    const signals: AbortSignal[] = []
    const poll = vi.fn(({ signal }: { signal: AbortSignal }) => new Promise<{ progress: number }>((resolve, reject) => {
      signals.push(signal)
      signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")))
      if (signals.length > 1) resolve({ progress: 2 })
    }))

    await render(<PollingProbe poll={poll} resetKey="first" />)
    await flush()
    expect(poll).toHaveBeenCalledTimes(1)

    await act(async () => {
      root.render(<PollingProbe poll={poll} resetKey="second" />)
      await flush()
    })
    expect(signals[0]?.aborted).toBe(true)
    expect(poll).toHaveBeenCalledTimes(2)
  })

  it("stops after a terminal response", async () => {
    const poll = vi.fn().mockResolvedValue({ progress: 100, status: "ready" })
    await render(<PollingProbe poll={poll} terminal />)
    await flush()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000)
    })
    expect(poll).toHaveBeenCalledTimes(1)
    expect(container.textContent).toContain("terminal")
  })

  async function render(element: React.ReactNode) {
    await act(async () => {
      root.render(element)
      await flush()
    })
  }
})

function PollingProbe({
  poll,
  terminal = false,
  resetKey,
}: {
  poll: (context: { signal: AbortSignal }) => Promise<{ progress: number; status?: string }>
  terminal?: boolean
  resetKey?: string
}) {
  const state = useAdaptivePolling({
    poll,
    getProgress: (result) => result.progress,
    isTerminal: terminal ? (result) => result.status === "ready" : undefined,
    initialDelayMs: 100,
    maxDelayMs: 1_000,
    backoffMultiplier: 2,
    jitterRatio: 0,
    resetKey,
  })
  return <span>{state.isTerminal ? "terminal" : "active"}</span>
}

async function flush() {
  await Promise.resolve()
  await Promise.resolve()
  await Promise.resolve()
}
