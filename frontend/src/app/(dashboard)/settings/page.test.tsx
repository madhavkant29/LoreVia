import React, { act, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"

const replaceMock = vi.hoisted(() => vi.fn())
const pushMock = vi.hoisted(() => vi.fn())
const setUserMock = vi.hoisted(() => vi.fn())
const logoutMock = vi.hoisted(() => vi.fn())
const setThemeMock = vi.hoisted(() => vi.fn())
const portalMock = vi.hoisted(() => vi.fn())
const subscriptionMock = vi.hoisted(() => vi.fn())
const setUsernameMock = vi.hoisted(() => vi.fn())
const setDailyGoalMock = vi.hoisted(() => vi.fn())
const setReadingModeMock = vi.hoisted(() => vi.fn())
const logoutApiMock = vi.hoisted(() => vi.fn())
const clearAuthCookiesMock = vi.hoisted(() => vi.fn())
const apiClientPutMock = vi.hoisted(() => vi.fn())
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
    trial_ends_at: null as string | null,
    reading_mode: "casual",
    daily_word_goal: 1000,
    today_word_count: 250,
    messaging_permission: "anyone",
  },
}))

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: replaceMock,
    push: pushMock,
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
    logout: logoutApiMock,
    setReadingMode: setReadingModeMock,
    setDailyWordGoal: setDailyGoalMock,
    setMessagingPermission: vi.fn(),
    setUsername: setUsernameMock,
  },
}))

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    put: apiClientPutMock,
  },
  clearAuthCookies: clearAuthCookiesMock,
}))

vi.mock("@/lib/api/billing", () => ({
  billingApi: {
    portal: portalMock,
    subscription: subscriptionMock,
  },
}))

vi.mock("@/lib/api/email", () => ({
  emailApi: {
    getPreferences: getEmailPreferencesMock,
    updatePreferences: updateEmailPreferencesMock,
  },
}))

vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: (selector?: (state: unknown) => unknown) => {
    const state = {
    hydrated: true,
    user: authState.user,
    setUser: setUserMock,
    logout: logoutMock,
    }
    return selector ? selector(state) : state
  },
}))

vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: () => ({
    theme: "light",
    setTheme: setThemeMock,
  }),
}))

import SettingsPage from "./page"

import type { BillingSubscription } from "@/lib/api/billing"

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
    pushMock.mockReset()
    setUserMock.mockReset()
    logoutMock.mockReset()
    setThemeMock.mockReset()
    portalMock.mockReset()
    subscriptionMock.mockReset()
    subscriptionMock.mockResolvedValue(
      makeBillingSubscription({
        display_state: "active",
        next_charge_at: "2026-10-19T00:00:00Z",
      }),
    )
    setUsernameMock.mockReset()
    setDailyGoalMock.mockReset()
    setReadingModeMock.mockReset()
    logoutApiMock.mockReset()
    clearAuthCookiesMock.mockReset()
    apiClientPutMock.mockReset()
    getEmailPreferencesMock.mockReset()
    updateEmailPreferencesMock.mockReset()
    authState.user = {
      email: "author@example.com",
      username: "author",
      tier: "author",
      tier_label: "Author",
      plan_tier: "author_monthly",
      trial_active: false,
      trial_ends_at: null,
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

  it("shows the active subscription state with the next renewal date", async () => {
    const view = await renderSettingsPage()

    expect(view.textContent).toContain("Manage subscription")
    expect(view.textContent).toContain("Author — $19/month")
    expect(view.textContent).toContain("Next renewal")
    expect(view.textContent).toContain("October 19, 2026")
    expect(view.textContent).toContain("renews automatically")
    expect(view.textContent).not.toContain("Cancellation scheduled")
  })

  it("preserves a failed daily goal and does not coerce invalid input", async () => {
    setDailyGoalMock.mockRejectedValue(new Error("offline"))
    const view = await renderSettingsPage()
    const field = view.querySelector('#daily-word-goal') as HTMLInputElement
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set
    await act(async () => { setter?.call(field, "-2"); field.dispatchEvent(new Event("input", { bubbles: true })) })
    expect(findButton(view, "Save daily goal")?.disabled).toBe(true)
    expect(field.value).toBe("-2")
    expect(setDailyGoalMock).not.toHaveBeenCalled()
    await act(async () => { setter?.call(field, "2500"); field.dispatchEvent(new Event("input", { bubbles: true })) })
    await act(async () => { findButton(view, "Save daily goal")?.click() })
    expect(setDailyGoalMock).toHaveBeenCalledWith(2500)
    expect(field.value).toBe("2500")
    expect(view.textContent).toContain("We could not save the daily goal")
  })

  it("retains the confirmed reading mode when the update fails", async () => {
    setReadingModeMock.mockRejectedValue(new Error("offline"))
    const view = await renderSettingsPage()
    await act(async () => { findButton(view, "Speed")?.click() })
    expect(setReadingModeMock).toHaveBeenCalledWith("speed")
    expect(findButton(view, "Casual")?.getAttribute("aria-pressed")).toBe("true")
    expect(view.textContent).toContain("Reading mode could not be saved")
    expect(setUserMock).not.toHaveBeenCalled()
  })

  it("retries failed billing and email loads without displaying invented choices", async () => {
    subscriptionMock.mockRejectedValueOnce(new Error("offline"))
    getEmailPreferencesMock.mockRejectedValueOnce(new Error("offline"))
    const view = await renderSettingsPage()
    expect(view.textContent).toContain("renewal and payment status are unverified")
    expect(findButton(view, "Product updates")).toBeUndefined()
    await act(async () => { findButton(view, "Retry billing details")?.click(); findButton(view, "Retry email preferences")?.click() })
    expect(view.textContent).toContain("Next renewal")
    expect(findButton(view, "Product updates")?.getAttribute("aria-pressed")).toBe("true")
  })

  it("opens the billing portal from the manage subscription action", async () => {
    portalMock.mockResolvedValue({
      billing_enabled: true,
      portal_url: "https://billing.example.test/session",
    })

    const view = await renderSettingsPage()
    const button = findButton(view, "Manage subscription")

    await act(async () => {
      button?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      await Promise.resolve()
    })

    expect(portalMock).toHaveBeenCalledTimes(1)
    expect(window.location.href).toBe("https://billing.example.test/session")
  })

  it("shows cancellation scheduled without presenting a renewal or cancellation as immediate", async () => {
    subscriptionMock.mockResolvedValue(
      makeBillingSubscription({
        display_state: "cancellation_scheduled",
        cancel_at_period_end: true,
        next_charge_at: null,
        auto_renew: false,
      }),
    )

    const view = await renderSettingsPage()

    expect(view.textContent).toContain("Cancellation scheduled")
    expect(view.textContent).toContain("remains active until October 19, 2026")
    expect(view.textContent).toContain("won't be charged again")
    expect(view.textContent).not.toContain("Next renewal")
    expect(view.textContent).not.toContain("renews automatically")
  })

  it("shows a payment issue state for past-due subscriptions", async () => {
    subscriptionMock.mockResolvedValue(
      makeBillingSubscription({
        status: "past_due",
        display_state: "past_due",
        next_charge_at: null,
        auto_renew: false,
        last_payment_status: "failed",
      }),
    )

    const view = await renderSettingsPage()

    expect(view.textContent).toContain("Payment issue")
    expect(view.textContent).toContain("Paddle retries")
    expect(view.textContent).not.toContain("Next renewal")
  })

  it("shows the Architect price from the backend subscription state", async () => {
    authState.user = {
      ...authState.user,
      tier_label: "Architect",
      plan_tier: "architect_monthly",
    }
    subscriptionMock.mockResolvedValue(
      makeBillingSubscription({
        plan: "architect_monthly",
        plan_tier: "architect",
        price: { amount: 39, currency: "USD", interval: "month" },
      }),
    )

    const view = await renderSettingsPage()

    expect(view.textContent).toContain("Architect — $39/month")
  })

  it("keeps refund policy and refund request actions beside paid billing controls", async () => {
    const view = await renderSettingsPage()

    expect(view.querySelector('a[href="/refund"]')?.textContent).toContain("Refund policy")
    expect(view.querySelector('a[href^="mailto:support@getlorevia.com"]')?.textContent).toContain("Request a refund")
  })

  it("shows the active free-trial countdown without implying a scheduled charge", async () => {
    authState.user = {
      ...authState.user,
      tier: "free",
      tier_label: "Author (free trial)",
      plan_tier: "free",
      trial_active: true,
      trial_ends_at: "2099-09-08T10:00:00Z",
    }
    subscriptionMock.mockResolvedValue(
      makeBillingSubscription({
        plan: "free",
        plan_tier: "free",
        status: "free",
        display_state: "trial",
        price: { amount: 0, currency: "USD", interval: "month" },
        current_period_start: null,
        current_period_end: null,
        cancel_at_period_end: false,
        cancellation_scheduled_at: null,
        next_charge_at: null,
        auto_renew: false,
        has_paddle_subscription: false,
      }),
    )

    const view = await renderSettingsPage()

    expect(view.textContent).toContain("Free trial countdown")
    expect(view.textContent).toContain("remaining")
    expect(view.textContent).toContain("Your free trial is already active")
    expect(view.textContent).toContain("no charge is scheduled when the trial ends")
    expect(view.textContent).toContain("View paid plans")
    expect(view.textContent).not.toContain("Manage subscription")
  })

  it("shows the account username editor and saves an updated public handle", async () => {
    setUsernameMock.mockResolvedValue({
      ...authState.user,
      username: "new-handle",
    })

    const view = await renderSettingsPage()
    expect(view.textContent).toContain("This is your public")
    expect(view.textContent).toContain("Your manuscript author or pen name can be changed per book")

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
    expect(view.textContent).toContain("@new-handle")
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

    expect(view.textContent).toContain("LoreVia emails")
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

  it("can unsubscribe from all promotional email preferences", async () => {
    updateEmailPreferencesMock.mockResolvedValue({
      email: "author@example.com",
      product_updates: false,
      marketing: false,
      unsubscribed_all: true,
      unsubscribed_at: "2026-06-29T07:00:00Z",
    })

    const view = await renderSettingsPage()

    await act(async () => {
      await Promise.resolve()
    })

    const button = findButton(view, "Unsubscribe from promotional emails")
    await act(async () => {
      button?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      await Promise.resolve()
    })

    expect(updateEmailPreferencesMock).toHaveBeenCalledWith({
      product_updates: false,
      marketing: false,
    })
    expect(view.textContent).toContain("Promotional emails unsubscribed")
  })

  it("searches settings categories without changing routes", async () => {
    const view = await renderSettingsPage()
    const search = view.querySelector('input[type="search"]') as HTMLInputElement
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set

    await act(async () => {
      setter?.call(search, "security")
      search.dispatchEvent(new Event("input", { bubbles: true }))
    })

    expect(view.textContent).toContain("Sign out")
    expect(view.textContent).toContain("Danger Zone")
    expect(view.textContent).not.toContain("Public identity")
    expect(view.querySelector('a[href="#session"]')).not.toBeNull()
  })

  it("marks the settings sidebar item for the section active under the header", async () => {
    const view = await renderSettingsPage()
    const accountLink = view.querySelector('a[href="#account"]') as HTMLAnchorElement | null
    const sessionLink = view.querySelector('a[href="#session"]') as HTMLAnchorElement | null

    expect(accountLink?.getAttribute("aria-current")).toBe("location")

    const sectionRects: Record<string, DOMRect> = {
      account: makeRect(-900, -760),
      identity: makeRect(-720, -520),
      appearance: makeRect(-500, -380),
      reading: makeRect(-360, -220),
      privacy: makeRect(-200, -80),
      community: makeRect(-160, -40),
      emails: makeRect(-40, 40),
      goals: makeRect(50, 90),
      session: makeRect(96, 260),
      danger: makeRect(280, 420),
    }

    for (const [id, rect] of Object.entries(sectionRects)) {
      const section = view.querySelector(`#${id}`) as HTMLElement | null
      if (section) {
        section.getBoundingClientRect = vi.fn(() => rect)
      }
    }

    const requestAnimationFrameMock = vi
      .spyOn(window, "requestAnimationFrame")
      .mockImplementation((callback: FrameRequestCallback) => {
        callback(0)
        return 1
      })
    const cancelAnimationFrameMock = vi
      .spyOn(window, "cancelAnimationFrame")
      .mockImplementation(() => undefined)

    Object.defineProperty(document.documentElement, "scrollHeight", {
      configurable: true,
      value: 3000,
    })
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: 800,
    })
    Object.defineProperty(window, "scrollY", {
      configurable: true,
      value: 1000,
    })

    await act(async () => {
      window.dispatchEvent(new Event("scroll"))
      await Promise.resolve()
    })

    expect(sessionLink?.getAttribute("aria-current")).toBe("location")
    expect(sessionLink?.className).toContain("settings-section-nav__item--active")
    expect(accountLink?.getAttribute("aria-current")).toBeNull()

    requestAnimationFrameMock.mockRestore()
    cancelAnimationFrameMock.mockRestore()
  })

  it("clears local auth and redirects after a failed bounded server logout", async () => {
    logoutApiMock.mockRejectedValue(new Error("network unavailable"))
    const view = await renderSettingsPage()
    const button = findButton(view, "Sign out")

    await act(async () => {
      button?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(logoutApiMock).toHaveBeenCalledTimes(1)
    expect(logoutMock).toHaveBeenCalledTimes(1)
    expect(logoutApiMock.mock.invocationCallOrder[0]).toBeLessThan(logoutMock.mock.invocationCallOrder[0])
    expect(clearAuthCookiesMock).toHaveBeenCalledTimes(1)
    expect(replaceMock).toHaveBeenCalledWith("/login")
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

function makeBillingSubscription(
  overrides: Partial<BillingSubscription> = {},
): BillingSubscription {
  return {
    plan: "author_monthly",
    plan_tier: "author",
    status: "active",
    display_state: "active",
    price: { amount: 19, currency: "USD", interval: "month" },
    current_period_start: "2026-09-19T00:00:00Z",
    current_period_end: "2026-10-19T00:00:00Z",
    cancel_at_period_end: false,
    cancellation_scheduled_at: null,
    next_charge_at: "2026-10-19T00:00:00Z",
    auto_renew: true,
    last_payment_status: null,
    has_paddle_subscription: true,
    ...overrides,
  }
}

function makeRect(top: number, bottom: number): DOMRect {
  return {
    x: 0,
    y: top,
    width: 100,
    height: bottom - top,
    top,
    right: 100,
    bottom,
    left: 0,
    toJSON: () => ({}),
  } as DOMRect
}
