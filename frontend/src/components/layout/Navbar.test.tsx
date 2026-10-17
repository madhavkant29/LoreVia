import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

const useAuthStoreMock = vi.hoisted(() => vi.fn())
const usePreferencesStoreMock = vi.hoisted(() => vi.fn())
const replaceMock = vi.hoisted(() => vi.fn())
const logoutApiMock = vi.hoisted(() => vi.fn())
const clearAuthCookiesMock = vi.hoisted(() => vi.fn())
const apiClientMock = vi.hoisted(() => ({
  delete: vi.fn(() => Promise.resolve({ data: {} })),
  get: vi.fn(() => Promise.resolve({ data: {} })),
  post: vi.fn(() => Promise.resolve({ data: {} })),
  put: vi.fn(() => Promise.resolve({ data: {} })),
}))
const prefetchChatsSidebarDataMock = vi.hoisted(() => vi.fn())
const prefetchNotificationsSidebarDataMock = vi.hoisted(() => vi.fn())

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

vi.mock("@/lib/api/auth", () => ({
  authApi: {
    logout: logoutApiMock,
  },
}))

vi.mock("@/lib/api/client", () => ({
  apiClient: apiClientMock,
  clearAuthCookies: clearAuthCookiesMock,
}))

vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: useAuthStoreMock,
}))

vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: usePreferencesStoreMock,
}))

vi.mock("@/lib/query/sidebarPrefetch", () => ({
  prefetchChatsSidebarData: prefetchChatsSidebarDataMock,
  prefetchNotificationsSidebarData: prefetchNotificationsSidebarDataMock,
}))

import { Navbar } from "./Navbar"

let container: HTMLDivElement | null = null
let root: Root | null = null

describe("Navbar", () => {
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
    useAuthStoreMock.mockReset()
    usePreferencesStoreMock.mockReset()
    logoutApiMock.mockReset()
    clearAuthCookiesMock.mockReset()
    Object.values(apiClientMock).forEach((mock) => mock.mockClear())
    replaceMock.mockReset()
    prefetchChatsSidebarDataMock.mockReset()
    prefetchNotificationsSidebarDataMock.mockReset()
    container = null
    root = null
  })

  it("shows a single public uploads link in the navigation", () => {
    useAuthStoreMock.mockReturnValue({
      user: {
        email: "writer@example.com",
        username: "writer",
        tier_label: "Author",
        created_at: "2026-05-01T00:00:00Z",
      },
      logout: vi.fn(),
    })
    usePreferencesStoreMock.mockReturnValue({ theme: "light", toggleTheme: vi.fn() })

    const view = renderNavbar()
    const uploadsLinks = Array.from(view.querySelectorAll("a")).filter((element) => element.textContent?.includes("Public Uploads"))

    expect(uploadsLinks).toHaveLength(1)
    expect(uploadsLinks[0].getAttribute("href")).toBe("/public/uploads")
  })

  it("opens the avatar dropdown with account details and the public profile link", () => {
    useAuthStoreMock.mockReturnValue({
      user: {
        email: "writer@example.com",
        username: "writer",
        tier_label: "Author",
        created_at: "2026-05-01T00:00:00Z",
      },
      logout: vi.fn(),
    })
    usePreferencesStoreMock.mockReturnValue({ theme: "dark", toggleTheme: vi.fn() })

    const view = renderNavbar()
    const profileButton = Array.from(view.querySelectorAll("button")).find((button) => button.getAttribute("aria-label") === "Open profile menu")
    expect(profileButton).not.toBeNull()

    act(() => {
      profileButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })

    expect(view.textContent).toContain("@writer")
    expect(view.textContent).toContain("writer@example.com")
    expect(view.textContent).toContain("Public writer profile")
    expect(Array.from(view.querySelectorAll("a")).some((element) => element.getAttribute("href") === "/public/writers/writer")).toBe(true)
  })

  it("revokes the server session before clearing local auth state", async () => {
    const localLogout = vi.fn()
    logoutApiMock.mockResolvedValue({ ok: true })
    useAuthStoreMock.mockImplementation((selector?: (state: unknown) => unknown) => {
      const state = {
        hydrated: true,
        user: {
          email: "writer@example.com",
          username: "writer",
          tier_label: "Author",
          created_at: "2026-05-01T00:00:00Z",
        },
        logout: localLogout,
      }
      return selector ? selector(state) : state
    })
    usePreferencesStoreMock.mockReturnValue({ theme: "light", toggleTheme: vi.fn() })

    const view = renderNavbar()
    const profileButton = Array.from(view.querySelectorAll("button")).find((button) => button.getAttribute("aria-label") === "Open profile menu")
    act(() => profileButton?.dispatchEvent(new MouseEvent("click", { bubbles: true })))
    const signOutButton = Array.from(view.querySelectorAll("button")).find((button) => button.textContent?.includes("Sign out"))

    await act(async () => {
      signOutButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(logoutApiMock).toHaveBeenCalledTimes(1)
    expect(localLogout).toHaveBeenCalledTimes(1)
    expect(logoutApiMock.mock.invocationCallOrder[0]).toBeLessThan(localLogout.mock.invocationCallOrder[0])
    expect(clearAuthCookiesMock).toHaveBeenCalledTimes(1)
    expect(replaceMock).toHaveBeenCalledWith("/login")
  })

  it("always clears local auth state when remote logout fails", async () => {
    const localLogout = vi.fn()
    logoutApiMock.mockRejectedValue(new Error("network unavailable"))
    useAuthStoreMock.mockImplementation((selector?: (state: unknown) => unknown) => {
      const state = {
        hydrated: true,
        user: {
          email: "writer@example.com",
          username: "writer",
          tier_label: "Author",
          created_at: "2026-05-01T00:00:00Z",
        },
        logout: localLogout,
      }
      return selector ? selector(state) : state
    })
    usePreferencesStoreMock.mockReturnValue({ theme: "light", toggleTheme: vi.fn() })

    const view = renderNavbar()
    const profileButton = Array.from(view.querySelectorAll("button")).find((button) => button.getAttribute("aria-label") === "Open profile menu")
    act(() => profileButton?.dispatchEvent(new MouseEvent("click", { bubbles: true })))
    const signOutButton = Array.from(view.querySelectorAll("button")).find((button) => button.textContent?.includes("Sign out"))

    await act(async () => {
      signOutButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(localLogout).toHaveBeenCalledTimes(1)
    expect(clearAuthCookiesMock).toHaveBeenCalledTimes(1)
    expect(replaceMock).toHaveBeenCalledWith("/login")
  })
})

function renderNavbar() {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  act(() => {
    root?.render(<Navbar />)
  })

  return container
}
