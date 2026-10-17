import React, { act, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

const useNotificationsStateMock = vi.hoisted(() => vi.fn())
const usePreferencesStoreMock = vi.hoisted(() => vi.fn())
const getRevisionIntelligenceMock = vi.hoisted(() => vi.fn())

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

vi.mock("@/lib/hooks/useNotifications", () => ({
  useNotificationsState: useNotificationsStateMock,
}))

vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: usePreferencesStoreMock,
}))

vi.mock("@/lib/api/books", () => ({
  booksApi: {
    getRevisionIntelligence: getRevisionIntelligenceMock,
  },
}))

vi.mock("@/lib/api/social", () => ({
  socialApi: {
    acceptFriendRequest: vi.fn(),
    declineFriendRequest: vi.fn(),
  },
}))

import { NotificationsPanel } from "./NotificationsPanel"

let container: HTMLDivElement | null = null
let root: Root | null = null

describe("NotificationsPanel", () => {
  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

  afterEach(() => {
    if (root) {
      act(() => {
        root?.unmount()
      })
    }
    if (container) {
      container.remove()
    }
    useNotificationsStateMock.mockReset()
    usePreferencesStoreMock.mockReset()
    getRevisionIntelligenceMock.mockReset()
    container = null
    root = null
  })

  it("loads revision details inline for revision digest notifications", async () => {
    usePreferencesStoreMock.mockReturnValue({ theme: "light" })
    useNotificationsStateMock.mockReturnValue({
      items: [
        {
          id: "notification-1",
          book_id: "book-1",
          kind: "revision_digest",
          title: "2 revision risks surfaced in Metamorphosis",
          body: "2 downstream logic risks need attention first.",
          data: {
            active_item_count: 3,
            high_severity_count: 2,
            hero_message: "2 downstream logic risks need attention first.",
          },
          read_at: null,
          created_at: "2026-05-18T16:00:00Z",
        },
      ],
      unreadCount: 1,
      loading: false,
      error: null,
      markRead: vi.fn(),
      markAllRead: vi.fn(),
      refresh: vi.fn(),
    })
    getRevisionIntelligenceMock.mockResolvedValue({
      tagline: "Know what your edit breaks before your readers do.",
      summary: {
        hero_message: "2 downstream logic risks need attention first.",
        active_item_count: 3,
        high_severity_count: 2,
        task_ready_count: 1,
        recent_edit_label: "You changed Chapter 2.",
      },
      change_impacts: [
        {
          id: "impact-1",
          category: "logic",
          title: "Gate rule contradiction",
          description: "Chapter 3 still assumes the original gate rule.",
          severity: "high",
          chapter_ref: 3,
          source_label: null,
          recommendation: "Revise the later payoff so the rule stays consistent.",
          status: "pending",
          assigned_version_id: null,
          task_id: null,
        },
      ],
      genre_checks: [],
      revision_plan: [],
      knowledge_matrix: [],
      knowledge_timeline: [],
      scene_advice: [],
      confusion_map: [],
      voice_alerts: [],
    })

    const view = renderNotificationsPanel()
    expect(view.textContent?.match(/2 downstream logic risks need attention first\./g)).toHaveLength(1)
    const detailsButton = Array.from(view.querySelectorAll("button")).find((button) => button.textContent?.trim() === "View details")
    expect(detailsButton).not.toBeNull()

    await act(async () => {
      detailsButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      await Promise.resolve()
    })

    expect(getRevisionIntelligenceMock).toHaveBeenCalledWith("book-1")
    expect(view.textContent).toContain("Revision Details")
    expect(view.textContent).toContain("Gate rule contradiction")
    expect(view.textContent).toContain("Chapter 3 still assumes the original gate rule.")
  })

  it("passes enabled state through to notification fetching", () => {
    usePreferencesStoreMock.mockReturnValue({ theme: "light" })
    useNotificationsStateMock.mockReturnValue({
      items: [],
      unreadCount: 0,
      loading: false,
      error: null,
      markRead: vi.fn(),
      markAllRead: vi.fn(),
      refresh: vi.fn(),
    })

    renderNotificationsPanel({ enabled: false })

    expect(useNotificationsStateMock).toHaveBeenCalledWith(40, {
      enabled: false,
      pollMs: 60_000,
      refreshOnFocus: true,
    })
  })

  it("keeps sidebar notification fetches on the cached-only path", () => {
    usePreferencesStoreMock.mockReturnValue({ theme: "light" })
    useNotificationsStateMock.mockReturnValue({
      items: [],
      unreadCount: 0,
      loading: false,
      error: null,
      markRead: vi.fn(),
      markAllRead: vi.fn(),
      refresh: vi.fn(),
    })

    renderNotificationsPanel({ enabled: true, mode: "sidebar" })

    expect(useNotificationsStateMock).toHaveBeenCalledWith(40, {
      enabled: true,
      pollMs: 60_000,
      refreshOnFocus: true,
    })
  })
})

function renderNotificationsPanel({ enabled, mode = "page" }: { enabled?: boolean; mode?: "sidebar" | "page" } = {}) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  act(() => {
    root?.render(<NotificationsPanel mode={mode} enabled={enabled} />)
  })

  return container
}
