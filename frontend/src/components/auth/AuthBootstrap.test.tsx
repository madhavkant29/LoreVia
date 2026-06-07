import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

const usePathnameMock = vi.hoisted(() => vi.fn())
const useRouterMock = vi.hoisted(() => vi.fn(() => ({ replace: vi.fn(), push: vi.fn() })))
const meMock = vi.hoisted(() => vi.fn())
const refreshMock = vi.hoisted(() => vi.fn())
const shouldSkipAuthBootstrapMock = vi.hoisted(() => vi.fn())
const useAuthStoreMock = vi.hoisted(() => vi.fn())

vi.mock("next/navigation", () => ({
  usePathname: usePathnameMock,
  useRouter: useRouterMock,
}))

vi.mock("@/lib/api/auth", () => ({
  authApi: {
    me: meMock,
    refresh: refreshMock,
  },
}))

vi.mock("@/lib/routes", () => ({
  shouldSkipAuthBootstrap: shouldSkipAuthBootstrapMock,
}))

vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: useAuthStoreMock,
}))

import { AuthBootstrap } from "./AuthBootstrap"

let container: HTMLDivElement | null = null
let root: Root | null = null

describe("AuthBootstrap", () => {
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
    usePathnameMock.mockReset()
    meMock.mockReset()
    refreshMock.mockReset()
    shouldSkipAuthBootstrapMock.mockReset()
    useAuthStoreMock.mockReset()
    container = null
    root = null
  })

  it("marks auth as hydrated immediately when a user already exists", async () => {
    const setHydrated = vi.fn()
    const setUser = vi.fn()

    usePathnameMock.mockReturnValue("/library")
    shouldSkipAuthBootstrapMock.mockReturnValue(false)
    meMock.mockResolvedValue({ id: "user-1", username: "reader" })
    useAuthStoreMock.mockReturnValue({
      user: { id: "user-1" },
      setUser,
      setHydrated,
      logout: vi.fn(),
    })

    renderAuthBootstrap()

    await act(async () => {
      await Promise.resolve()
    })

    expect(setHydrated).toHaveBeenCalledTimes(1)
    expect(meMock).toHaveBeenCalledTimes(1)
    expect(setUser).toHaveBeenCalledWith({ id: "user-1", username: "reader" })
  })
})

function renderAuthBootstrap() {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  act(() => {
    root?.render(<AuthBootstrap />)
  })

  return container
}
