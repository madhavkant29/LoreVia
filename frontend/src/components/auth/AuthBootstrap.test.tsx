import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

const usePathnameMock = vi.hoisted(() => vi.fn())
const useRouterMock = vi.hoisted(() => vi.fn(() => ({ replace: vi.fn(), push: vi.fn() })))
const sessionMock = vi.hoisted(() => vi.fn())
const shouldSkipAuthBootstrapMock = vi.hoisted(() => vi.fn())
const useAuthStoreMock = vi.hoisted(() => vi.fn())

vi.mock("next/navigation", () => ({
  usePathname: usePathnameMock,
  useRouter: useRouterMock,
}))

vi.mock("@/lib/api/auth", () => ({
  authApi: {
    session: sessionMock,
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
    useRouterMock.mockReset()
    sessionMock.mockReset()
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
    sessionMock.mockResolvedValue({ id: "user-1", username: "reader" })
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
    expect(sessionMock).toHaveBeenCalledTimes(1)
    expect(setUser).toHaveBeenCalledWith({ id: "user-1", username: "reader" })
  })

  it("restores a missing cached user with one session request", async () => {
    const setHydrated = vi.fn()
    const setUser = vi.fn()

    usePathnameMock.mockReturnValue("/library")
    shouldSkipAuthBootstrapMock.mockReturnValue(false)
    sessionMock.mockResolvedValue({ id: "user-2", username: "author" })
    useAuthStoreMock.mockReturnValue({
      user: null,
      setUser,
      setHydrated,
      logout: vi.fn(),
    })

    renderAuthBootstrap()

    await act(async () => {
      await Promise.resolve()
    })

    expect(sessionMock).toHaveBeenCalledTimes(1)
    expect(setUser).toHaveBeenCalledWith({ id: "user-2", username: "author" })
  })

  it("retains a cached user and offers a retry when the session service is unavailable", async () => {
    const logout = vi.fn()
    const setHydrated = vi.fn()
    const setUser = vi.fn()
    const replace = vi.fn()
    usePathnameMock.mockReturnValue("/library")
    useRouterMock.mockReturnValue({ replace, push: vi.fn() })
    shouldSkipAuthBootstrapMock.mockReturnValue(false)
    sessionMock.mockRejectedValueOnce(new Error("Network unavailable"))
      .mockResolvedValueOnce({ id: "user-1", username: "reader" })
    useAuthStoreMock.mockReturnValue({
      user: { id: "user-1" }, setUser, setHydrated, logout,
    })

    renderAuthBootstrap()
    await act(async () => { await Promise.resolve() })

    expect(logout).not.toHaveBeenCalled()
    expect(replace).not.toHaveBeenCalled()
    expect(container?.textContent).toContain("Could not verify your session")

    const retryButton = container?.querySelector("button")
    expect(retryButton?.textContent).toContain("Retry session check")
    await act(async () => { retryButton?.click(); await Promise.resolve() })

    expect(sessionMock).toHaveBeenCalledTimes(2)
    expect(setUser).toHaveBeenCalledWith({ id: "user-1", username: "reader" })
    expect(container?.textContent).not.toContain("Could not verify your session")
  })

  it("clears a cached user only after the session endpoint confirms 401", async () => {
    const logout = vi.fn()
    const replace = vi.fn()
    usePathnameMock.mockReturnValue("/library")
    useRouterMock.mockReturnValue({ replace, push: vi.fn() })
    shouldSkipAuthBootstrapMock.mockReturnValue(false)
    sessionMock.mockRejectedValue(Object.assign(new Error("Unauthorized"), {
      isAxiosError: true, response: { status: 401 },
    }))
    useAuthStoreMock.mockReturnValue({
      user: { id: "user-1" }, setUser: vi.fn(), setHydrated: vi.fn(), logout,
    })

    renderAuthBootstrap()
    await act(async () => { await Promise.resolve() })

    expect(logout).toHaveBeenCalledTimes(1)
    expect(replace).toHaveBeenCalledWith("/login?next=%2Flibrary")
  })

  it("does not claim a missing cache is a signed-out session during a server error", async () => {
    const replace = vi.fn()
    usePathnameMock.mockReturnValue("/library")
    useRouterMock.mockReturnValue({ replace, push: vi.fn() })
    shouldSkipAuthBootstrapMock.mockReturnValue(false)
    sessionMock.mockRejectedValue(Object.assign(new Error("Server error"), {
      isAxiosError: true, response: { status: 503 },
    }))
    useAuthStoreMock.mockReturnValue({
      user: null, setUser: vi.fn(), setHydrated: vi.fn(), logout: vi.fn(),
    })

    renderAuthBootstrap()
    await act(async () => { await Promise.resolve() })

    expect(replace).not.toHaveBeenCalled()
    expect(container?.textContent).toContain("Retry session check")
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
