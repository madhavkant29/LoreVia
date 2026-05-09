import { beforeEach, describe, expect, it, vi } from "vitest"

const { getMock, postMock, patchMock, isAxiosErrorMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  postMock: vi.fn(),
  patchMock: vi.fn(),
  isAxiosErrorMock: vi.fn(),
}))

vi.mock("./client", () => ({
  apiClient: {
    get: getMock,
    post: postMock,
    patch: patchMock,
  },
}))

vi.mock("axios", () => ({
  default: {
    isAxiosError: isAxiosErrorMock,
  },
  isAxiosError: isAxiosErrorMock,
}))

import { authApi } from "./auth"

describe("auth api", () => {
  beforeEach(() => {
    getMock.mockReset()
    postMock.mockReset()
    patchMock.mockReset()
    isAxiosErrorMock.mockReset()

    postMock.mockResolvedValue({ data: { ok: true } })
    getMock.mockResolvedValue({ data: { ok: true } })
    patchMock.mockResolvedValue({ data: { ok: true } })
  })

  it("registers with the expected payload", async () => {
    await authApi.register("reader@example.com", "reader", "Secret123!", true, "device-1")

    expect(postMock).toHaveBeenCalledWith("/auth/register", {
      email: "reader@example.com",
      username: "reader",
      password: "Secret123!",
      accepted_terms: true,
      device_id: "device-1",
    })
  })

  it("logs in with email and password", async () => {
    await authApi.login("reader@example.com", "Secret123!")

    expect(postMock).toHaveBeenCalledWith("/auth/login", {
      email: "reader@example.com",
      password: "Secret123!",
    })
  })

  it("logs in with a supabase token and default accepted terms", async () => {
    await authApi.loginWithSupabaseToken("supabase-token", "device-2")

    expect(postMock).toHaveBeenCalledWith("/auth/oauth/supabase", {
      token: "supabase-token",
      accepted_terms: false,
      device_id: "device-2",
    })
  })

  it("logs in with a supabase token and explicit accepted terms", async () => {
    await authApi.loginWithSupabaseToken("supabase-token", "device-2", true)

    expect(postMock).toHaveBeenCalledWith("/auth/oauth/supabase", {
      token: "supabase-token",
      accepted_terms: true,
      device_id: "device-2",
    })
  })

  it("verifies email tokens", async () => {
    await authApi.verifyEmail("verify-token")

    expect(postMock).toHaveBeenCalledWith("/auth/verify-email", { token: "verify-token" })
  })

  it("resends verification emails", async () => {
    await authApi.resendVerification("reader@example.com")

    expect(postMock).toHaveBeenCalledWith("/auth/resend-verification", { email: "reader@example.com" })
  })

  it("starts forgot password flows", async () => {
    await authApi.forgotPassword("reader@example.com")

    expect(postMock).toHaveBeenCalledWith("/auth/forgot-password", { email: "reader@example.com" })
  })

  it("resets passwords with token and new password", async () => {
    await authApi.resetPassword("reset-token", "NewSecret123!")

    expect(postMock).toHaveBeenCalledWith("/auth/reset-password", {
      token: "reset-token",
      password: "NewSecret123!",
    })
  })

  it("refreshes the auth session", async () => {
    await authApi.refresh()

    expect(postMock).toHaveBeenCalledWith("/auth/refresh")
  })

  it("logs out the current session", async () => {
    await authApi.logout()

    expect(postMock).toHaveBeenCalledWith("/auth/logout")
  })

  it("returns the current user on me success", async () => {
    getMock.mockResolvedValue({ data: { id: "user-1" } })

    await expect(authApi.me()).resolves.toEqual({ id: "user-1" })
  })

  it("returns null on me when the backend responds with 401", async () => {
    const error = { response: { status: 401 } }
    getMock.mockRejectedValue(error)
    isAxiosErrorMock.mockReturnValue(true)

    await expect(authApi.me()).resolves.toBeNull()
  })

  it("rethrows me failures that are not unauthorized axios errors", async () => {
    const error = { response: { status: 500 } }
    getMock.mockRejectedValue(error)
    isAxiosErrorMock.mockReturnValue(true)

    await expect(authApi.me()).rejects.toBe(error)
  })

  it("updates the reading mode using a query string", async () => {
    await authApi.setReadingMode("author")

    expect(patchMock).toHaveBeenCalledWith("/auth/me/reading-mode?mode=author")
  })

  it("updates the daily word goal with the api payload shape", async () => {
    await authApi.setDailyWordGoal(1200)

    expect(patchMock).toHaveBeenCalledWith("/auth/me/daily-word-goal", { daily_word_goal: 1200 })
  })

  it("updates the username with request params", async () => {
    await authApi.setUsername("new-handle")

    expect(patchMock).toHaveBeenCalledWith("/auth/me/username", null, {
      params: { username: "new-handle" },
    })
  })

  it("loads tier limits from the auth api", async () => {
    await authApi.getTierLimits()

    expect(getMock).toHaveBeenCalledWith("/auth/tier-limits")
  })
})
