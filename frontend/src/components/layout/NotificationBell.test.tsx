import React, { act, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

const useNotificationsMock = vi.hoisted(() => vi.fn())
const usePreferencesStoreMock = vi.hoisted(() => vi.fn())

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

vi.mock("@/components/layout/NotificationsPanel", () => ({
  NotificationsPanel: () => <aside data-testid="notifications-panel" />,
}))

vi.mock("@/lib/hooks/useNotifications", () => ({
  useNotifications: useNotificationsMock,
}))

vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: usePreferencesStoreMock,
}))

import { NotificationBell } from "./NotificationBell"

let container: HTMLDivElement | null = null
let root: Root | null = null

describe("NotificationBell", () => {
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
    useNotificationsMock.mockReset()
    usePreferencesStoreMock.mockReset()
    container = null
    root = null
  })

  it("shows an unread badge and highlights the bell when notifications are waiting", () => {
    useNotificationsMock.mockReturnValue({ unreadCount: 12 })
    usePreferencesStoreMock.mockReturnValue({ theme: "light" })

    const view = renderNotificationBell()

    const unreadBadge = view.querySelector(".bg-rose-500")
    expect(unreadBadge?.textContent).toBe("9+")

    const anchorsAndButtons = view.querySelectorAll("a,button")
    expect(anchorsAndButtons).toHaveLength(2)
    for (const element of anchorsAndButtons) {
      expect(element.getAttribute("aria-label")).toContain("unread")
      expect(element.className).toContain("border-rose-400/40")
      expect(element.querySelector("svg")?.getAttribute("class") ?? "").toContain("text-rose-500")
    }
  })

  it("keeps the bell neutral when there are no unread notifications", () => {
    useNotificationsMock.mockReturnValue({ unreadCount: 0 })
    usePreferencesStoreMock.mockReturnValue({ theme: "dark" })

    const view = renderNotificationBell()

    expect(view.querySelector(".bg-rose-500")).toBeNull()
    expect(view.querySelector("a")?.getAttribute("aria-label")).toBe("Open notifications")
    expect(view.querySelector("button")?.getAttribute("aria-label")).toBe("Toggle notifications")
  })
})

function renderNotificationBell() {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  act(() => {
    root?.render(<NotificationBell />)
  })

  return container
}
