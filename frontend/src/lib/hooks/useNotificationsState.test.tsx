import React, { act } from "react"
import { type InfiniteData, QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { asQueryKey, notificationsCacheKey } from "@/lib/query/cacheKeys"
import type { NotificationListResponse } from "@/types/notifications"

const notificationsApiMock = vi.hoisted(() => ({
  list: vi.fn(),
  markRead: vi.fn(),
  markAllRead: vi.fn(),
}))
const authState = vi.hoisted(() => ({ user: { id: "user-1" } as { id: string } | null }))

vi.mock("@/lib/api/notifications", () => ({ notificationsApi: notificationsApiMock }))
vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: (selector: (state: typeof authState) => unknown) => selector(authState),
}))

import { useNotifications, useNotificationsState } from "./useNotifications"

const unread = {
  id: "notification-1",
  book_id: "book-1",
  kind: "revision_digest",
  title: "Revision risk",
  body: "Review the downstream edit.",
  data: null,
  read_at: null,
  created_at: "2026-06-15T09:00:00Z",
}

describe("useNotificationsState runtime behavior", () => {
  let container: HTMLDivElement
  let root: Root
  let queryClient: QueryClient

  beforeEach(() => {
    authState.user = { id: "user-1" }
    notificationsApiMock.list.mockReset().mockResolvedValue({
      items: [unread], unread_count: 1, next_cursor: null, has_more: false,
    })
    notificationsApiMock.markRead.mockReset().mockResolvedValue({ ...unread, read_at: "2026-06-15T09:05:00Z" })
    notificationsApiMock.markAllRead.mockReset().mockResolvedValue({
      items: [{ ...unread, read_at: "2026-06-15T09:10:00Z" }],
      unread_count: 0,
      next_cursor: null,
      has_more: false,
    })
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" })
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    container = document.createElement("div")
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => root.unmount())
    queryClient.clear()
    container.remove()
  })

  it("loads, marks one and all read, and refreshes from app, focus, and visibility events", async () => {
    await render(<Probe />)
    await waitForText("Revision risk|1")
    expect(notificationsApiMock.list).toHaveBeenCalledWith(5, expect.objectContaining({ cursor: null }))

    notificationsApiMock.list.mockResolvedValue({
      items: [{ ...unread, read_at: "2026-06-15T09:05:00Z" }],
      unread_count: 0,
      next_cursor: null,
      has_more: false,
    })
    await click("Mark one")
    await waitForText("Revision risk|0")
    expect(notificationsApiMock.markRead).toHaveBeenCalledWith("notification-1")

    await click("Mark all")
    await waitForText("Revision risk|0")
    expect(notificationsApiMock.markAllRead).toHaveBeenCalled()

    const callsBeforeEvents = notificationsApiMock.list.mock.calls.length
    await act(async () => {
      window.dispatchEvent(new Event("notifications:changed"))
      window.dispatchEvent(new Event("focus"))
      Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" })
      document.dispatchEvent(new Event("visibilitychange"))
      Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" })
      document.dispatchEvent(new Event("visibilitychange"))
      await tick()
    })
    expect(notificationsApiMock.list.mock.calls.length).toBeGreaterThan(callsBeforeEvents)
  })

  it("keeps manual pagination working after the adaptive poll seeds the first page", async () => {
    const older = {
      ...unread,
      id: "notification-older",
      title: "Older revision risk",
      created_at: "2026-06-14T09:00:00Z",
    }
    notificationsApiMock.list.mockImplementation((_limit, options) => Promise.resolve(
      options?.cursor
        ? { items: [older], unread_count: 1, next_cursor: null, has_more: false }
        : { items: [unread], unread_count: 1, next_cursor: "older-page", has_more: true },
    ))

    await render(<Probe />)
    await waitForText("Revision risk|1")
    await click("Load more")
    await waitForText("Older revision risk")
    expect(notificationsApiMock.list).toHaveBeenLastCalledWith(
      5,
      expect.objectContaining({ cursor: "older-page" }),
    )
  })

  it("aborts an in-flight notification poll in a hidden tab and resumes when visible", async () => {
    const signals: AbortSignal[] = []
    notificationsApiMock.list.mockImplementation((_limit, options) => new Promise((_, reject) => {
      const signal = options?.signal
      if (!signal) throw new Error("expected an abort signal")
      signals.push(signal)
      signal.addEventListener("abort", () => reject(new Error("aborted")), { once: true })
    }))

    await render(<Probe />)
    expect(signals).toHaveLength(1)

    await act(async () => {
      Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" })
      document.dispatchEvent(new Event("visibilitychange"))
      await Promise.resolve()
    })
    expect(signals[0]?.aborted).toBe(true)

    await act(async () => {
      Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" })
      document.dispatchEvent(new Event("visibilitychange"))
      await tick()
    })
    expect(signals).toHaveLength(2)
  })

  it("reports query failures and returns an empty state without a signed-in user", async () => {
    notificationsApiMock.list.mockRejectedValueOnce(new Error("offline"))
    await render(<Probe />)
    await waitForText("Could not load notifications.")

    act(() => root.unmount())
    authState.user = null
    root = createRoot(container)
    await render(<DefaultProbe />)
    await waitForText("anonymous|0")
  })

  it("treats notification responses without items as an empty page", async () => {
    notificationsApiMock.list.mockResolvedValueOnce({
      unread_count: 0,
      next_cursor: null,
      has_more: false,
    })

    await render(<Probe />)
    await waitForText("empty|0")
  })

  it("normalizes a prefetched single notification page before mounting the infinite query", async () => {
    const queryKey = asQueryKey(notificationsCacheKey(5))
    queryClient.setQueryData<NotificationListResponse>(queryKey, {
      items: [unread],
      unread_count: 1,
      next_cursor: null,
      has_more: false,
    })

    await render(<Probe />)
    await waitForText("Revision risk|1")

    const cached = queryClient.getQueryData<InfiniteData<NotificationListResponse>>(queryKey)
    expect(cached?.pages[0]?.items[0]?.id).toBe("notification-1")
    expect(cached?.pageParams).toEqual([null])
  })

  async function render(child: React.ReactNode) {
    await act(async () => {
      root.render(<QueryClientProvider client={queryClient}>{child}</QueryClientProvider>)
      await tick()
    })
  }

  async function click(label: string) {
    const button = Array.from(container.querySelectorAll("button")).find((candidate) => candidate.textContent === label)
    if (!button) throw new Error(`Missing button: ${label}`)
    await act(async () => {
      button.click()
      await tick()
    })
  }

  async function waitForText(text: string) {
    for (let index = 0; index < 30; index += 1) {
      if (container.textContent?.includes(text)) return
      await act(tick)
    }
    throw new Error(`Missing text: ${text}; received ${container.textContent}`)
  }
})

function Probe() {
  const state = useNotificationsState(5, {
    pollMs: 2500,
    refreshOnFocus: true,
  })
  return (
    <div>
      <span>{state.items[0]?.title ?? "empty"}|{state.unreadCount}</span>
      <span>{state.items.map((item) => item.title).join("|")}</span>
      <span>{state.error}</span>
      <button onClick={() => void state.markRead("notification-1")}>Mark one</button>
      <button onClick={() => void state.markAllRead()}>Mark all</button>
      <button onClick={() => void state.refresh()}>Refresh</button>
      <button onClick={() => void state.loadMore()}>Load more</button>
    </div>
  )
}

function DefaultProbe() {
  const state = useNotifications(3)
  return <span>{state.items.length ? "signed-in" : "anonymous"}|{state.unreadCount}</span>
}

async function tick() {
  await Promise.resolve()
  await new Promise((resolve) => window.setTimeout(resolve, 0))
  await Promise.resolve()
}
