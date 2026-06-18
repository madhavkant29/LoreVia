import React, { act } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

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
    notificationsApiMock.list.mockReset().mockResolvedValue({ items: [unread], unread_count: 1 })
    notificationsApiMock.markRead.mockReset().mockResolvedValue({ ...unread, read_at: "2026-06-15T09:05:00Z" })
    notificationsApiMock.markAllRead.mockReset().mockResolvedValue({
      items: [{ ...unread, read_at: "2026-06-15T09:10:00Z" }],
      unread_count: 0,
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
    expect(notificationsApiMock.list).toHaveBeenCalledWith(5, { syncRevisionDigests: false })

    notificationsApiMock.list.mockResolvedValue({
      items: [{ ...unread, read_at: "2026-06-15T09:05:00Z" }],
      unread_count: 0,
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
    syncRevisionDigests: false,
  })
  return (
    <div>
      <span>{state.items[0]?.title ?? "empty"}|{state.unreadCount}</span>
      <span>{state.error}</span>
      <button onClick={() => void state.markRead("notification-1")}>Mark one</button>
      <button onClick={() => void state.markAllRead()}>Mark all</button>
      <button onClick={() => void state.refresh()}>Refresh</button>
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
