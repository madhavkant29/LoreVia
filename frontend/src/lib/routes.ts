const PUBLIC_PAGE_ROUTES = new Set([
  "/",
  "/blog",
  "/answers",
  "/compliance",
  "/contact",
  "/checkout",
  "/demo",
  "/eula",
  "/pricing",
  "/privacy",
  "/refund",
  "/status",
  "/terms",
])

const AUTH_BOOTSTRAP_EXCLUDED_PREFIXES = [
  "/auth/callback",
  "/answers",
  "/blog",
  "/checkout",
  "/complete-username",
  "/demo",
  "/forgot-password",
  "/login",
  "/public",
  "/register",
  "/reset-password",
  "/verify-email",
]

export function shouldSkipAuthBootstrap(pathname: string | null): boolean {
  if (!pathname) return false
  if (PUBLIC_PAGE_ROUTES.has(pathname)) return true
  return AUTH_BOOTSTRAP_EXCLUDED_PREFIXES.some((prefix) =>
    pathname === prefix || pathname.startsWith(`${prefix}/`)
  )
}
