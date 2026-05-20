"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import type { Route } from "next"
import { usePathname, useRouter } from "next/navigation"

import { authApi } from "@/lib/api/auth"
import { BrandLockup } from "@/components/layout/BrandLockup"
import { ChatLauncher } from "@/components/layout/ChatLauncher"
import { NotificationBell } from "@/components/layout/NotificationBell"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

function formatMemberSince(value?: string | null) {
  if (!value) return "Unknown"
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return "Unknown"
  return parsed.toLocaleDateString(undefined, { month: "short", year: "numeric" })
}

export function Navbar() {
  const { user, logout } = useAuthStore()
  const authHydrated = useAuthStore((state) => state.hydrated)
  const { theme, toggleTheme } = usePreferencesStore()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [profileMenuOpen, setProfileMenuOpen] = useState(false)
  const [badgeQueriesEnabled, setBadgeQueriesEnabled] = useState(false)
  const profileMenuRef = useRef<HTMLDivElement | null>(null)
  const router = useRouter()
  const pathname = usePathname()

  const isDark = theme === "dark"

  const handleLogout = async () => {
    try {
      await authApi.logout()
    } catch {
      // ignore logout errors
    }
    logout()
    setMobileMenuOpen(false)
    setProfileMenuOpen(false)
    router.replace("/login")
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
    })

    return () => cancelEnablement(handle)
  }, [authHydrated, badgeQueriesEnabled, user])

  const navItems: Array<{ href: Route; label: string }> = [
    { href: "/library", label: "Library" },
    { href: "/notes", label: "Notes" },
    { href: "/quotes", label: "Quotes" },
    { href: "/stats", label: "Stats" },
    { href: "/series", label: "Series" },
    { href: "/upgrade", label: "Pricing" },
    { href: "/settings", label: "Settings" },
  ]

  const profileInitial = useMemo(() => {
    const source = user?.username || user?.email || "?"
    return source.slice(0, 1).toUpperCase()
  }, [user?.email, user?.username])

  const publicProfileHref = user?.username ? (`/public/writers/${user.username}` as Route) : null

  return (
    <nav className="sticky top-0 z-30 border-b border-border bg-background px-4 py-4 transition-colors duration-150">
      <div className="mx-auto flex max-w-7xl flex-col gap-4">
        <div className="flex items-center justify-between gap-4">
          <Link href="/library" className="group flex items-center">
            <BrandLockup
              size="sm"
              className="transition-transform group-hover:scale-[1.02]"
              iconClassName="h-10 w-10 rounded-xl"
              textClassName="text-slate-900 dark:text-white"
            />
          </Link>

          <div className="flex items-center gap-2">
            <ChatLauncher enabled={badgeQueriesEnabled} />
            <NotificationBell enabled={badgeQueriesEnabled} />
            <Link
              href="/public/uploads"
              className={`hidden sm:inline-flex items-center rounded-lg border px-4 py-2 text-sm font-semibold transition-colors duration-150 ${
                pathname === "/public/uploads" || pathname === "/public/analytics"
                  ? "border-sky-400/40 bg-sky-500/10 text-sky-600 dark:text-sky-300"
                  : "border-border bg-card text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              Public Uploads
            </Link>

            {user ? (
              <div className="relative" ref={profileMenuRef}>
                <button
                  type="button"
                  onClick={() => setProfileMenuOpen((value) => !value)}
                  aria-label="Open profile menu"
                  className={`flex h-10 w-10 items-center justify-center rounded-full border text-sm font-semibold transition-colors duration-150 ${
                    profileMenuOpen
                      ? "border-sky-400/40 bg-sky-500/10 text-sky-600 dark:text-sky-300"
                      : "border-border bg-card text-foreground hover:bg-muted"
                  }`}
                >
                  {profileInitial}
                </button>

                {profileMenuOpen ? (
                  <div className={`absolute right-0 top-full z-40 mt-2 w-72 overflow-hidden rounded-2xl border shadow-[0_25px_80px_-40px_rgba(0,0,0,0.85)] ${isDark ? "border-white/10 bg-[#12121a]" : "border-stone-200 bg-white"}`}>
                    <div className={`border-b px-4 py-4 ${isDark ? "border-white/10" : "border-stone-200"}`}>
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
                      <button
                        type="button"
                        onClick={() => void handleLogout()}
                        className={`block w-full rounded-xl px-3 py-2.5 text-left text-sm ${isDark ? "text-rose-300 hover:bg-rose-500/10" : "text-rose-600 hover:bg-rose-50"}`}
                      >
                        Sign out
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}

            <button
              onClick={toggleTheme}
              className="group relative flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-card hover:bg-muted transition-colors duration-150"
              aria-label="Toggle theme"
            >
              {isDark ? (
                <svg className="h-5 w-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707m12.728 0l-.707-.707M6.343 6.364l-.707-.707M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              ) : (
                <svg className="h-5 w-5 text-brand-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                </svg>
              )}
            </button>

            <button
              onClick={() => setMobileMenuOpen((v) => !v)}
              className="lg:hidden flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-card text-foreground"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={mobileMenuOpen ? "M6 18L18 6M6 6l12 12" : "M4 6h16M4 12h16M4 18h16"} />
              </svg>
            </button>
          </div>
        </div>

        <div className={`${mobileMenuOpen ? "block" : "hidden"} lg:block`}>
          <div className="flex flex-wrap items-center gap-1 lg:justify-center">
            <Link
              href="/public/uploads"
              onClick={() => setMobileMenuOpen(false)}
              className={`relative px-4 py-2 text-sm font-semibold tracking-tight transition-colors duration-150 rounded-md ${
                pathname === "/public/uploads" || pathname === "/public/analytics"
                  ? "text-slate-900 bg-slate-100 dark:text-white dark:bg-slate-800"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              }`}
            >
              Public Uploads
            </Link>
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileMenuOpen(false)}
                className={`relative px-4 py-2 text-sm font-semibold tracking-tight transition-colors duration-150 rounded-md ${
                  pathname === item.href
                    ? "text-slate-900 bg-slate-100 dark:text-white dark:bg-slate-800"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted"
                }`}
              >
                {item.label}
                {pathname === item.href && (
                  <span className="absolute bottom-0 left-4 right-4 h-0.5 bg-slate-900 dark:bg-white rounded-full" />
                )}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </nav>
  )
}
