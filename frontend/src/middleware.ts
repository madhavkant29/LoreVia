import type { NextRequest } from "next/server"
import { NextResponse } from "next/server"
import { createServerClient } from "@supabase/ssr"

const NONCE_HEADER = "x-nonce"
const AUTHENTICATED_HOME_PATH = "/library"
const LOGIN_PATH = "/login"
const AUTH_COOKIE_NAMES = ["lorevia_access_token", "lorevia_refresh_token"]
const SECURITY_HEADERS = {
  "X-Frame-Options": "DENY",
  "X-Content-Type-Options": "nosniff",
  "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Permissions-Policy":
    "accelerometer=(), camera=(), display-capture=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()",
}

const AUTH_ENTRY_ROUTES = new Set([
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
])

const PUBLIC_PAGE_ROUTES = new Set([
  "/",
  "/answers",
  "/auth/callback",
  "/blog",
  "/checkout",
  "/checkout/success",
  "/compare",
  "/compliance",
  "/contact",
  "/copyright",
  "/demo",
  "/eula",
  "/pricing",
  "/privacy",
  "/public",
  "/refund",
  "/status",
  "/terms",
])

const PUBLIC_PAGE_PREFIXES = [
  "/answers/",
  "/blog/",
  "/compare/",
  "/demo/",
  "/public/",
]

const PRIVATE_PAGE_ROUTES = new Set([
  "/admin",
  "/beta-reads",
  "/chats",
  "/complete-username",
  "/library",
  "/notes",
  "/notifications",
  "/quotes",
  "/series",
  "/settings",
  "/stats",
  "/upgrade",
])

const PRIVATE_PAGE_PREFIXES = [
  "/library/",
  "/series/",
]

const NON_BOOK_TOP_LEVEL_SEGMENTS = new Set([
  "admin",
  "answers",
  "auth",
  "beta-reads",
  "blog",
  "chats",
  "checkout",
  "compare",
  "compliance",
  "complete-username",
  "contact",
  "copyright",
  "demo",
  "eula",
  "forgot-password",
  "library",
  "login",
  "notes",
  "notifications",
  "pricing",
  "privacy",
  "public",
  "quotes",
  "refund",
  "register",
  "reset-password",
  "series",
  "settings",
  "stats",
  "status",
  "terms",
  "upgrade",
  "verify-email",
])

function getOrigin(value: string | undefined) {
  if (!value) return null

  try {
    return new URL(value).origin
  } catch {
    return null
  }
}

function toWebSocketOrigin(origin: string | null) {
  if (!origin) return null

  try {
    const url = new URL(origin)
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:"
    return url.origin
  } catch {
    return null
  }
}

export function createNonce() {
  const bytes = new Uint8Array(16)
  crypto.getRandomValues(bytes)

  let binary = ""
  for (const byte of bytes) {
    binary += String.fromCharCode(byte)
  }

  return btoa(binary)
}

export function buildContentSecurityPolicy(nonce: string) {
  const apiOrigin = getOrigin(process.env.NEXT_PUBLIC_API_URL)
  const posthogOrigin = getOrigin(process.env.NEXT_PUBLIC_POSTHOG_HOST) ?? "https://eu.i.posthog.com"
  const supabaseOrigin = getOrigin(process.env.NEXT_PUBLIC_SUPABASE_URL)
  const supabaseWebSocketOrigin = toWebSocketOrigin(supabaseOrigin)

  const scriptSources = new Set([
    "'self'",
    `'nonce-${nonce}'`,
    "'strict-dynamic'",
    "https://cdn.paddle.com",
    "https://eu.posthog.com",
    "https://eu.i.posthog.com",
    "https://eu-assets.i.posthog.com",
    posthogOrigin,
  ])

  const imageSources = new Set([
    "'self'",
    "data:",
    "blob:",
    "https://getlorevia.com",
    "https://api.getlorevia.com",
  ])

  const connectSources = new Set([
    "'self'",
    "https://getlorevia.com",
    "https://api.getlorevia.com",
    "https://*.paddle.com",
    "https://eu.posthog.com",
    "https://eu.i.posthog.com",
    "https://eu-assets.i.posthog.com",
    posthogOrigin,
  ])

  for (const origin of [apiOrigin, supabaseOrigin]) {
    if (origin) {
      imageSources.add(origin)
      connectSources.add(origin)
    }
  }

  if (supabaseWebSocketOrigin) {
    connectSources.add(supabaseWebSocketOrigin)
  }

  return [
    "default-src 'self'",
    `script-src ${Array.from(scriptSources).join(" ")}`,
    "style-src 'self' 'unsafe-inline'",
    `img-src ${Array.from(imageSources).join(" ")}`,
    "font-src 'self' data:",
    `connect-src ${Array.from(connectSources).join(" ")}`,
    "frame-src 'self' https://*.paddle.com",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self' https://*.paddle.com",
    "object-src 'none'",
  ].join("; ")
}

function isNetlifyPreviewHost(hostname: string) {
  return hostname.endsWith(".netlify.app")
}

function shouldSkipMiddleware(pathname: string) {
  if (
    pathname.startsWith("/api") ||
    pathname.startsWith("/_next/static") ||
    pathname.startsWith("/_next/image") ||
    pathname.startsWith("/_next/data")
  ) {
    return true
  }

  if (
    pathname === "/favicon.ico" ||
    pathname === "/robots.txt" ||
    pathname === "/sitemap.xml" ||
    pathname === "/manifest.webmanifest"
  ) {
    return true
  }

  return /\.(?:avif|bmp|css|gif|ico|jpeg|jpg|js|json|map|png|svg|txt|webmanifest|webp|woff|woff2)$/i.test(pathname)
}

function normalizePathname(pathname: string) {
  if (pathname.length > 1 && pathname.endsWith("/")) {
    return pathname.slice(0, -1)
  }

  return pathname
}

export function isAuthEntryRoute(pathname: string) {
  return AUTH_ENTRY_ROUTES.has(normalizePathname(pathname))
}

export function isPublicPageRoute(pathname: string) {
  const normalizedPathname = normalizePathname(pathname)
  if (AUTH_ENTRY_ROUTES.has(normalizedPathname) || PUBLIC_PAGE_ROUTES.has(normalizedPathname)) {
    return true
  }

  return PUBLIC_PAGE_PREFIXES.some((prefix) => normalizedPathname.startsWith(prefix))
}

export function isPrivatePageRoute(pathname: string) {
  const normalizedPathname = normalizePathname(pathname)
  if (PRIVATE_PAGE_ROUTES.has(normalizedPathname)) {
    return true
  }

  if (PRIVATE_PAGE_PREFIXES.some((prefix) => normalizedPathname.startsWith(prefix))) {
    return true
  }

  const [topLevelSegment] = normalizedPathname.split("/").filter(Boolean)
  return Boolean(topLevelSegment && !NON_BOOK_TOP_LEVEL_SEGMENTS.has(topLevelSegment))
}

function hasAuthCookie(request: NextRequest) {
  // If the frontend interceptor determined the session is dead, do NOT treat
  // stale cookie bytes as valid auth — this breaks the /login ↔ /library loop.
  if (request.cookies.get("lorevia_session_dead")?.value === "1") return false

  return AUTH_COOKIE_NAMES.some((cookieName) => Boolean(request.cookies.get(cookieName)?.value))
}

function buildLoginRedirect(request: NextRequest) {
  const url = request.nextUrl.clone()
  const nextPath = `${request.nextUrl.pathname}${request.nextUrl.search}`

  url.pathname = LOGIN_PATH
  url.search = ""
  url.searchParams.set("next", nextPath)

  return NextResponse.redirect(url)
}

function buildAuthenticatedRedirect(request: NextRequest) {
  const url = request.nextUrl.clone()
  url.pathname = AUTHENTICATED_HOME_PATH
  url.search = ""

  return NextResponse.redirect(url)
}

function buildSecurityHeaders(request: NextRequest) {
  if (process.env.NODE_ENV !== "production") {
    return null
  }

  const nonce = createNonce()
  const csp = isNetlifyPreviewHost(request.nextUrl.hostname)
    ? `${buildContentSecurityPolicy(nonce)}; frame-src 'self' https://app.netlify.com`
    : buildContentSecurityPolicy(nonce)

  return { csp, nonce }
}

function applySecurityHeaders(
  request: NextRequest,
  response: NextResponse,
  security = buildSecurityHeaders(request),
) {
  if (!security) {
    return response
  }

  response.headers.set("Content-Security-Policy", security.csp)

  for (const [key, value] of Object.entries(SECURITY_HEADERS)) {
    response.headers.set(key, value)
  }

  return response
}

export function middleware(request: NextRequest) {
  if (shouldSkipMiddleware(request.nextUrl.pathname)) {
    return NextResponse.next()
  }

  const isAuthenticated = hasAuthCookie(request)

  // When the frontend interceptor signals that cookies are dead, scrub them
  // at the server level so the loop ends permanently (not just for 30 s).
  if (request.cookies.get("lorevia_session_dead")?.value === "1") {
    const response = isPrivatePageRoute(request.nextUrl.pathname)
      ? buildLoginRedirect(request)
      : NextResponse.next()
    for (const name of AUTH_COOKIE_NAMES) {
      response.cookies.set(name, "", { maxAge: 0, path: "/" })
    }
    response.cookies.set("lorevia_session_dead", "", { maxAge: 0, path: "/" })
    return applySecurityHeaders(request, response)
  }

  if (!isAuthenticated && isPrivatePageRoute(request.nextUrl.pathname)) {
    return applySecurityHeaders(request, buildLoginRedirect(request))
  }

  if (isAuthenticated && isAuthEntryRoute(request.nextUrl.pathname)) {
    return applySecurityHeaders(request, buildAuthenticatedRedirect(request))
  }

  // Initialize Supabase client for session management (auth routes and authenticated pages)
  let supabaseResponse = NextResponse.next()
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

  if (supabaseUrl && supabaseAnonKey) {
    supabaseResponse = NextResponse.next({
      request: {
        headers: request.headers,
      },
    })

    const supabase = createServerClient(supabaseUrl, supabaseAnonKey, {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) => {
            request.cookies.set(name, value)
          })
          supabaseResponse = NextResponse.next({
            request: {
              headers: request.headers,
            },
          })
          cookiesToSet.forEach(({ name, value, options }) => {
            supabaseResponse.cookies.set(name, value, options)
          })
        },
      },
    })

    // Refresh Supabase session if it exists - this ensures PKCE flow works correctly
    supabase.auth.getUser()
  }

  const security = buildSecurityHeaders(request)
  if (!security) {
    return supabaseResponse
  }

  const requestHeaders = new Headers(request.headers)
  requestHeaders.set(NONCE_HEADER, security.nonce)
  requestHeaders.set("Content-Security-Policy", security.csp)

  const response = NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  })

  // Copy Supabase cookies to final response
  if (supabaseUrl && supabaseAnonKey) {
    supabaseResponse.cookies.getAll().forEach((cookie) => {
      response.cookies.set(cookie.name, cookie.value)
    })
  }

  return applySecurityHeaders(request, response, security)
}

export const config = {
  matcher: "/:path*",
}
