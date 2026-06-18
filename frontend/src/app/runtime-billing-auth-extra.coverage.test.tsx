// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const routerMock = vi.hoisted(() => ({
  replace: vi.fn(),
}))
const searchState = vi.hoisted(() => ({
  value: "",
}))
const authApiMock = vi.hoisted(() => ({
  resendVerification: vi.fn(),
  verifyEmail: vi.fn(),
}))
const billingApiMock = vi.hoisted(() => ({
  confirmation: vi.fn(),
}))
const authStoreMock = vi.hoisted(() => ({
  setUser: vi.fn(),
}))

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
}))

vi.mock("next/script", () => ({
  default: ({ nonce, onError, onLoad, src }: { nonce?: string; onError?: () => void; onLoad?: () => void; src: string }) => (
    <div data-nonce={nonce} data-src={src}>
      <button type="button" onClick={onLoad}>Load Paddle script</button>
      <button type="button" onClick={onError}>Fail Paddle script</button>
    </div>
  ),
}))

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
  useSearchParams: () => new URLSearchParams(searchState.value),
}))

vi.mock("@/lib/api/auth", () => ({
  authApi: authApiMock,
}))

vi.mock("@/lib/api/billing", () => ({
  billingApi: billingApiMock,
}))

vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: (selector: (state: typeof authStoreMock) => unknown) => selector(authStoreMock),
}))

vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: () => ({ theme: "dark" }),
}))

import CheckoutSuccessPage from "@/app/checkout/success/page"
import VerifyEmailPage from "@/app/(auth)/verify-email/page"
import { PaddleCheckoutPage } from "@/components/billing/PaddleCheckoutPage"
import ScreenplayStats from "@/components/screenplay/ScreenplayStats"
import type { ScreenplayStats as ScreenplayStatsData } from "@/types/screenplay"

type PaddleEvent = {
  name: "checkout.closed" | "checkout.completed"
  data?: { transaction_id?: string }
}

type PaddleInitConfig = {
  eventCallback?: (event: PaddleEvent) => void
}

type PaddleWindow = Window & {
  Paddle?: {
    Initialized: boolean
    Environment: { set: ReturnType<typeof vi.fn> }
    Initialize: ReturnType<typeof vi.fn>
    Checkout: { open: ReturnType<typeof vi.fn> }
  }
}

let root: Root | null = null
let container: HTMLDivElement | null = null
let paddleInitConfig: PaddleInitConfig | null = null
const originalPaddleToken = process.env.NEXT_PUBLIC_PADDLE_CLIENT_TOKEN

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

beforeEach(() => {
  searchState.value = ""
  routerMock.replace.mockReset()
  authApiMock.resendVerification.mockReset()
  authApiMock.verifyEmail.mockReset()
  billingApiMock.confirmation.mockReset()
  authStoreMock.setUser.mockReset()
  process.env.NEXT_PUBLIC_PADDLE_CLIENT_TOKEN = "test_client_token"
  paddleInitConfig = null
  ;(window as PaddleWindow).Paddle = {
    Initialized: false,
    Environment: { set: vi.fn() },
    Initialize: vi.fn((config: PaddleInitConfig) => {
      paddleInitConfig = config
      const paddle = (window as PaddleWindow).Paddle
      if (paddle) paddle.Initialized = true
    }),
    Checkout: { open: vi.fn() },
  }
  billingApiMock.confirmation.mockResolvedValue({
    transaction_id: "txn_123",
    subscription_id: "sub_123",
    customer_email: "mira@example.com",
    display_name: "Architect",
    billing_interval: "annual",
    status: "active",
    total: "$120.00",
    invoice_number: "INV-1",
    invoice_pdf_url: "https://example.com/invoice.pdf",
  })
  authApiMock.verifyEmail.mockResolvedValue({ id: "user-1", email: "mira@example.com", username: "mira" })
  authApiMock.resendVerification.mockResolvedValue({})
})

afterEach(() => {
  if (root) {
    act(() => {
      root?.unmount()
    })
  }
  container?.remove()
  document.body.innerHTML = ""
  root = null
  container = null
  delete (window as PaddleWindow).Paddle
  process.env.NEXT_PUBLIC_PADDLE_CLIENT_TOKEN = originalPaddleToken
})

describe("billing, auth, and stats runtime coverage", () => {
  it("renders screenplay statistics with scene and dialogue insights", async () => {
    const stats: ScreenplayStatsData = {
      total_scenes: 4,
      total_dialogue_lines: 20,
      total_words: 3200,
      estimated_pages: 12,
      character_dialogue_counts: { Mara: 12, Theo: 8 },
      scene_types: { INT: 3, EXT: 1, OTHER: 0 },
    }

    await renderElement(<ScreenplayStats stats={stats} />)

    expect(container?.textContent).toContain("Screenplay Statistics")
    expect(container?.textContent).toContain("3 (75%)")
    expect(container?.textContent).toContain("Most talkative character: Mara (12 lines)")
    expect(container?.textContent).toContain("More interior scenes")
  })

  it("renders zero-state screenplay statistics without dividing scene counts", async () => {
    await renderElement(
      <ScreenplayStats
        stats={{
          total_scenes: 0,
          total_dialogue_lines: 0,
          total_words: 0,
          character_dialogue_counts: {},
          scene_types: { INT: 0, EXT: 0, OTHER: 0 },
        }}
      />,
    )

    expect(container?.textContent).toContain("Est. Pages")
    expect(container?.textContent).toContain("N/A")
    expect(container?.textContent).toContain("Average words per scene: 0")
  })

  it("verifies an email token and redirects verified users", async () => {
    searchState.value = "email=mira%40example.com&token=verify-token"

    await renderElement(<VerifyEmailPage />)
    await flushAsync()

    expect(authApiMock.verifyEmail).toHaveBeenCalledWith("verify-token")
    expect(authStoreMock.setUser).toHaveBeenCalledWith(expect.objectContaining({ username: "mira" }))
    expect(routerMock.replace).toHaveBeenCalledWith("/library")
  })

  it("resends verification emails and surfaces missing-email errors", async () => {
    searchState.value = "email=mira%40example.com"

    await renderElement(<VerifyEmailPage />)
    await clickButton("Resend verification email")

    expect(authApiMock.resendVerification).toHaveBeenCalledWith("mira@example.com")
    expect(container?.textContent).toContain("we sent a fresh email")

    cleanupRenderedTree()
    searchState.value = ""
    await renderElement(<VerifyEmailPage />)
    await clickButton("Resend verification email")

    expect(container?.textContent).toContain("Add your email to resend")
  })

  it("initializes Paddle checkout from a transaction link", async () => {
    searchState.value = "_ptxn=txn_123&lvct=confirm_1"

    await renderElement(<PaddleCheckoutPage nonce="nonce-1" />)
    await clickButton("Load Paddle script")

    const paddle = (window as PaddleWindow).Paddle
    expect(paddle?.Environment.set).toHaveBeenCalledWith("sandbox")
    expect(paddle?.Initialize).toHaveBeenCalled()
    expect(paddle?.Checkout.open).toHaveBeenCalledWith(expect.objectContaining({ transactionId: "txn_123" }))

    act(() => {
      paddleInitConfig?.eventCallback?.({ name: "checkout.closed" })
    })
    expect(container?.textContent).toContain("Checkout was closed")
  })

  it("handles missing checkout references and Paddle script failures", async () => {
    await renderElement(<PaddleCheckoutPage />)
    await clickButton("Fail Paddle script")
    expect(container?.textContent).toContain("could not be loaded")

    await clickButton("Open checkout again")
    expect(container?.textContent).toContain("missing its Paddle transaction reference")
  })

  it("loads checkout success confirmation details", async () => {
    searchState.value = "txn=txn_123&confirmation_token=confirm_1"

    await renderElement(<CheckoutSuccessPage />)
    await flushAsync()

    expect(billingApiMock.confirmation).toHaveBeenCalledWith("txn_123", "confirm_1")
    expect(container?.textContent).toContain("Payment confirmed")
    expect(container?.textContent).toContain("Architect Annual")
    expect(container?.textContent).toContain("INV-1")
    expect(container?.querySelector('a[href="https://example.com/invoice.pdf"]')).toBeTruthy()
  })

  it("shows checkout success fallback states for missing or delayed transaction confirmation", async () => {
    await renderElement(<CheckoutSuccessPage />)
    await flushAsync()

    expect(container?.textContent).toContain("Missing transaction reference")
    expect(billingApiMock.confirmation).not.toHaveBeenCalled()

    cleanupRenderedTree()
    searchState.value = "txn=txn_delayed"
    billingApiMock.confirmation.mockRejectedValueOnce(new Error("pending"))
    await renderElement(<CheckoutSuccessPage />)
    await flushAsync()

    expect(container?.textContent).toContain("Payment may still be processing")
  })
})

async function renderElement(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root?.render(element)
    await Promise.resolve()
  })
}

function cleanupRenderedTree() {
  if (root) {
    act(() => {
      root?.unmount()
    })
  }
  container?.remove()
  document.body.innerHTML = ""
  root = null
  container = null
}

async function flushAsync() {
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
    await new Promise((resolve) => window.setTimeout(resolve, 0))
  })
}

async function clickButton(text: string) {
  const button = Array.from(container?.querySelectorAll("button") ?? []).find((node) => node.textContent?.includes(text))
  expect(button, `button containing ${text}`).toBeTruthy()
  await act(async () => {
    button?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await Promise.resolve()
  })
}
