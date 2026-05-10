import { NextRequest } from "next/server"
import { afterEach, describe, expect, it } from "vitest"

import { buildContentSecurityPolicy, config, createNonce, middleware } from "../middleware"

describe("middleware CSP", () => {
  const originalEnv = { ...process.env }

  afterEach(() => {
    process.env = { ...originalEnv }
  })

  it("creates unique base64 nonces", () => {
    const first = createNonce()
    const second = createNonce()

    expect(first).not.toBe(second)
    expect(first).toMatch(/^[A-Za-z0-9+/=]+$/)
  })

  it("builds a CSP that includes nonce, api, analytics, and supabase origins", () => {
    Object.assign(process.env, {
      NEXT_PUBLIC_API_URL: "https://staging.getlorevia.com/api/v1",
      NEXT_PUBLIC_POSTHOG_HOST: "https://eu.i.posthog.com",
      NEXT_PUBLIC_SUPABASE_URL: "https://example-project.supabase.co",
    })

    const policy = buildContentSecurityPolicy("nonce-value")

    expect(policy).toContain("script-src 'self' 'nonce-nonce-value'")
    expect(policy).toContain("https://staging.getlorevia.com")
    expect(policy).toContain("https://eu.i.posthog.com")
    expect(policy).toContain("https://example-project.supabase.co")
    expect(policy).toContain("https://securepubads.g.doubleclick.net")
    expect(policy).toContain("https://googleads.g.doubleclick.net")
    expect(policy).toContain("wss://example-project.supabase.co")
    expect(policy).toContain("object-src 'none'")
  })

  it("skips non-production requests", () => {
    Object.assign(process.env, { NODE_ENV: "development" })

    const response = middleware(new NextRequest("https://getlorevia.com/login"))

    expect(response.headers.get("Content-Security-Policy")).toBeNull()
  })

  it("sets security headers and CSP for html routes in production", () => {
    Object.assign(process.env, {
      NODE_ENV: "production",
      NEXT_PUBLIC_POSTHOG_HOST: "https://eu.i.posthog.com",
      NEXT_PUBLIC_SUPABASE_URL: "https://example-project.supabase.co",
    })

    const response = middleware(new NextRequest("https://getlorevia.com/login"))
    const csp = response.headers.get("Content-Security-Policy") ?? ""
    const nonceMatch = csp.match(/'nonce-([^']+)'/)
    const scriptDirective = csp.split("; ").find((directive) => directive.startsWith("script-src")) ?? ""

    expect(response.headers.get("X-Frame-Options")).toBe("DENY")
    expect(response.headers.get("X-Content-Type-Options")).toBe("nosniff")
    expect(response.headers.get("Referrer-Policy")).toBe("strict-origin-when-cross-origin")
    expect(response.headers.get("Permissions-Policy")).toContain("camera=()")
    expect(csp).toContain("style-src 'self' 'unsafe-inline'")
    expect(scriptDirective).not.toContain("'unsafe-eval'")
    expect(scriptDirective).not.toContain("'unsafe-inline'")
    expect(nonceMatch?.[1]).toBeTruthy()
    expect(response.headers.get("x-middleware-request-content-security-policy")).toBe(csp)
    expect(response.headers.get("x-middleware-request-x-nonce")).toBe(nonceMatch?.[1] ?? null)
  })

  it("skips static assets and metadata routes", () => {
    Object.assign(process.env, { NODE_ENV: "production" })

    const staticResponse = middleware(new NextRequest("https://getlorevia.com/_next/static/chunk.js"))
    const manifestResponse = middleware(new NextRequest("https://getlorevia.com/manifest.webmanifest"))

    expect(staticResponse.headers.get("Content-Security-Policy")).toBeNull()
    expect(manifestResponse.headers.get("Content-Security-Policy")).toBeNull()
  })

  it("keeps the middleware matcher broad so all routes can be evaluated centrally", () => {
    expect(config.matcher).toBe("/:path*")
  })
})
