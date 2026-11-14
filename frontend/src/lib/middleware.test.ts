import { NextRequest } from "next/server"
import { afterEach, describe, expect, it } from "vitest"

import {
  buildContentSecurityPolicy,
  config,
  createNonce,
  isPrivatePageRoute,
  isPublicPageRoute,
  middleware,
} from "../middleware"

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

  it("builds a CSP that includes nonce, strict-dynamic, api, analytics, and supabase origins", () => {
    Object.assign(process.env, {
      NEXT_PUBLIC_API_URL: "https://staging.getlorevia.com/api/v1",
      NEXT_PUBLIC_POSTHOG_HOST: "https://eu.i.posthog.com",
      NEXT_PUBLIC_SUPABASE_URL: "https://example-project.supabase.co",
    })

    const policy = buildContentSecurityPolicy("nonce-value")

    expect(policy).toContain("script-src 'self' 'nonce-nonce-value' 'strict-dynamic'")
    expect(policy).toContain("https://staging.getlorevia.com")
    expect(policy).toContain("https://eu.i.posthog.com")
    expect(policy).toContain("https://example-project.supabase.co")
    expect(policy).toContain("wss://example-project.supabase.co")
    expect(policy).toContain("frame-src 'self' https://*.paddle.com https://www.youtube-nocookie.com")
    expect(policy).toContain("object-src 'none'")
    expect(policy).not.toContain("https://securepubads.g.doubleclick.net")
    expect(policy).not.toContain("https://googleads.g.doubleclick.net")
  })

  it("skips non-production requests", () => {
    Object.assign(process.env, { NODE_ENV: "development" })

    const response = middleware(new NextRequest("https://getlorevia.com/login"))

    expect(response.headers.get("Content-Security-Policy")).toBeNull()
  })

  it("redirects unauthenticated users from private pages to login with next", () => {
    Object.assign(process.env, { NODE_ENV: "development" })

    const response = middleware(new NextRequest("https://getlorevia.com/library"))

    expect(response.headers.get("location")).toBe("https://getlorevia.com/login?next=%2Flibrary")
    expect(response.headers.get("Cache-Control")).toBe(
      "private, no-store, no-cache, max-age=0, must-revalidate"
    )
  })

  it("preserves the target query string in login next redirects", () => {
    Object.assign(process.env, { NODE_ENV: "development" })

    const response = middleware(new NextRequest("https://getlorevia.com/library?sort=recent"))

    expect(response.headers.get("location")).toBe("https://getlorevia.com/login?next=%2Flibrary%3Fsort%3Drecent")
    expect(response.headers.get("Cache-Control")).toContain("private")
    expect(response.headers.get("Cache-Control")).toContain("no-store")
  })

  it("redirects unauthenticated users from private book routes to login", () => {
    Object.assign(process.env, { NODE_ENV: "development" })

    const response = middleware(new NextRequest("https://getlorevia.com/sky-of-ash--book-1/manuscript"))

    expect(response.headers.get("location")).toBe(
      "https://getlorevia.com/login?next=%2Fsky-of-ash--book-1%2Fmanuscript"
    )
  })

  it("allows authenticated users to visit auth entry pages to validate their session", () => {
    Object.assign(process.env, { NODE_ENV: "development" })

    const request = new NextRequest("https://getlorevia.com/login?next=%2Fstats", {
      headers: {
        cookie: "lorevia_refresh_token=refresh-token",
      },
    })
    const response = middleware(request)

    // Should NOT redirect - let the auth page validate the session client-side
    // This prevents redirect loops when users have stale/expired sessions
    expect(response.headers.get("location")).toBeNull()
  })

  it("allows public pages for authenticated and unauthenticated users", () => {
    Object.assign(process.env, { NODE_ENV: "development" })

    const guestResponse = middleware(new NextRequest("https://getlorevia.com/blog/how-to-revise"))
    const authResponse = middleware(new NextRequest("https://getlorevia.com/public/forum", {
      headers: {
        cookie: "lorevia_access_token=access-token",
      },
    }))

    expect(guestResponse.headers.get("location")).toBeNull()
    expect(authResponse.headers.get("location")).toBeNull()
  })

  it("classifies known public page routes as non-private", () => {
    const publicRoutes = [
      "/",
      "/answers",
      "/answers/how-do-i-track-character-arcs",
      "/auth/callback",
      "/blog",
      "/blog/how-to-keep-track-of-characters",
      "/checkout",
      "/checkout/success",
      "/compare",
      "/compare/lorevia-vs-scrivener",
      "/compliance",
      "/contact",
      "/copyright",
      "/demo",
      "/demo/gregor-samsa-character-tracker",
      "/eula",
      "/pricing",
      "/privacy",
      "/public",
      "/public/analytics",
      "/public/forum",
      "/public/forum/forum-post-1",
      "/public/uploads",
      "/public/writers/author",
      "/public/public-book-1",
      "/public/public-book-1/chapter/1",
      "/refund",
      "/status",
      "/terms",
      "/unsubscribe",
    ]

    for (const route of publicRoutes) {
      expect(isPublicPageRoute(route), route).toBe(true)
      expect(isPrivatePageRoute(route), route).toBe(false)
    }
  })

  it("classifies auth entry routes as public but not private", () => {
    for (const route of ["/login", "/register", "/forgot-password", "/reset-password", "/verify-email"]) {
      expect(isPublicPageRoute(route), route).toBe(true)
      expect(isPrivatePageRoute(route), route).toBe(false)
    }
  })

  it("classifies known private page routes", () => {
    const privateRoutes = [
      "/admin",
      "/beta-reads",
      "/chats",
      "/complete-username",
      "/library",
      "/library/add-chapter",
      "/notes",
      "/notifications",
      "/quotes",
      "/series",
      "/series/series-1/ask",
      "/settings",
      "/stats",
      "/upgrade",
      "/sky-of-ash--book-1",
      "/sky-of-ash--book-1/advisor",
      "/sky-of-ash--book-1/analysis",
      "/sky-of-ash--book-1/ask",
      "/sky-of-ash--book-1/author-loop",
      "/sky-of-ash--book-1/beta-feedback",
      "/sky-of-ash--book-1/chapter/1",
      "/sky-of-ash--book-1/chapters",
      "/sky-of-ash--book-1/characters",
      "/sky-of-ash--book-1/collaboration",
      "/sky-of-ash--book-1/compliance",
      "/sky-of-ash--book-1/cross-book-wiki",
      "/sky-of-ash--book-1/editorial-review",
      "/sky-of-ash--book-1/export",
      "/sky-of-ash--book-1/foreshadowing",
      "/sky-of-ash--book-1/graph",
      "/sky-of-ash--book-1/manuscript",
      "/sky-of-ash--book-1/notes",
      "/sky-of-ash--book-1/plot-threads",
      "/sky-of-ash--book-1/relationship-evolution",
      "/sky-of-ash--book-1/reports",
      "/sky-of-ash--book-1/scenes",
      "/sky-of-ash--book-1/search",
      "/sky-of-ash--book-1/summaries",
      "/sky-of-ash--book-1/timeline",
      "/sky-of-ash--book-1/voice",
      "/sky-of-ash--book-1/world-gap",
    ]

    for (const route of privateRoutes) {
      expect(isPublicPageRoute(route), route).toBe(false)
      expect(isPrivatePageRoute(route), route).toBe(true)
    }
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
    expect(response.headers.get("Permissions-Policy")).toContain("payment=()")
    expect(csp).toContain("style-src 'self' 'unsafe-inline'")
    expect(scriptDirective).not.toContain("'unsafe-eval'")
    expect(scriptDirective).not.toContain("'unsafe-inline'")
    expect(nonceMatch?.[1]).toBeTruthy()
    expect(response.headers.get("x-middleware-request-content-security-policy")).toBe(csp)
    expect(response.headers.get("x-middleware-request-x-nonce")).toBe(nonceMatch?.[1] ?? null)
  })

  it("adds the Netlify preview frame source without relaxing the payment policy", () => {
    Object.assign(process.env, { NODE_ENV: "production" })

    const response = middleware(new NextRequest("https://lorevia-preview.netlify.app/login"))
    const csp = response.headers.get("Content-Security-Policy") ?? ""

    expect(csp).toContain("frame-src 'self' https://*.paddle.com")
    expect(csp).toContain("; frame-src 'self' https://app.netlify.com")
    expect(response.headers.get("Permissions-Policy")).toContain("payment=()")
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
