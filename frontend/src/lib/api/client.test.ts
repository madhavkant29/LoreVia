import { beforeEach, describe, expect, it, vi } from "vitest"

const { axiosCreateMock, axiosPostMock, isAxiosErrorMock } = vi.hoisted(() => ({
  axiosCreateMock: vi.fn(),
  axiosPostMock: vi.fn(),
  isAxiosErrorMock: vi.fn(),
}))

vi.mock("axios", () => ({
  default: {
    create: axiosCreateMock,
    post: axiosPostMock,
    isAxiosError: isAxiosErrorMock,
  },
  create: axiosCreateMock,
  post: axiosPostMock,
  isAxiosError: isAxiosErrorMock,
}))

async function loadClientModule() {
  vi.resetModules()

  const captured: {
    request?: (config: Record<string, unknown>) => Record<string, unknown>
    responseSuccess?: (response: unknown) => unknown
    responseError?: (error: Record<string, any>) => Promise<unknown>
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
    isAxiosErrorMock.mockReset()
    vi.restoreAllMocks()
  })

  it("creates an axios client with the expected defaults", async () => {
    await loadClientModule()

    expect(axiosCreateMock).toHaveBeenCalledWith({
      baseURL: "/api/v1",
      headers: { "Content-Type": "application/json" },
      withCredentials: true,
    })
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

  it("passes successful responses through unchanged", async () => {
    const { captured } = await loadClientModule()
    const response = { data: { ok: true } }

    expect(captured.responseSuccess?.(response)).toBe(response)
  })

  it("refreshes and retries non-auth 401 responses", async () => {
    const { captured, apiClientMock } = await loadClientModule()
    const originalRequest = { url: "/books/1" }
    axiosPostMock.mockResolvedValue({ data: {} })
    apiClientMock.mockResolvedValue({ data: { retried: true } })

    const result = await captured.responseError?.({
      config: originalRequest,
      response: { status: 401 },
    })

    expect(axiosPostMock).toHaveBeenCalledWith("/api/v1/auth/refresh", null, { withCredentials: true })
    expect(originalRequest._retry).toBe(true)
    expect(apiClientMock).toHaveBeenCalledWith(originalRequest)
    expect(result).toEqual({ data: { retried: true } })
  })

  it("does not refresh auth me failures", async () => {
    const { captured } = await loadClientModule()
    const error = { config: { url: "/auth/me" }, response: { status: 401 } }

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
    let resolveRefresh: (() => void) | null = null
    axiosPostMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveRefresh = () => resolve({ data: {} })
        })
    )
    apiClientMock.mockResolvedValue({ data: { ok: true } })

    const first = captured.responseError?.({ config: { url: "/books/1" }, response: { status: 401 } })
    const second = captured.responseError?.({ config: { url: "/books/2" }, response: { status: 401 } })
    resolveRefresh?.()

    await Promise.all([first, second])
    expect(axiosPostMock).toHaveBeenCalledTimes(1)
    expect(apiClientMock).toHaveBeenCalledTimes(2)
  })
})
