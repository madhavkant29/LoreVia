import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"

const signInWithOAuthMock = vi.hoisted(() => vi.fn())
const supabaseMock = vi.hoisted(() => ({
  value: null as null | { auth: { signInWithOAuth: typeof signInWithOAuthMock } },
}))

vi.mock("@/lib/supabase", () => ({
  get supabase() {
    return supabaseMock.value
  },
}))

import { GoogleOAuthButton } from "./GoogleOAuthButton"

let container: HTMLDivElement | null = null
let root: Root | null = null

describe("GoogleOAuthButton", () => {
  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

  beforeEach(() => {
    signInWithOAuthMock.mockReset()
    signInWithOAuthMock.mockResolvedValue({})
    supabaseMock.value = { auth: { signInWithOAuth: signInWithOAuthMock } }
    window.sessionStorage.clear()
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

  it("starts Google OAuth and records the accepted terms state", async () => {
    const onError = vi.fn()
    renderButton(<GoogleOAuthButton acceptedTerms onError={onError} />)

    await clickButton()

    expect(window.sessionStorage.getItem("lorevia-oauth-accepted-terms")).toBe("true")
    expect(signInWithOAuthMock).toHaveBeenCalledWith({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    })
    expect(onError).not.toHaveBeenCalled()
  })

  it("reports missing configuration without starting OAuth", async () => {
    const onError = vi.fn()
    supabaseMock.value = null
    renderButton(<GoogleOAuthButton onError={onError} />)

    await clickButton()

    expect(onError).toHaveBeenCalledWith("Google sign-in is not configured right now.")
    expect(signInWithOAuthMock).not.toHaveBeenCalled()
  })

  it("requires accepted terms on registration surfaces", async () => {
    const onError = vi.fn()
    renderButton(<GoogleOAuthButton requireAcceptedTerms onError={onError} />)

    await clickButton()

    expect(onError).toHaveBeenCalledWith("Please accept the Terms, Compliance notice, and EULA before continuing with Google.")
    expect(signInWithOAuthMock).not.toHaveBeenCalled()
  })
})

function renderButton(ui: React.ReactNode) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  act(() => {
    root?.render(ui)
  })
}

async function clickButton() {
  await act(async () => {
    container?.querySelector("button")?.click()
    await Promise.resolve()
  })
}
