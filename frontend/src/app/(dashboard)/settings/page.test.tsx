import React, { act, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"

const replaceMock = vi.hoisted(() => vi.fn())
const setUserMock = vi.hoisted(() => vi.fn())
const logoutMock = vi.hoisted(() => vi.fn())
const setThemeMock = vi.hoisted(() => vi.fn())
const portalMock = vi.hoisted(() => vi.fn())

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: replaceMock,
  }),
}))

vi.mock("@/components/ui/Workspace", () => ({
  WorkspaceHeader: ({ title, description, meta }: { title: ReactNode; description: ReactNode; meta?: ReactNode }) => (
    <div>
      <h1>{title}</h1>
      <p>{description}</p>
      {meta}
    </div>
  ),
  WorkspaceMetric: ({ label, value, note }: { label: ReactNode; value: ReactNode; note?: ReactNode }) => (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
      {note ? <p>{note}</p> : null}
    </div>
  ),
  WorkspacePage: ({ children, className }: { children: ReactNode; className?: string }) => <div className={className}>{children}</div>,
  WorkspacePanel: ({ children, className }: { children: ReactNode; className?: string }) => <section className={className}>{children}</section>,
}))

vi.mock("@/lib/api/auth", () => ({
  authApi: {
    logout: vi.fn(),
    setReadingMode: vi.fn(),
    setDailyWordGoal: vi.fn(),
    setMessagingPermission: vi.fn(),
  },
}))

vi.mock("@/lib/api/billing", () => ({
  billingApi: {
    portal: portalMock,
  },
}))

vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: () => ({
    user: {
      email: "author@example.com",
      tier: "author",
      tier_label: "Author",
      plan_tier: "author_monthly",
      trial_active: false,
      reading_mode: "casual",
      daily_word_goal: 1000,
      today_word_count: 250,
      messaging_permission: "anyone",
    },
    setUser: setUserMock,
    logout: logoutMock,
  }),
}))

vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: () => ({
    theme: "light",
    setTheme: setThemeMock,
  }),
}))

import SettingsPage from "./page"

let container: HTMLDivElement | null = null
let root: Root | null = null
const originalLocation = window.location

describe("SettingsPage billing actions", () => {
  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

  beforeEach(() => {
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { href: "http://localhost/settings" },
    })

    replaceMock.mockReset()
    setUserMock.mockReset()
    logoutMock.mockReset()
    setThemeMock.mockReset()
    portalMock.mockReset()
  })

  afterAll(() => {
    Object.defineProperty(window, "location", {
      configurable: true,
      value: originalLocation,
    })
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
    container = null
    root = null
    window.location.href = "http://localhost/settings"
  })

  it("shows an explicit cancel subscription action", () => {
    const view = renderSettingsPage()

    expect(view.textContent).toContain("Manage billing / cancel subscription")
    expect(view.textContent).toContain("cancel renewal")
  })

  it("opens the billing portal from the cancel subscription action", async () => {
    portalMock.mockResolvedValue({
      billing_enabled: true,
      portal_url: "https://billing.example.test/session",
    })

    const view = renderSettingsPage()
    const button = findButton(view, "Manage billing / cancel subscription")

    await act(async () => {
      button?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      await Promise.resolve()
    })

    expect(portalMock).toHaveBeenCalledTimes(1)
    expect(window.location.href).toBe("https://billing.example.test/session")
  })
})

function renderSettingsPage() {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  act(() => {
    root?.render(<SettingsPage />)
  })

  return container
}

function findButton(view: HTMLDivElement, label: string) {
  return Array.from(view.querySelectorAll("button")).find((button) => button.textContent?.includes(label))
}
