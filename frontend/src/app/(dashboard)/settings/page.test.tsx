import React, { act, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"

const replaceMock = vi.hoisted(() => vi.fn())
const setUserMock = vi.hoisted(() => vi.fn())
const logoutMock = vi.hoisted(() => vi.fn())
const setThemeMock = vi.hoisted(() => vi.fn())
const portalMock = vi.hoisted(() => vi.fn())
const setUsernameMock = vi.hoisted(() => vi.fn())
const getEmailPreferencesMock = vi.hoisted(() => vi.fn())
const updateEmailPreferencesMock = vi.hoisted(() => vi.fn())
const authState = vi.hoisted(() => ({
  user: {
    email: "author@example.com",
    username: "author",
    tier: "author",
    tier_label: "Author",
    plan_tier: "author_monthly",
    trial_active: false,
    reading_mode: "casual",
    daily_word_goal: 1000,
    today_word_count: 250,
    messaging_permission: "anyone",
  },
}))

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
    setUsername: setUsernameMock,
  },
}))

vi.mock("@/lib/api/billing", () => ({
  billingApi: {
    portal: portalMock,
  },
}))

vi.mock("@/lib/api/email", () => ({
  emailApi: {
    getPreferences: getEmailPreferencesMock,
    updatePreferences: updateEmailPreferencesMock,
  },
}))

vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: () => ({
    user: authState.user,
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
    setUsernameMock.mockReset()
    getEmailPreferencesMock.mockReset()
    updateEmailPreferencesMock.mockReset()
    authState.user = {
      email: "author@example.com",
      username: "author",
      tier: "author",
      tier_label: "Author",
      plan_tier: "author_monthly",
      trial_active: false,
      reading_mode: "casual",
      daily_word_goal: 1000,
      today_word_count: 250,
      messaging_permission: "anyone",
    }
    getEmailPreferencesMock.mockResolvedValue({
      email: "author@example.com",
      product_updates: true,
      marketing: true,
      unsubscribed_all: false,
      unsubscribed_at: null,
    })
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

  it("shows an explicit cancel subscription action", async () => {
    const view = await renderSettingsPage()

    expect(view.textContent).toContain("Manage billing / cancel subscription")
    expect(view.textContent).toContain("cancel renewal")
  })

  it("opens the billing portal from the cancel subscription action", async () => {
    portalMock.mockResolvedValue({
      billing_enabled: true,
      portal_url: "https://billing.example.test/session",
    })

    const view = await renderSettingsPage()
    const button = findButton(view, "Manage billing / cancel subscription")

    await act(async () => {
      button?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      await Promise.resolve()
    })

    expect(portalMock).toHaveBeenCalledTimes(1)
    expect(window.location.href).toBe("https://billing.example.test/session")
  })

  it("shows the account username editor and saves an updated public handle", async () => {
    setUsernameMock.mockResolvedValue({
      ...authState.user,
      username: "new-handle",
    })

    const view = await renderSettingsPage()
    expect(view.textContent).toContain("This is your public")
    expect(view.textContent).toContain("separate from the author or pen name")

    const usernameInput = view.querySelector('input[autocomplete="username"]') as HTMLInputElement | null
    const saveButton = findButton(view, "Change username")
    expect(usernameInput?.value).toBe("author")

    await act(async () => {
      if (usernameInput) {
        usernameInput.value = "new-handle"
        usernameInput.dispatchEvent(new Event("input", { bubbles: true }))
      }
    })

    await act(async () => {
      saveButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      await Promise.resolve()
    })

    expect(setUsernameMock).toHaveBeenCalledWith("new-handle")
    expect(setUserMock).toHaveBeenCalledWith(expect.objectContaining({ username: "new-handle" }))
    expect(view.textContent).toContain("Public username updated.")
  })

  it("loads and updates promotional email preferences", async () => {
    updateEmailPreferencesMock.mockResolvedValue({
      email: "author@example.com",
      product_updates: false,
      marketing: true,
      unsubscribed_all: false,
      unsubscribed_at: null,
    })

    const view = await renderSettingsPage()

    await act(async () => {
      await Promise.resolve()
    })

    expect(view.textContent).toContain("Control promotional LoreVia emails")
    expect(getEmailPreferencesMock).toHaveBeenCalledTimes(1)

    const button = findButton(view, "Product updates")
    await act(async () => {
      button?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      await Promise.resolve()
    })

    expect(updateEmailPreferencesMock).toHaveBeenCalledWith({
      product_updates: false,
      marketing: true,
    })
    expect(view.textContent).toContain("Email preferences updated.")
  })
})

async function renderSettingsPage() {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  act(() => {
    root?.render(<SettingsPage />)
  })
  await act(async () => {
    await Promise.resolve()
  })

  return container
}

function findButton(view: HTMLDivElement, label: string) {
  return Array.from(view.querySelectorAll("button")).find((button) => button.textContent?.includes(label))
}
