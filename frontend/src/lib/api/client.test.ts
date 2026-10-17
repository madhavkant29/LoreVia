import { beforeEach, describe, expect, it, vi } from "vitest"

const {
  axiosCreateMock,
  axiosPostMock,
  axiosGetMock,
  isAxiosErrorMock,
  buildDailyCapEventDetailMock,
  dispatchDailyCapEventMock,
  captureApiFailureMock,
} = vi.hoisted(() => ({
  axiosCreateMock: vi.fn(),
  axiosPostMock: vi.fn(),
  axiosGetMock: vi.fn(),
  isAxiosErrorMock: vi.fn(),
  buildDailyCapEventDetailMock: vi.fn(),
  dispatchDailyCapEventMock: vi.fn(),
  captureApiFailureMock: vi.fn(),
}))

vi.mock("@/lib/analytics/browserTelemetry", () => ({
  captureApiFailure: captureApiFailureMock,
}))

vi.mock("axios", () => ({
  default: {
    create: axiosCreateMock,
    post: axiosPostMock,
    get: axiosGetMock,
    isAxiosError: isAxiosErrorMock,
  },
  create: axiosCreateMock,
  post: axiosPostMock,
  get: axiosGetMock,
  isAxiosError: isAxiosErrorMock,
}))

vi.mock("@/lib/limits/dailyCap", () => ({
  buildDailyCapEventDetail: buildDailyCapEventDetailMock,
  dispatchDailyCapEvent: dispatchDailyCapEventMock,
}))

async function loadClientModule() {
  vi.resetModules()

  const captured: {
    request?: (config: Record<string, unknown>) => Record<string, unknown>
    responseSuccess?: (response: unknown) => unknown
    responseError?: (error: Record<string, unknown>) => Promise<unknown>
  } = {}

  const apiClientMock = Object.assign(vi.fn(), {
    interceptors: {
      request: {
        use: vi.fn((handler) => {
          captured.request = handler
        }),
      },
      response: {
        use: vi.fn((success, error) => {
          captured.responseSuccess = success
          captured.responseError = error
        }),
      },
    },
  })

  axiosCreateMock.mockReturnValue(apiClientMock)
  const clientModule = await import("./client")

  return { ...clientModule, apiClientMock, captured }
}

describe("api client", () => {
  beforeEach(() => {
    axiosCreateMock.mockReset()
    axiosPostMock.mockReset()
    axiosGetMock.mockReset()
    isAxiosErrorMock.mockReset()
    buildDailyCapEventDetailMock.mockReset()
    dispatchDailyCapEventMock.mockReset()
    captureApiFailureMock.mockReset()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    process.env.VITEST = "true"
    delete process.env.NEXT_PUBLIC_API_URL
  })

  it("creates an axios client with the expected defaults", async () => {
    await loadClientModule()

    expect(axiosCreateMock).toHaveBeenCalledWith({
      baseURL: "/api/v1",
      headers: { "Content-Type": "application/json" },
      timeout: 60_000,
      withCredentials: true,
    })
  })

  it("keeps browser requests same-origin even when NEXT_PUBLIC_API_URL is set", async () => {
    process.env.NEXT_PUBLIC_API_URL = "http://localhost:8000/api/v1"

    await loadClientModule()

    expect(axiosCreateMock).toHaveBeenCalledWith({
      baseURL: "/api/v1",
      headers: { "Content-Type": "application/json" },
      timeout: 60_000,
      withCredentials: true,
    })
  })

  it("keeps localhost browser sessions same-origin so auth cookies are shared with middleware", async () => {
    const originalWindow = globalThis.window
    const originalVitest = process.env.VITEST
    delete process.env.VITEST
    vi.stubGlobal("window", { location: { hostname: "localhost", origin: "http://localhost:3000" } })

    try {
      await loadClientModule()

      expect(axiosCreateMock).toHaveBeenCalledWith({
        baseURL: "/api/v1",
        headers: { "Content-Type": "application/json" },
        timeout: 60_000,
        withCredentials: true,
      })
    } finally {
      vi.stubGlobal("window", originalWindow)
      if (originalVitest) process.env.VITEST = originalVitest
    }
  })

  it("removes uppercase content-type headers from FormData requests", async () => {
    const { captured } = await loadClientModule()
    const form = new FormData()

    const config = captured.request?.({
      data: form,
      headers: { "Content-Type": "multipart/form-data" },
    })

    expect(config?.headers).toEqual({})
  })

  it("removes lowercase content-type headers from FormData requests", async () => {
    const { captured } = await loadClientModule()
    const form = new FormData()

    const config = captured.request?.({
      data: form,
      headers: { "content-type": "multipart/form-data" },
    })

    expect(config?.headers).toEqual({})
  })

  it("leaves non-formdata request headers intact", async () => {
    const { captured } = await loadClientModule()

    const config = captured.request?.({
      data: { title: "LoreVia" },
      headers: { "Content-Type": "application/json" },
    })

    expect(config?.headers).toEqual({ "Content-Type": "application/json" })
  })

  it("uses a longer timeout for uploads and blob downloads without overriding custom values", async () => {
    const { captured } = await loadClientModule()

    const upload = captured.request?.({
      data: new FormData(),
      headers: {},
      timeout: 60_000,
    })
    const download = captured.request?.({
      headers: {},
      responseType: "blob",
      timeout: 60_000,
    })
    const custom = captured.request?.({
      data: new FormData(),
      headers: {},
      timeout: 900_000,
    })

    expect(upload?.timeout).toBe(600_000)
    expect(download?.timeout).toBe(600_000)
    expect(custom?.timeout).toBe(900_000)
  })

  it("adds the auth csrf header to unsafe requests when the cookie is present", async () => {
    const { captured } = await loadClientModule()
    const originalDocument = globalThis.document
    vi.stubGlobal("document", { cookie: "lorevia_csrf=csrf-token" })

    const config = captured.request?.({
      method: "post",
      url: "/books/1",
      headers: {},
    })

    expect(config?.headers).toEqual({ "X-CSRF-Token": "csrf-token" })
    vi.stubGlobal("document", originalDocument)
  })

  it("uses the last matching auth csrf cookie when duplicate values are present", async () => {
    const { captured } = await loadClientModule()
    const originalDocument = globalThis.document
    vi.stubGlobal("document", { cookie: "lorevia_csrf=stale-token; lorevia_csrf=fresh-token" })

    const config = captured.request?.({
      method: "patch",
      url: "/auth/me/username",
      headers: {},
    })

    expect(config?.headers).toEqual({ "X-CSRF-Token": "fresh-token" })
    vi.stubGlobal("document", originalDocument)
  })

  it("exposes the auth csrf header for browser keepalive requests", async () => {
    const { getAuthCsrfHeaders } = await loadClientModule()
    const originalDocument = globalThis.document
    vi.stubGlobal("document", { cookie: "lorevia_csrf=pagehide%20token" })

    expect(getAuthCsrfHeaders()).toEqual({ "X-CSRF-Token": "pagehide token" })
    vi.stubGlobal("document", originalDocument)
  })

  it("adds the admin csrf header alongside the auth csrf header for admin writes", async () => {
    const { captured } = await loadClientModule()
    const originalDocument = globalThis.document
    vi.stubGlobal("document", { cookie: "lorevia_csrf=csrf-token; lorevia_admin_csrf=admin-token" })

    const config = captured.request?.({
      method: "post",
      url: "/admin/access",
      headers: {},
    })

    expect(config?.headers).toEqual({
      "X-CSRF-Token": "csrf-token",
      "X-Admin-CSRF-Token": "admin-token",
    })
    vi.stubGlobal("document", originalDocument)
  })

  it("passes successful responses through unchanged", async () => {
    const { captured } = await loadClientModule()
    const response = { data: { ok: true } }

    expect(captured.responseSuccess?.(response)).toBe(response)
  })

  it("dispatches a daily cap event before handling the rejected response", async () => {
    const { captured } = await loadClientModule()
    const error = { config: { url: "/intelligence/book-1/qa" }, response: { status: 429 } }
    buildDailyCapEventDetailMock.mockReturnValue({
      action: "prediction",
      detail: "cap",
      requestPath: "/intelligence/book-1/qa",
      status: 429,
    })

    await expect(captured.responseError?.(error)).rejects.toBe(error)
    expect(buildDailyCapEventDetailMock).toHaveBeenCalledWith(error)
    expect(dispatchDailyCapEventMock).toHaveBeenCalledWith({
      action: "prediction",
      detail: "cap",
      requestPath: "/intelligence/book-1/qa",
      status: 429,
    })
    expect(captureApiFailureMock).toHaveBeenCalledWith(error)
  })

  it("refreshes and retries non-auth 401 responses", async () => {
    const { captured, apiClientMock } = await loadClientModule()
    const originalRequest: { url: string; _retry?: boolean } = { url: "/books/1" }
    const originalDocument = globalThis.document
    vi.stubGlobal("document", { cookie: "lorevia_csrf=csrf-token" })
    axiosPostMock.mockResolvedValue({ data: {} })
    apiClientMock.mockResolvedValue({ data: { retried: true } })

    const result = await captured.responseError?.({
      config: originalRequest,
      response: { status: 401 },
    })

    expect(axiosPostMock).toHaveBeenCalledWith("/api/v1/auth/refresh", null, {
      withCredentials: true,
      headers: { "X-CSRF-Token": "csrf-token" },
      timeout: 15_000,
    })
    expect(originalRequest._retry).toBe(true)
    expect(apiClientMock).toHaveBeenCalledWith(originalRequest)
    expect(result).toEqual({ data: { retried: true } })
    vi.stubGlobal("document", originalDocument)
  })

  it("bootstraps a missing CSRF cookie and retries CSRF-protected writes once", async () => {
    const { captured, apiClientMock } = await loadClientModule()
    const originalRequest: { url: string; _csrfRetry?: boolean } = { url: "/notifications/notification-1/read" }
    axiosGetMock.mockResolvedValue({ status: 204 })
    apiClientMock.mockResolvedValue({ data: { retried: true } })

    const result = await captured.responseError?.({
      config: originalRequest,
      response: { status: 403, data: { detail: "Invalid CSRF token." } },
    })

    expect(axiosGetMock).toHaveBeenCalledWith("/api/v1/auth/csrf", {
      withCredentials: true,
      timeout: 15_000,
    })
    expect(originalRequest._csrfRetry).toBe(true)
    expect(apiClientMock).toHaveBeenCalledWith(originalRequest)
    expect(result).toEqual({ data: { retried: true } })
  })

  it("keeps refresh requests same-origin in the browser even when NEXT_PUBLIC_API_URL is set", async () => {
    process.env.NEXT_PUBLIC_API_URL = "http://localhost:8000/api/v1"
    const { captured, apiClientMock } = await loadClientModule()
    const originalRequest: { url: string; _retry?: boolean } = { url: "/books/1" }
    axiosPostMock.mockResolvedValue({ data: {} })
    apiClientMock.mockResolvedValue({ data: { retried: true } })

    await captured.responseError?.({
      config: originalRequest,
      response: { status: 401 },
    })

    expect(axiosPostMock).toHaveBeenCalledWith("/api/v1/auth/refresh", null, {
      withCredentials: true,
      timeout: 15_000,
    })
  })

  it("does not refresh auth me failures", async () => {
    const { captured } = await loadClientModule()
    const error = { config: { url: "/auth/me" }, response: { status: 401 } }

    await expect(captured.responseError?.(error)).rejects.toBe(error)
    expect(axiosPostMock).not.toHaveBeenCalled()
  })

  it("does not refresh auth session failures", async () => {
    const { captured } = await loadClientModule()
    const error = { config: { url: "/auth/session" }, response: { status: 401 } }

    await expect(captured.responseError?.(error)).rejects.toBe(error)
    expect(axiosPostMock).not.toHaveBeenCalled()
  })

  it("does not refresh auth login failures", async () => {
    const { captured } = await loadClientModule()
    const error = { config: { url: "/auth/login" }, response: { status: 401 } }

    await expect(captured.responseError?.(error)).rejects.toBe(error)
    expect(axiosPostMock).not.toHaveBeenCalled()
  })

  it("does not refresh oauth auth failures", async () => {
    const { captured } = await loadClientModule()
    const error = { config: { url: "/auth/oauth/supabase" }, response: { status: 401 } }

    await expect(captured.responseError?.(error)).rejects.toBe(error)
    expect(axiosPostMock).not.toHaveBeenCalled()
  })

  it("does not retry requests that already have the retry flag", async () => {
    const { captured } = await loadClientModule()
    const error = { config: { url: "/books/1", _retry: true }, response: { status: 401 } }

    await expect(captured.responseError?.(error)).rejects.toBe(error)
    expect(axiosPostMock).not.toHaveBeenCalled()
  })

  it("redirects to login when refresh fails in the browser", async () => {
    const { captured } = await loadClientModule()
    const originalWindow = globalThis.window
    const replaceMock = vi.fn()
    axiosPostMock.mockRejectedValue(new Error("refresh failed"))
    const error = { config: { url: "/books/1" }, response: { status: 401 } }
    vi.stubGlobal("window", { location: { replace: replaceMock } })

    await expect(captured.responseError?.(error)).rejects.toBe(error)
    expect(replaceMock).toHaveBeenCalledWith("/login")
    vi.stubGlobal("window", originalWindow)
  })

  it("does not redirect when window is unavailable", async () => {
    const { captured } = await loadClientModule()
    const originalWindow = globalThis.window
    axiosPostMock.mockRejectedValue(new Error("refresh failed"))
    vi.stubGlobal("window", undefined)

    await expect(captured.responseError?.({ config: { url: "/books/1" }, response: { status: 401 } })).rejects.toMatchObject({
      response: { status: 401 },
    })

    vi.stubGlobal("window", originalWindow)
  })

  it("reuses one refresh request across concurrent 401s", async () => {
    const { captured, apiClientMock } = await loadClientModule()
    let refreshCreated = false
    let resolveRefresh: () => void = () => {
      throw new Error("refresh promise was not created")
    }
    axiosPostMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          refreshCreated = true
          resolveRefresh = () => resolve({ data: {} })
        })
    )
    apiClientMock.mockResolvedValue({ data: { ok: true } })

    const first = captured.responseError?.({ config: { url: "/books/1" }, response: { status: 401 } })
    const second = captured.responseError?.({ config: { url: "/books/2" }, response: { status: 401 } })
    if (!refreshCreated) {
      throw new Error("refresh promise was not created")
    }
    resolveRefresh()

    await Promise.all([first, second])
    expect(axiosPostMock).toHaveBeenCalledTimes(1)
    expect(apiClientMock).toHaveBeenCalledTimes(2)
  })
})
