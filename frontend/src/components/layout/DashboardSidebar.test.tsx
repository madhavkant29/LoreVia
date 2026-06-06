import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

const replaceMock = vi.hoisted(() => vi.fn())
const prefetchChatsSidebarDataMock = vi.hoisted(() => vi.fn())
const prefetchNotificationsSidebarDataMock = vi.hoisted(() => vi.fn())

const authState = {
  hydrated: true,
  user: {
    email: "writer@example.com",
    username: "writer",
    tier_label: "Author",
    created_at: "2026-05-01T00:00:00Z",
  },
  logout: vi.fn(),
}

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

vi.mock("next/navigation", () => ({
  usePathname: () => "/library",
  useRouter: () => ({ replace: replaceMock }),
}))

vi.mock("@/components/layout/BrandLockup", () => ({
  BrandLockup: () => <div>Brand</div>,
}))

vi.mock("@/components/layout/ChatLauncher", () => ({
  ChatLauncher: () => <div data-testid="chat-launcher" />,
}))

vi.mock("@/components/layout/NotificationBell", () => ({
  NotificationBell: () => <div data-testid="notification-bell" />,
}))

vi.mock("@/lib/api/books", () => ({
  booksApi: {
    list: vi.fn(),
  },
}))

vi.mock("@/lib/query/queryClient", () => ({
  queryClient: {
    prefetchQuery: vi.fn(),
  },
}))

vi.mock("@/lib/query/cacheKeys", () => ({
  asQueryKey: (key: string) => key,
  booksListCacheKey: () => "books-list",
}))

vi.mock("@/lib/query/sidebarPrefetch", () => ({
  prefetchChatsSidebarData: prefetchChatsSidebarDataMock,
  prefetchNotificationsSidebarData: prefetchNotificationsSidebarDataMock,
}))

vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: (selector?: (state: typeof authState) => unknown) => (selector ? selector(authState) : authState),
}))

vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: () => ({ theme: "dark", toggleTheme: vi.fn() }),
}))

import { DashboardSidebar } from "./DashboardSidebar"

let container: HTMLDivElement | null = null
let root: Root | null = null

describe("DashboardSidebar", () => {
  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

  afterEach(() => {
    if (root) {
      act(() => {
        root?.unmount()
      })
    }
    container?.remove()
    replaceMock.mockReset()
    prefetchChatsSidebarDataMock.mockReset()
    prefetchNotificationsSidebarDataMock.mockReset()
    container = null
    root = null
  })

  it("renders dashboard navigation with one public uploads link and an active library item", () => {
    const view = renderSidebar()
    const uploadsLinks = Array.from(view.querySelectorAll("a")).filter((element) => element.textContent?.includes("Public Uploads"))
    const libraryLink = Array.from(view.querySelectorAll("a")).find((element) => element.textContent?.includes("Library"))

    expect(uploadsLinks).toHaveLength(1)
    expect(uploadsLinks[0].getAttribute("href")).toBe("/public/uploads")
    expect(libraryLink?.getAttribute("href")).toBe("/library")
    expect(libraryLink?.className).toContain("bg-stone-200")
    expect(view.textContent).toContain("Page content")
  })

  it("links the bottom profile card to the public writer profile", () => {
    const view = renderSidebar()
    const profileLink = view.querySelector('a[aria-label="Open author public profile"]')

    expect(profileLink?.getAttribute("href")).toBe("/public/writers/writer")
    expect(view.textContent).toContain("@writer")
    expect(view.textContent).toContain("Author")
    expect(Array.from(view.querySelectorAll("button")).some((button) => button.getAttribute("aria-label") === "Open profile menu")).toBe(false)
  })
})

function renderSidebar() {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  act(() => {
    root?.render(<DashboardSidebar>Page content</DashboardSidebar>)
  })

  return container
}
