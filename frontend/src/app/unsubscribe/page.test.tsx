import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"

const unsubscribeMock = vi.hoisted(() => vi.fn())
const searchParamsState = vi.hoisted(() => ({ token: "token-123" }))

vi.mock("next/image", () => ({
  default: ({ alt = "", priority: _priority, ...props }: React.ImgHTMLAttributes<HTMLImageElement> & { priority?: boolean }) => <img alt={alt} {...props} />,
}))

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>{children}</a>
  ),
}))

vi.mock("next/navigation", () => ({
  useSearchParams: () => ({
    get: (key: string) => (key === "token" ? searchParamsState.token : null),
  }),
}))

vi.mock("@/lib/api/email", () => ({
  emailApi: {
    unsubscribe: unsubscribeMock,
  },
}))

import UnsubscribePage from "./page"

let container: HTMLDivElement | null = null
let root: Root | null = null

describe("UnsubscribePage", () => {
  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

  beforeEach(() => {
    searchParamsState.token = "token-123"
    unsubscribeMock.mockReset()
    unsubscribeMock.mockResolvedValue({
      email: "author@example.com",
      product_updates: false,
      marketing: false,
      unsubscribed_all: true,
    })
  })

  afterAll(() => {
    delete (globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT
  })

  afterEach(() => {
    if (root) {
      act(() => {
        root?.unmount()
      })
    }
    container?.remove()
    container = null
    root = null
  })

  it("submits the token and confirms promotional email unsubscribe", async () => {
    const view = await renderUnsubscribePage()

    expect(unsubscribeMock).toHaveBeenCalledWith("token-123")
    expect(view.textContent).toContain("You are unsubscribed")
    expect(view.textContent).toContain("author@example.com")
    expect(view.textContent).toContain("product updates or marketing emails")
  })

  it("does not submit when the token is missing", async () => {
    searchParamsState.token = ""

    const view = await renderUnsubscribePage()

    expect(unsubscribeMock).not.toHaveBeenCalled()
    expect(view.textContent).toContain("missing a token")
  })

  it("shows a recoverable error when the unsubscribe token is rejected", async () => {
    unsubscribeMock.mockRejectedValue(new Error("expired"))

    const view = await renderUnsubscribePage()

    expect(unsubscribeMock).toHaveBeenCalledWith("token-123")
    expect(view.textContent).toContain("We could not unsubscribe you")
    expect(view.textContent).toContain("expired or already used")
  })

  it("reuses the in-flight request when the page remounts with the same token", async () => {
    let resolveUnsubscribe: ((value: {
      email: string
      product_updates: boolean
      marketing: boolean
      unsubscribed_all: boolean
    }) => void) | null = null
    unsubscribeMock.mockReturnValue(
      new Promise((resolve) => {
        resolveUnsubscribe = resolve
      }),
    )

    await renderUnsubscribePage()

    act(() => {
      root?.unmount()
    })
    container?.remove()
    root = null
    container = null

    const view = await renderUnsubscribePage()
    expect(unsubscribeMock).toHaveBeenCalledTimes(1)

    await act(async () => {
      resolveUnsubscribe?.({
        email: "author@example.com",
        product_updates: false,
        marketing: false,
        unsubscribed_all: true,
      })
      await Promise.resolve()
    })

    expect(view.textContent).toContain("You are unsubscribed")
  })
})

async function renderUnsubscribePage() {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  act(() => {
    root?.render(<UnsubscribePage />)
  })
  await act(async () => {
    await Promise.resolve()
  })

  return container
}
