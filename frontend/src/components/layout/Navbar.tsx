"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import type { Route } from "next"
import { usePathname, useRouter } from "next/navigation"

import { Button } from "@/components/ui/Button"
import { authApi } from "@/lib/api/auth"
import { clearAuthCookies } from "@/lib/api/client"
import { booksApi } from "@/lib/api/books"
import { BrandLockup } from "@/components/layout/BrandLockup"
import { ChatLauncher } from "@/components/layout/ChatLauncher"
import { NotificationBell } from "@/components/layout/NotificationBell"
import { asQueryKey, booksListCacheKey } from "@/lib/query/cacheKeys"
import { queryClient } from "@/lib/query/queryClient"
import { prefetchChatsSidebarData, prefetchNotificationsSidebarData } from "@/lib/query/sidebarPrefetch"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

function formatMemberSince(value?: string | null) {
  if (!value) return "Unknown"
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return "Unknown"
  return parsed.toLocaleDateString("en-US", { month: "short", year: "numeric" })
}

export function Navbar() {
  const { user, logout } = useAuthStore()
  const authHydrated = useAuthStore((state) => state.hydrated)
  const { theme, toggleTheme } = usePreferencesStore()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [profileMenuOpen, setProfileMenuOpen] = useState(false)
  const [badgeQueriesEnabled, setBadgeQueriesEnabled] = useState(false)
  const profileMenuRef = useRef<HTMLDivElement | null>(null)
  const sidebarPrefetchedRef = useRef(false)
  const router = useRouter()
  const pathname = usePathname()

  const isDark = theme === "dark"
  const showUserChrome = authHydrated && !!user

  const handleLogout = async () => {
    // Clear client state IMMEDIATELY before API call to prevent race conditions
    logout()
    document.cookie = "lorevia_session_dead=1; Max-Age=30; Path=/; Secure; SameSite=Lax"
    clearAuthCookies()
    setMobileMenuOpen(false)
    setProfileMenuOpen(false)
    router.replace("/login")
    
    // Then make the API call in background (don't await)
    authApi.logout().catch(() => {
      // ignore logout errors - client state already cleared
    })
  }

  useEffect(() => {
    function handleClick(event: MouseEvent) {
      if (!profileMenuRef.current) return
      if (event.target instanceof Node && !profileMenuRef.current.contains(event.target)) {
        setProfileMenuOpen(false)
      }
    }

    document.addEventListener("mousedown", handleClick)
    return () => document.removeEventListener("mousedown", handleClick)
  }, [])

  useEffect(() => {
    if (!user || !authHydrated || badgeQueriesEnabled) return

    const scheduleEnablement =
      typeof window.requestIdleCallback === "function"
        ? window.requestIdleCallback.bind(window)
        : ((callback: IdleRequestCallback) =>
            window.setTimeout(() => callback({ didTimeout: false, timeRemaining: () => 0 } as IdleDeadline), 150))
    const cancelEnablement =
      typeof window.cancelIdleCallback === "function"
        ? window.cancelIdleCallback.bind(window)
        : window.clearTimeout.bind(window)

    const handle = scheduleEnablement(() => {
      setBadgeQueriesEnabled(true)
      if (!sidebarPrefetchedRef.current) {
        sidebarPrefetchedRef.current = true
        void prefetchNotificationsSidebarData()
        void prefetchChatsSidebarData()
      }
    })

    return () => cancelEnablement(handle)
  }, [authHydrated, badgeQueriesEnabled, user])

  const navItems: Array<{ href: Route; label: string }> = [
    { href: "/library", label: "Library" },
    { href: "/notes", label: "Notes" },
    { href: "/quotes", label: "Quotes" },
    { href: "/stats", label: "Stats" },
    { href: "/series", label: "Series" },
    { href: "/beta-reads", label: "Beta Reads" },
    { href: "/upgrade", label: "Pricing" },
    { href: "/settings", label: "Settings" },
  ]

  const profileInitial = useMemo(() => {
    const source = user?.username || user?.email || "?"
    return source.slice(0, 1).toUpperCase()
  }, [user?.email, user?.username])

  const libraryPrefetchedRef = useRef(false)

  const handleLibraryPrefetch = useCallback(() => {
    if (libraryPrefetchedRef.current) return
    libraryPrefetchedRef.current = true
    queryClient.prefetchQuery({
      queryKey: asQueryKey(booksListCacheKey(true)),
      queryFn: () => booksApi.list(true),
    })
  }, [])

  const publicProfileHref = user?.username ? (`/public/writers/${user.username}` as Route) : null

  return (
    <nav className="sticky top-0 z-30 border-b border-[rgba(var(--border),0.9)] bg-[rgb(243,244,246)] px-4 py-4 transition-colors duration-150 dark:bg-[rgb(20,24,27)]">
      <div className="mx-auto flex max-w-7xl flex-col gap-4">
        <div className="flex items-center justify-between gap-4">
          <Link href="/library" className="group flex items-center">
            <BrandLockup
              size="xl"
              className="transition-transform group-hover:scale-[1.02]"
            />
          </Link>

          <div className="flex items-center gap-2">
            {showUserChrome ? <ChatLauncher enabled={badgeQueriesEnabled} /> : null}
            <NotificationBell enabled={badgeQueriesEnabled} />

            {showUserChrome ? (
              <div className="relative" ref={profileMenuRef}>
                <Button
                  variant={profileMenuOpen ? "primary" : "secondary"}
                  size="sm"
                  onClick={() => setProfileMenuOpen((value) => !value)}
                  aria-label="Open profile menu"
                  className="h-10 w-10 rounded-full"
                >
                  {profileInitial}
                </Button>

                {profileMenuOpen ? (
                  <div className={`absolute right-0 top-full z-40 mt-2 w-72 overflow-hidden rounded-md border ${isDark ? "border-white/10 bg-[#1f2528]" : "border-[rgba(var(--border),0.9)] bg-[rgb(255,252,247)]"}`}>
                    <div className={`border-b px-4 py-4 ${isDark ? "border-white/10" : "border-[rgba(var(--border),0.9)]"}`}>
                      <p className="text-base font-semibold">{user.username ? `@${user.username}` : user.email}</p>
                      <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-600"}`}>{user.email}</p>
                      <div className="mt-3 flex flex-wrap gap-2 text-xs">
                        <span className={`rounded-full px-3 py-1 font-semibold ${isDark ? "bg-white/10 text-white" : "bg-stone-100 text-stone-900"}`}>{user.tier_label}</span>
                        <span className={`rounded-full px-3 py-1 ${isDark ? "bg-white/5 text-slate-300" : "bg-stone-50 text-stone-600"}`}>Member since {formatMemberSince(user.created_at)}</span>
                      </div>
                    </div>
                    <div className="p-2">
                      <Link href="/settings" onClick={() => setProfileMenuOpen(false)} className={`block rounded-xl px-3 py-2.5 text-sm ${isDark ? "text-slate-200 hover:bg-white/[0.06]" : "text-stone-700 hover:bg-stone-50"}`}>
                        Settings
                      </Link>
                      {publicProfileHref ? (
                        <Link href={publicProfileHref} onClick={() => setProfileMenuOpen(false)} className={`block rounded-xl px-3 py-2.5 text-sm ${isDark ? "text-slate-200 hover:bg-white/[0.06]" : "text-stone-700 hover:bg-stone-50"}`}>
                          Public writer profile
                        </Link>
                      ) : null}
                      <Button
                        variant="ghost"
                        size="md"
                        onClick={() => void handleLogout()}
                        className={`w-full justify-start rounded-xl ${isDark ? "text-rose-300 hover:bg-rose-500/10" : "text-rose-600 hover:bg-rose-50"}`}
                      >
                        Sign out
                      </Button>
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}

            <Button
              variant="secondary"
              size="sm"
              onClick={toggleTheme}
              className="h-10 w-10 rounded-xl"
              aria-label="Toggle theme"
            >
              {isDark ? (
                <svg className="h-5 w-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707m12.728 0l-.707-.707M6.343 6.364l-.707-.707M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              ) : (
                <svg className="h-5 w-5 text-teal-800" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                </svg>
              )}
            </Button>

            <Button
              variant="secondary"
              size="sm"
              onClick={() => setMobileMenuOpen((v) => !v)}
              className="h-10 w-10 rounded-xl lg:hidden"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={mobileMenuOpen ? "M6 18L18 6M6 6l12 12" : "M4 6h16M4 12h16M4 18h16"} />
              </svg>
            </Button>
          </div>
        </div>

        <div className={`${mobileMenuOpen ? "block" : "hidden"} lg:block`}>
          <div className="flex flex-wrap items-center gap-1 lg:justify-center">
            <Link
              href="/public/uploads"
              onClick={() => setMobileMenuOpen(false)}
              className={`relative rounded-xl px-4 py-2 text-sm font-semibold tracking-tight transition-colors duration-150 ${
                pathname === "/public/uploads" || pathname === "/public/analytics"
                  ? "bg-teal-700/10 text-teal-800 dark:bg-teal-400/15 dark:text-teal-200"
                  : "text-[rgb(var(--muted-foreground))] hover:bg-[rgba(var(--muted),0.85)] hover:text-[rgb(var(--foreground))]"
              }`}
            >
              Public Uploads
            </Link>
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileMenuOpen(false)}
                onMouseEnter={item.href === "/library" ? handleLibraryPrefetch : undefined}
                onFocus={item.href === "/library" ? handleLibraryPrefetch : undefined}
                className={`relative rounded-xl px-4 py-2 text-sm font-semibold tracking-tight transition-colors duration-150 ${
                  pathname === item.href
                    ? "bg-teal-700/10 text-teal-800 dark:bg-teal-400/15 dark:text-teal-200"
                    : "text-[rgb(var(--muted-foreground))] hover:bg-[rgba(var(--muted),0.85)] hover:text-[rgb(var(--foreground))]"
                }`}
              >
                {item.label}
                {pathname === item.href && (
                  <span className="absolute bottom-0 left-4 right-4 h-0.5 rounded-full bg-teal-800 dark:bg-teal-300" />
                )}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </nav>
  )
}
