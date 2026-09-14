import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const socialApiMock = vi.hoisted(() => ({ getConversationUnreadCount: vi.fn() }))
const readerApiMock = vi.hoisted(() => ({ getRecall: vi.fn() }))
const authState = vi.hoisted(() => ({ user: { id: "user-1" } as { id: string } | null, hydrated: true }))

vi.mock("@/lib/api/social", () => ({ socialApi: socialApiMock }))
vi.mock("@/lib/api/reader", () => ({ readerApi: readerApiMock }))
vi.mock("@/lib/stores/authStore", () => ({ useAuthStore: () => authState }))

import { emitChatsChanged, useChatUnreadCount } from "./useChatUnreadCount"
import { useRecall } from "./useRecall"

describe("runtime notification hooks", () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    authState.user = { id: "user-1" }
    authState.hydrated = true
    socialApiMock.getConversationUnreadCount.mockReset().mockResolvedValue({ unread_count: 4 })
    readerApiMock.getRecall.mockReset().mockResolvedValue({ recall: "Mara found the key.", last_chapter: 3 })
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

  it("refreshes chat unread counts from initial, custom, focus, visibility, and polling triggers", async () => {
    vi.useFakeTimers()
    await render(<ChatProbe />)
    await flushTimers()
    expect(container.textContent).toContain("4|ready")

    socialApiMock.getConversationUnreadCount.mockResolvedValue({ unread_count: 7 })
    await act(async () => {
      emitChatsChanged()
      window.dispatchEvent(new Event("focus"))
      Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" })
      document.dispatchEvent(new Event("visibilitychange"))
      Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" })
      document.dispatchEvent(new Event("visibilitychange"))
      await vi.advanceTimersByTimeAsync(1000)
    })
    expect(container.textContent).toContain("7|ready")
    // Visibility and focus signals are coalesced while the prior request is
    // in flight, so a busy tab does not fan out duplicate requests.
    expect(socialApiMock.getConversationUnreadCount.mock.calls.length).toBeGreaterThanOrEqual(2)

    socialApiMock.getConversationUnreadCount.mockRejectedValue(new Error("offline"))
    await act(async () => {
      emitChatsChanged()
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(container.textContent).toContain("7|ready")
  })

  it("returns zero for signed-out users and respects disabled hydration", async () => {
    authState.user = null
    authState.hydrated = false
    await render(<ChatProbe disabled />)
    await tick()
    expect(container.textContent).toContain("0|pending")
    expect(socialApiMock.getConversationUnreadCount).not.toHaveBeenCalled()
    act(() => emitChatsChanged())
    expect(container.textContent).toContain("0|pending")
  })

  it("does not retry a failed one-shot unread refresh", async () => {
    vi.useFakeTimers()
    socialApiMock.getConversationUnreadCount.mockRejectedValue(new Error("offline"))

    await render(<ChatOneShotProbe />)
    await flushTimers()
    expect(socialApiMock.getConversationUnreadCount).toHaveBeenCalledTimes(1)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(120_000)
    })
    expect(socialApiMock.getConversationUnreadCount).toHaveBeenCalledTimes(1)
  })

  it("loads and dismisses recall while tolerating empty and failed responses", async () => {
    await render(<RecallProbe bookId="book-1" />)
    await waitForText("Mara found the key.|3|shown")
    act(() => container.querySelector("button")?.click())
    expect(container.textContent).toContain("hidden")

    readerApiMock.getRecall.mockResolvedValue({ recall: null, last_chapter: null })
    await act(async () => {
      root.render(<RecallProbe key="book-2" bookId="book-2" />)
      await tick()
    })
    expect(container.textContent).toContain("none|null|hidden")

    readerApiMock.getRecall.mockRejectedValue(new Error("offline"))
    await act(async () => {
      root.render(<RecallProbe key="book-3" bookId="book-3" />)
      await tick()
    })
    expect(container.textContent).toContain("none|null|hidden")
  })

  async function render(child: React.ReactNode) {
    await act(async () => {
      root.render(child)
      await tick()
    })
  }

  async function waitForText(text: string) {
    for (let index = 0; index < 20; index += 1) {
      if (container.textContent?.includes(text)) return
      await act(tick)
    }
    throw new Error(`Missing ${text}: ${container.textContent}`)
  }
})

function ChatProbe({ disabled = false }: { disabled?: boolean }) {
  const state = useChatUnreadCount({ enabled: !disabled, pollMs: 1000, refreshOnFocus: true })
  return <span>{state.unreadCount}|{state.hydrated ? "ready" : "pending"}</span>
}

function ChatOneShotProbe() {
  const state = useChatUnreadCount({ pollMs: false })
  return <span>{state.unreadCount}|{state.hydrated ? "ready" : "pending"}</span>
}

function RecallProbe({ bookId }: { bookId: string }) {
  const state = useRecall(bookId)
  return <div>{state.recall ?? "none"}|{state.lastChapter ?? "null"}|{state.show ? "shown" : "hidden"}<button onClick={state.dismiss}>Dismiss</button></div>
}

async function tick() {
  await Promise.resolve()
  await Promise.resolve()
}

async function flushTimers() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0)
    await Promise.resolve()
  })
}
