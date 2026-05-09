import type { NextRequest } from "next/server"
import { NextResponse } from "next/server"

const NONCE_HEADER = "x-nonce"
const SECURITY_HEADERS = {
  "X-Frame-Options": "DENY",
  "X-Content-Type-Options": "nosniff",
  "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Permissions-Policy":
    "accelerometer=(), camera=(), display-capture=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()",
}

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
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
  ].join("; ")
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

export function middleware(request: NextRequest) {
  if (process.env.NODE_ENV !== "production" || shouldSkipMiddleware(request.nextUrl.pathname)) {
    return NextResponse.next()
  }

  const nonce = createNonce()
  const csp = buildContentSecurityPolicy(nonce)
  const requestHeaders = new Headers(request.headers)
  requestHeaders.set(NONCE_HEADER, nonce)

  const response = NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  })

  response.headers.set("Content-Security-Policy", csp)

  for (const [key, value] of Object.entries(SECURITY_HEADERS)) {
    response.headers.set(key, value)
  }

  return response
}

export const config = {
  matcher: "/:path*",
}
