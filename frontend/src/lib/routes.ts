const PUBLIC_PAGE_ROUTES = new Set([
  "/",
  "/compare",
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

const NON_BOOK_TOP_LEVEL_SEGMENTS = new Set([
  "answers",
  "auth",
  "beta-reads",
  "blog",
  "chats",
  "checkout",
  "compliance",
  "compare",
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
  "points",
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

const AUTH_BOOTSTRAP_EXCLUDED_PREFIXES = [
  "/auth/callback",
  "/answers",
  "/blog",
  "/checkout",
  "/compare",
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

export function shouldHideSiteFooter(pathname: string | null): boolean {
  if (!pathname || pathname === "/") return false

  const [topLevelSegment] = pathname.split("/").filter(Boolean)
  if (!topLevelSegment) return false

  return !NON_BOOK_TOP_LEVEL_SEGMENTS.has(topLevelSegment)
}
