// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"

const routerPush = vi.fn()
const checkout = vi.fn()
const checkoutPreview = vi.fn()
const abandonCheckout = vi.fn()
const portal = vi.fn()
let authUser: unknown = null
let theme = "light"
let scriptOnLoad: (() => void) | undefined

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
}))

vi.mock("next/script", () => ({
  default: ({ onLoad }: { onLoad?: () => void }) => {
    scriptOnLoad = onLoad
    return null
  },
}))

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPush }),
}))

vi.mock("@/components/layout/BrandLockup", () => ({
  BrandLockup: () => <span>LoreVia</span>,
}))

vi.mock("@/components/marketing/Reveal", () => ({
  Reveal: ({ children }: { children: ReactNode }) => <>{children}</>,
}))

vi.mock("@/lib/api/billing", () => ({
  billingApi: {
    checkout: (...args: unknown[]) => checkout(...args),
    checkoutPreview: (...args: unknown[]) => checkoutPreview(...args),
    abandonCheckout: (...args: unknown[]) => abandonCheckout(...args),
    portal: (...args: unknown[]) => portal(...args),
  },
}))

vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: () => ({ user: authUser }),
}))

vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: () => ({ theme }),
}))

import { PricingPlans } from "@/components/billing/PricingPlans"
import { TrustPage } from "@/components/legal/TrustPage"
import { HomePricingSection } from "@/components/marketing/HomePricingSection"

let root: Root | null = null
let container: HTMLDivElement | null = null
const originalLocation = window.location

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

async function renderElement(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  await act(async () => {
    root?.render(element)
    await Promise.resolve()
  })
}

async function clickByText(text: string) {
  const button = Array.from(document.body.querySelectorAll("button")).find((item) =>
    item.textContent?.includes(text)
  )
  if (!button) throw new Error(`Missing button: ${text}`)
  await act(async () => {
    button.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await Promise.resolve()
  })
}

afterEach(() => {
  if (root) {
    act(() => {
      root?.unmount()
    })
  }
  container?.remove()
  root = null
  container = null
  document.body.innerHTML = ""
  routerPush.mockReset()
  checkout.mockReset()
  checkoutPreview.mockReset()
  abandonCheckout.mockReset()
  portal.mockReset()
  authUser = null
  theme = "light"
  scriptOnLoad = undefined
  delete window.Paddle
  vi.unstubAllEnvs()
  Object.defineProperty(window, "location", {
    configurable: true,
    value: originalLocation,
  })
})

describe("runtime marketing and legal pages", () => {
  it("renders pricing plans and routes guests to registration", async () => {
    await renderElement(<PricingPlans surface="public" nonce="nonce-1" />)

    expect(container?.textContent).toContain("Plans for fiction authors")
    expect(container?.textContent).toContain("Free")
    expect(container?.textContent).toContain("Author")
    expect(container?.textContent).toContain("Architect")
    expect(container?.textContent).toContain("$19/mo")
    expect(container?.textContent).toContain("$39/mo")
    expect(container?.textContent).toContain("Paid checkout charges $19 now")
    expect(container?.textContent).toContain("Paid checkout charges $39 now")

    await clickByText("Create free account")
    await clickByText("Create account for free trial")

    expect(routerPush).toHaveBeenCalledWith("/register")
    expect(routerPush).toHaveBeenCalledTimes(2)
    expect(checkout).not.toHaveBeenCalled()
  })

  it("switches pricing cadence and handles signed-in plan actions", async () => {
    authUser = { id: "user-1", email: "author@example.com", trial_active: false }
    theme = "dark"
    checkoutPreview.mockResolvedValue({
      billing_enabled: false,
      message: "Billing is disabled locally.",
    })

    await renderElement(<PricingPlans surface="app" />)

    await clickByText("Yearly")
    expect(container?.textContent).toContain("Get two months free with yearly billing.")
    expect(container?.textContent).toContain("$190/year")
    expect(container?.textContent).toContain("$390/year")
    expect(container?.textContent).toContain("Save $38 with yearly billing")
    expect(container?.textContent).toContain("Save $78 with yearly billing")
    expect(container?.textContent).toContain("Paid checkout charges $190 now, then $190/year until canceled.")
    expect(container?.textContent).toContain("Paid checkout charges $390 now, then $390/year until canceled.")

    await clickByText("Included with your account")
    expect(container?.textContent).toContain("Free is included with every account.")

    await clickByText("Upgrade to Author")
    expect(checkoutPreview).toHaveBeenCalledWith("author_annual")
    expect(checkout).not.toHaveBeenCalled()
    expect(container?.textContent).toContain("Billing is disabled locally.")
  })

  it("requires an active trial user to acknowledge the immediate charge before checkout", async () => {
    authUser = {
      id: "trial-user",
      email: "trial@example.com",
      trial_active: true,
      trial_ends_at: "2099-09-08T10:00:00Z",
    }
    checkoutPreview.mockResolvedValue({
      plan: "author_monthly",
      display_name: "Author",
      billing_interval: "monthly",
      trial_status: "active",
      trial_active: true,
      trial_ends_at: "2099-09-08T10:00:00Z",
      charge_today: "$19.00 USD",
      recurring_price: "$19.00 USD every month",
      confirmation_required: true,
      confirmation_text: "I understand my trial is already active and I will be charged $19.00 USD now.",
      checkout_button_label: "Pay $19.00 USD now",
      default_action_label: "Continue free trial",
      quote_token: "signed-quote",
      billing_enabled: true,
      message: null,
    })
    checkout.mockResolvedValue({ billing_enabled: false, checkout_url: null, message: "Checkout failed safely." })

    await renderElement(<PricingPlans surface="app" />)

    expect(container?.textContent).toContain("Your free trial is already active")
    expect(container?.textContent).toContain("Author — temporary trial access")
    expect(container?.textContent).toContain("no subscription to cancel or refund")
    expect(container?.textContent).toContain("No payment is scheduled when it ends")
    await clickByText("View payment details")

    const dialog = document.body.querySelector('[role="dialog"]')
    expect(dialog?.textContent).toContain("Active — already started")
    expect(dialog?.textContent).toContain("Amount charged today$19.00 USD")
    expect(dialog?.textContent).toContain("Recurring price$19.00 USD every month until canceled")
    const payButton = Array.from(dialog?.querySelectorAll("button") ?? []).find((button) =>
      button.textContent?.includes("Pay $19.00 USD now")
    )
    expect(payButton?.disabled).toBe(true)
    expect(checkout).not.toHaveBeenCalled()

    const confirmation = dialog?.querySelector('input[type="checkbox"]') as HTMLInputElement | null
    await act(async () => {
      confirmation?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      await Promise.resolve()
    })
    expect(payButton?.disabled).toBe(false)
    await act(async () => {
      payButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      await Promise.resolve()
    })

    expect(checkout).toHaveBeenCalledWith("author_monthly", true, "signed-quote")
    expect(dialog?.querySelector('[role="alert"]')?.textContent).toContain("Checkout failed safely.")
  })

  it("shows the active paid plan and routes plan management to the billing portal", async () => {
    authUser = {
      id: "paid-user",
      email: "paid@example.com",
      tier: "author",
      plan_tier: "author",
      trial_active: false,
    }

    await renderElement(<PricingPlans surface="app" />)

    Object.defineProperty(window, "location", {
      configurable: true,
      value: { href: "http://localhost:3000/upgrade" },
    })

    expect(container?.textContent).toContain("Your current plan")
    expect(container?.textContent).toContain("Author")
    expect(container?.textContent).toContain("Manage billing / cancel subscription")
    expect(container?.querySelector('a[href="/refund"]')?.textContent).toContain("Refund policy")
    expect(container?.querySelector('a[href^="mailto:support@getlorevia.com"]')?.textContent).toContain("Request a refund")

    portal.mockResolvedValue({
      billing_enabled: true,
      portal_url: "https://billing.example.test/session",
    })
    await clickByText("Manage billing / cancel subscription")

    expect(portal).toHaveBeenCalledTimes(1)
    expect(checkoutPreview).not.toHaveBeenCalled()
    expect(window.location.href).toBe("https://billing.example.test/session")
  })

  it("cancels a still-pending transaction when Paddle checkout is closed", async () => {
    vi.stubEnv("NEXT_PUBLIC_PADDLE_CLIENT_TOKEN", "test_client_token")
    authUser = { id: "user-1", email: "author@example.com", trial_active: false }
    checkoutPreview.mockResolvedValue({
      plan: "author_monthly",
      display_name: "Author",
      billing_interval: "monthly",
      trial_status: "expired",
      trial_active: false,
      trial_ends_at: "2026-09-08T10:00:00Z",
      charge_today: "$19.00 USD",
      recurring_price: "$19.00 USD every month",
      confirmation_required: false,
      confirmation_text: null,
      checkout_button_label: "Pay $19.00 USD now",
      default_action_label: null,
      quote_token: "signed-quote",
      billing_enabled: true,
      message: null,
    })
    checkout.mockResolvedValue({
      billing_enabled: true,
      checkout_url: "https://getlorevia.com/checkout?_ptxn=txn_pending",
    })
    abandonCheckout.mockResolvedValue({
      abandoned: true,
      transaction_id: "txn_pending",
      status: "canceled",
    })
    const checkoutOpen = vi.fn()
    let eventCallback: ((event: { name?: string; data?: { transaction_id?: string } }) => void) | undefined
    window.Paddle = {
      Initialized: false,
      Checkout: { open: checkoutOpen },
      Environment: { set: vi.fn() },
      Initialize: (options) => {
        eventCallback = options.eventCallback
        if (window.Paddle) window.Paddle.Initialized = true
      },
    }

    await renderElement(<PricingPlans surface="app" />)
    await act(async () => {
      scriptOnLoad?.()
      await Promise.resolve()
    })
    await clickByText("Upgrade to Author")
    await clickByText("Pay $19.00 USD now")
    expect(checkoutOpen).toHaveBeenCalledWith(expect.objectContaining({ transactionId: "txn_pending" }))

    await act(async () => {
      eventCallback?.({ name: "checkout.closed", data: { transaction_id: "txn_pending" } })
      await Promise.resolve()
    })

    expect(abandonCheckout).toHaveBeenCalledWith("txn_pending")
  })

  it("updates Paddle's event callback when it was initialized by another page", async () => {
    vi.stubEnv("NEXT_PUBLIC_PADDLE_CLIENT_TOKEN", "test_client_token")
    const update = vi.fn()
    window.Paddle = {
      Initialized: true,
      Checkout: { open: vi.fn() },
      Environment: { set: vi.fn() },
      Initialize: vi.fn(),
      Update: update,
    }

    await renderElement(<PricingPlans surface="app" />)
    await act(async () => {
      scriptOnLoad?.()
      await Promise.resolve()
    })

    expect(update).toHaveBeenCalledWith({ eventCallback: expect.any(Function) })
  })

  it("renders homepage pricing in monthly and yearly modes", async () => {
    await renderElement(<HomePricingSection ctaHref="/register" />)

    expect(container?.textContent).toContain("$19/mo")
    expect(container?.textContent).toContain("$39/mo")
    expect(container?.textContent).toContain("Paid plan: $19/mo. The free trial does not auto-convert.")
    expect(container?.textContent).toContain("Paid plan: $39/mo. The free trial does not auto-convert.")

    await clickByText("Yearly")
    expect(container?.textContent).toContain("Get two months free with yearly billing.")
    expect(container?.textContent).toContain("$190/year")
    expect(container?.textContent).toContain("$390/year")
    expect(container?.textContent).toContain("Save $38 with yearly billing")
    expect(container?.textContent).toContain("Save $78 with yearly billing")
    expect(container?.textContent).toContain("Paid plan: $190/year. The free trial does not auto-convert.")
    expect(container?.textContent).toContain("Paid plan: $390/year. The free trial does not auto-convert.")
  })

  it("renders trust page facts, sections, contacts, and resource links", async () => {
    await renderElement(
      <TrustPage
        currentPath="/privacy"
        eyebrow="Privacy"
        title="How LoreVia protects author work"
        description="Plain-language policy summary for readers and writers."
        facts={[
          { label: "Encryption", value: "TLS", detail: "Traffic is encrypted in transit." },
          { label: "Ownership", value: "Yours", detail: "Authors retain rights to their manuscripts." },
          { label: "Support", value: "Email", detail: "Help is available for account issues." },
        ]}
        intro={["Introductory copy is accepted by the public page data shape."]}
        sections={[
          {
            title: "Data we process",
            paragraphs: ["We process account information and manuscript content to provide the service."],
            bullets: ["Account profile", "Uploaded manuscripts"],
          },
          {
            title: "Your controls",
            paragraphs: ["You can request account support and data help."],
          },
        ]}
        contacts={[
          {
            title: "Author support",
            description: "Help with account access.",
            ctaLabel: "support@example.com",
            ctaHref: "mailto:support@example.com",
          },
          {
            title: "Legal desk",
            description: "Formal legal requests.",
            ctaLabel: "legal@example.com",
            ctaHref: "mailto:legal@example.com",
          },
        ]}
      />,
    )

    expect(container?.textContent).toContain("LoreVia")
    expect(container?.textContent).toContain("How LoreVia protects author work")
    expect(container?.textContent).toContain("Quick summary")
    expect(container?.textContent).toContain("Data we process")
    expect(container?.textContent).toContain("Uploaded manuscripts")
    expect(container?.textContent).toContain("Author support")
    expect(container?.textContent).toContain("Service status")
    expect(container?.textContent).toContain("Report security issues responsibly")
  })
})
