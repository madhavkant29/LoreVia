import { beforeEach, describe, expect, it, vi } from "vitest"

const headersMock = vi.hoisted(() => vi.fn())
const cookiesMock = vi.hoisted(() => vi.fn())
const notFoundMock = vi.hoisted(() => vi.fn(() => {
  throw new Error("NEXT_NOT_FOUND")
}))

vi.mock("next/headers", () => ({
  cookies: cookiesMock,
  headers: headersMock,
}))

vi.mock("next/navigation", () => ({
  notFound: notFoundMock,
}))

describe("admin server api", () => {
  beforeEach(() => {
    vi.resetModules()
    headersMock.mockReset()
    cookiesMock.mockReset()
    cookiesMock.mockResolvedValue({ get: () => undefined })
    notFoundMock.mockClear()
    vi.unstubAllGlobals()
    vi.unstubAllEnvs()
    delete process.env.ADMIN_E2E_TEST_SECRET
    delete process.env.ADMIN_E2E_ALLOW_PRODUCTION
    delete process.env.API_ORIGIN
    delete process.env.NEXT_PUBLIC_E2E_MOCK_API
    delete process.env.NEXT_PUBLIC_API_URL
  })

  it("uses the dev-only owner cookie override without calling fetch", async () => {
    process.env.ADMIN_E2E_TEST_SECRET = "test-admin-secret"
    headersMock.mockResolvedValue(
      new Headers({
        cookie: "lorevia_admin_test_session=owner%3Atest-admin-secret",
      })
    )
    const fetchMock = vi.fn()
    vi.stubGlobal("fetch", fetchMock)

    const { getAdminSessionServer } = await import("./admin.server")
    const session = await getAdminSessionServer()

    expect(fetchMock).not.toHaveBeenCalled()
    expect(session.is_owner).toBe(true)
    expect(session.scopes).toEqual(["moderation_admin", "billing_admin", "super_admin"])
  })

  it("uses the dev-only owner header override without calling fetch", async () => {
    process.env.ADMIN_E2E_TEST_SECRET = "test-admin-secret"
    headersMock.mockResolvedValue(
      new Headers({
        "x-lorevia-admin-test-session": "owner:test-admin-secret",
      })
    )
    const fetchMock = vi.fn()
    vi.stubGlobal("fetch", fetchMock)

    const { getAdminSessionServer } = await import("./admin.server")
    const session = await getAdminSessionServer()

    expect(fetchMock).not.toHaveBeenCalled()
    expect(session.is_owner).toBe(true)
    expect(session.scopes).toEqual(["moderation_admin", "billing_admin", "super_admin"])
  })

  it("refuses the production override unless the server-only production acknowledgement is set", async () => {
    vi.stubEnv("NODE_ENV", "production")
    process.env.NEXT_PUBLIC_E2E_MOCK_API = "1"
    process.env.ADMIN_E2E_TEST_SECRET = "test-admin-secret"
    headersMock.mockResolvedValue(
      new Headers({
        cookie: "lorevia_admin_test_session=owner%3Atest-admin-secret",
      })
    )
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 403 })
    vi.stubGlobal("fetch", fetchMock)

    const { getAdminSessionServer } = await import("./admin.server")

    await expect(getAdminSessionServer()).rejects.toThrow("NEXT_NOT_FOUND")
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it("allows the production override only with mock mode, a secret, and the server acknowledgement", async () => {
    vi.stubEnv("NODE_ENV", "production")
    process.env.NEXT_PUBLIC_E2E_MOCK_API = "1"
    process.env.ADMIN_E2E_TEST_SECRET = "test-admin-secret"
    process.env.ADMIN_E2E_ALLOW_PRODUCTION = "1"
    headersMock.mockResolvedValue(
      new Headers({
        cookie: "lorevia_admin_test_session=owner%3Atest-admin-secret",
      })
    )
    const fetchMock = vi.fn()
    vi.stubGlobal("fetch", fetchMock)

    const { getAdminSessionServer } = await import("./admin.server")
    const session = await getAdminSessionServer()

    expect(fetchMock).not.toHaveBeenCalled()
    expect(session.is_owner).toBe(true)
  })

  it("404s when the dev-only guest cookie override is supplied", async () => {
    process.env.ADMIN_E2E_TEST_SECRET = "test-admin-secret"
    headersMock.mockResolvedValue(
      new Headers({
        cookie: "lorevia_admin_test_session=guest%3Atest-admin-secret",
      })
    )
    vi.stubGlobal("fetch", vi.fn())

    const { getAdminSessionServer } = await import("./admin.server")

    await expect(getAdminSessionServer()).rejects.toThrow("NEXT_NOT_FOUND")
    expect(notFoundMock).toHaveBeenCalled()
  })

  it("ignores invalid dev override cookies and falls back to backend auth", async () => {
    process.env.ADMIN_E2E_TEST_SECRET = "test-admin-secret"
    headersMock.mockResolvedValue(
      new Headers({
        cookie: "lorevia_admin_test_session=owner%3Awrong-secret; lorevia_access_token=token",
      })
    )
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        is_admin: true,
        scopes: ["moderation_admin"],
        is_owner: false,
        requires_step_up: true,
        session_expires_at: null,
      }),
    })
    vi.stubGlobal("fetch", fetchMock)

    const { getAdminSessionServer } = await import("./admin.server")
    const session = await getAdminSessionServer()

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(session.scopes).toEqual(["moderation_admin"])
  })

  it("forwards cookies to the backend admin session endpoint", async () => {
    process.env.NEXT_PUBLIC_API_URL = "http://localhost:8000/api/v1"
    headersMock.mockResolvedValue(
      new Headers({
        cookie: "lorevia_access_token=token",
      })
    )
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        is_admin: true,
        scopes: ["billing_admin"],
        is_owner: false,
        requires_step_up: false,
        session_expires_at: null,
      }),
    })
    vi.stubGlobal("fetch", fetchMock)

    const { getAdminSessionServer } = await import("./admin.server")
    const session = await getAdminSessionServer()

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/v1/admin/session", {
      cache: "no-store",
      headers: { cookie: "lorevia_access_token=token" },
    })
    expect(session.scopes).toEqual(["billing_admin"])
    expect(session.requires_step_up).toBe(false)
  })

  it("prefers the deployment server api origin for admin session checks", async () => {
    process.env.API_ORIGIN = "http://api:8000"
    process.env.NEXT_PUBLIC_API_URL = "https://public.example.com/api/v1"
    headersMock.mockResolvedValue(
      new Headers({
        cookie: "lorevia_access_token=token",
      })
    )
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        is_admin: true,
        scopes: ["super_admin"],
        is_owner: false,
        requires_step_up: true,
        session_expires_at: null,
      }),
    })
    vi.stubGlobal("fetch", fetchMock)

    const { getAdminSessionServer } = await import("./admin.server")
    const session = await getAdminSessionServer()

    expect(fetchMock).toHaveBeenCalledWith("http://api:8000/api/v1/admin/session", {
      cache: "no-store",
      headers: { cookie: "lorevia_access_token=token" },
    })
    expect(session.scopes).toEqual(["super_admin"])
  })

  it("404s when the backend rejects admin session access", async () => {
    headersMock.mockResolvedValue(new Headers())
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
    }))

    const { getAdminSessionServer } = await import("./admin.server")

    await expect(getAdminSessionServer()).rejects.toThrow("NEXT_NOT_FOUND")
    expect(notFoundMock).toHaveBeenCalled()
  })
})
