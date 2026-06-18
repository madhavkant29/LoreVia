// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"

const routerPush = vi.fn()
const checkout = vi.fn()
let authUser: unknown = null
let theme = "light"

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
}))

vi.mock("next/script", () => ({
  default: ({ onLoad }: { onLoad?: () => void }) => {
    void onLoad
    return null
  },
}))

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPush }),
}))

vi.mock("@/components/layout/BrandLockup", () => ({
  BrandLockup: () => <span>LoreVia</span>,
}))

vi.mock("@/lib/api/billing", () => ({
  billingApi: {
    checkout: (...args: unknown[]) => checkout(...args),
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

let root: Root | null = null
let container: HTMLDivElement | null = null

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
  const button = Array.from(container?.querySelectorAll("button") ?? []).find((item) =>
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
  authUser = null
  theme = "light"
})

describe("runtime marketing and legal pages", () => {
  it("renders pricing plans and routes guests to registration", async () => {
    await renderElement(<PricingPlans surface="public" nonce="nonce-1" />)

    expect(container?.textContent).toContain("Plans for fiction authors")
    expect(container?.textContent).toContain("Free")
    expect(container?.textContent).toContain("Author")
    expect(container?.textContent).toContain("Architect")

    await clickByText("Create free account")
    await clickByText("Create account for free trial")

    expect(routerPush).toHaveBeenCalledWith("/register")
    expect(routerPush).toHaveBeenCalledTimes(2)
    expect(checkout).not.toHaveBeenCalled()
  })

  it("switches pricing cadence and handles signed-in plan actions", async () => {
    authUser = { id: "user-1", email: "author@example.com" }
    theme = "dark"
    checkout.mockResolvedValue({
      billing_enabled: false,
      checkout_url: null,
      message: "Billing is disabled locally.",
    })

    await renderElement(<PricingPlans surface="app" />)

    await clickByText("Yearly")
    expect(container?.textContent).toContain("Save more with yearly billing.")
    expect(container?.textContent).toContain("Save $99 with yearly billing")

    await clickByText("Included with your account")
    expect(container?.textContent).toContain("Free is included with every account.")

    await clickByText("Upgrade to Author")
    expect(checkout).toHaveBeenCalledWith("author_annual")
    expect(container?.textContent).toContain("Billing is disabled locally.")
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
