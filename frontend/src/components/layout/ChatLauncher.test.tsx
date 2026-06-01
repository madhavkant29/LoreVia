import React, { act, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

const useAuthStoreMock = vi.hoisted(() => vi.fn())
const usePreferencesStoreMock = vi.hoisted(() => vi.fn())
const useChatUnreadCountMock = vi.hoisted(() => vi.fn())
const prefetchChatsSidebarDataMock = vi.hoisted(() => vi.fn())

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

vi.mock("@/components/layout/ChatsPanel", () => ({
  ChatsPanel: ({ enabled }: { enabled?: boolean }) => <aside data-enabled={String(enabled)} data-testid="chats-panel" />,
}))

vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: useAuthStoreMock,
}))

vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: usePreferencesStoreMock,
}))

vi.mock("@/lib/hooks/useChatUnreadCount", () => ({
  useChatUnreadCount: useChatUnreadCountMock,
}))

vi.mock("@/lib/query/sidebarPrefetch", () => ({
  prefetchChatsSidebarData: prefetchChatsSidebarDataMock,
}))

import { ChatLauncher } from "./ChatLauncher"

let container: HTMLDivElement | null = null
let root: Root | null = null

describe("ChatLauncher", () => {
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
    useAuthStoreMock.mockReset()
    usePreferencesStoreMock.mockReset()
    useChatUnreadCountMock.mockReset()
    prefetchChatsSidebarDataMock.mockReset()
    container = null
    root = null
  })

  it("hides the launcher for signed-out visitors", () => {
    useAuthStoreMock.mockReturnValue({ user: null })
    usePreferencesStoreMock.mockReturnValue({ theme: "light" })
    useChatUnreadCountMock.mockReturnValue({ unreadCount: 0, hydrated: true })

    const view = renderChatLauncher()

    expect(view.querySelector("a,button")).toBeNull()
  })

  it("shows an unread badge and highlighted button when messages are unread", () => {
    useAuthStoreMock.mockReturnValue({ user: { id: "user-1" } })
    usePreferencesStoreMock.mockReturnValue({ theme: "dark" })
    useChatUnreadCountMock.mockReturnValue({ unreadCount: 12, hydrated: true })

    const view = renderChatLauncher()

    const unreadBadge = view.querySelector(".bg-sky-500")
    expect(unreadBadge?.textContent).toBe("9+")

    const anchorsAndButtons = view.querySelectorAll("a,button")
    expect(anchorsAndButtons).toHaveLength(2)
    for (const element of anchorsAndButtons) {
      expect(element.getAttribute("aria-label")).toContain("unread")
      expect(element.className).toContain("border-sky-400/40")
      expect(element.querySelector("svg")?.getAttribute("class") ?? "").toContain("text-sky-500")
    }
  })

  it("mounts the chats sidebar only after the desktop launcher is opened", async () => {
    useAuthStoreMock.mockReturnValue({ user: { id: "user-1" } })
    usePreferencesStoreMock.mockReturnValue({ theme: "light" })
    useChatUnreadCountMock.mockReturnValue({ unreadCount: 0, hydrated: true })

    const view = renderChatLauncher()

    expect(view.querySelector('[data-testid="chats-panel"]')).toBeNull()

    const buttons = view.querySelectorAll("button")
    const toggleButton = buttons[0]

    await act(async () => {
      toggleButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      await Promise.resolve()
    })
    await flushDynamicPanel()

    const panelShell = view.querySelector('aside[aria-hidden="false"]')
    expect(panelShell).not.toBeNull()
    expect(panelShell?.className).toContain("translate-x-0")
  })

  it("keeps the chats sidebar mounted but hidden when clicking outside it", async () => {
    useAuthStoreMock.mockReturnValue({ user: { id: "user-1" } })
    usePreferencesStoreMock.mockReturnValue({ theme: "light" })
    useChatUnreadCountMock.mockReturnValue({ unreadCount: 0, hydrated: true })

    const view = renderChatLauncher()
    const toggleButton = view.querySelector("button")

    await act(async () => {
      toggleButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      await Promise.resolve()
    })
    await flushDynamicPanel()

    expect(view.querySelector('aside[aria-hidden="false"]')).not.toBeNull()

    await act(async () => {
      document.body.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }))
      await Promise.resolve()
    })

    const panelShell = view.querySelector('aside[aria-hidden="true"]')
    expect(panelShell?.getAttribute("aria-hidden")).toBe("true")
    expect(panelShell?.className).toContain("pointer-events-none")
  })

  it("defers unread queries until the launcher is enabled or opened", async () => {
    useAuthStoreMock.mockReturnValue({ user: { id: "user-1" } })
    usePreferencesStoreMock.mockReturnValue({ theme: "light" })
    useChatUnreadCountMock.mockReturnValue({ unreadCount: 0, hydrated: true })

    const view = renderChatLauncher({ enabled: false })

    expect(useChatUnreadCountMock).toHaveBeenCalledWith({
      enabled: false,
      pollMs: false,
      refreshOnFocus: true,
    })

    const buttons = view.querySelectorAll("button")
    const toggleButton = buttons[0]

    await act(async () => {
      toggleButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      await Promise.resolve()
    })
    await flushDynamicPanel()

    expect(useChatUnreadCountMock).toHaveBeenLastCalledWith({
      enabled: true,
      pollMs: false,
      refreshOnFocus: true,
    })
  })

  it("prefetches sidebar chat data before opening the launcher", () => {
    useAuthStoreMock.mockReturnValue({ user: { id: "user-1" } })
    usePreferencesStoreMock.mockReturnValue({ theme: "light" })
    useChatUnreadCountMock.mockReturnValue({ unreadCount: 0, hydrated: true })

    const view = renderChatLauncher()
    const toggleButton = view.querySelector("button")

    act(() => {
      toggleButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })

    expect(prefetchChatsSidebarDataMock).toHaveBeenCalledTimes(1)
  })
})

function renderChatLauncher({ enabled }: { enabled?: boolean } = {}) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  act(() => {
    root?.render(<ChatLauncher enabled={enabled} />)
  })

  return container
}

async function flushDynamicPanel() {
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
    await new Promise((resolve) => window.setTimeout(resolve, 0))
  })
}
