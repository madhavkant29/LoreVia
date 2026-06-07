"use client"

import type { ReactNode } from "react"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import type { Route } from "next"
import { usePathname } from "next/navigation"

import { Button } from "@/components/ui/Button"
import { booksApi } from "@/lib/api/books"
import { BrandLockup } from "@/components/layout/BrandLockup"
import { ChatLauncher } from "@/components/layout/ChatLauncher"
import { NotificationBell } from "@/components/layout/NotificationBell"
import { asQueryKey, booksListCacheKey } from "@/lib/query/cacheKeys"
import { queryClient } from "@/lib/query/queryClient"
import { prefetchChatsSidebarData, prefetchNotificationsSidebarData } from "@/lib/query/sidebarPrefetch"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

type NavItem = {
  href: Route
  label: string
  icon: (className?: string) => ReactNode
  group?: "primary" | "secondary"
}

const NAV_ITEMS: NavItem[] = [
  { href: "/public/uploads", label: "Public Uploads", icon: UploadIcon },
  { href: "/library", label: "Library", icon: LibraryIcon },
  { href: "/notes", label: "Notes", icon: NotesIcon },
  { href: "/quotes", label: "Quotes", icon: QuotesIcon },
  { href: "/stats", label: "Stats", icon: StatsIcon },
  { href: "/series", label: "Series", icon: SeriesIcon },
  { href: "/beta-reads", label: "Beta Reads", icon: BetaReadsIcon },
  { href: "/upgrade", label: "Pricing", icon: PricingIcon, group: "secondary" },
  { href: "/settings", label: "Settings", icon: SettingsIcon, group: "secondary" },
]

function isActivePath(pathname: string, href: string) {
  if (href === "/public/uploads") return pathname === "/public/uploads" || pathname === "/public/analytics"
  return pathname === href
}

export function DashboardSidebar({ children }: { children: ReactNode }) {
  const { user } = useAuthStore()
  const authHydrated = useAuthStore((state) => state.hydrated)
  const { theme, toggleTheme } = usePreferencesStore()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [badgeQueriesEnabled, setBadgeQueriesEnabled] = useState(false)
  const sidebarPrefetchedRef = useRef(false)
  const libraryPrefetchedRef = useRef(false)
  const pathname = usePathname()
  const isDark = theme === "dark"
  const showUserChrome = authHydrated && !!user

  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])

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

  const profileInitial = useMemo(() => {
    const source = user?.username || user?.email || "?"
    return source.slice(0, 1).toUpperCase()
  }, [user?.email, user?.username])

  const accountName = user?.username ? `@${user.username}` : user?.email ?? "Account"
  const publicProfileHref = user?.username ? (`/public/writers/${user.username}` as Route) : null

  const handleLibraryPrefetch = useCallback(() => {
    if (libraryPrefetchedRef.current) return
    libraryPrefetchedRef.current = true
    queryClient.prefetchQuery({
      queryKey: asQueryKey(booksListCacheKey(true)),
      queryFn: () => booksApi.list(true),
    })
  }, [])

  return (
    <div className="min-h-screen bg-[#f4f6f8] text-stone-950 transition-colors duration-150 dark:bg-[rgb(20,24,27)] dark:text-[#efe9df]">
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-[15rem] flex-col border-r border-stone-200 bg-[#f4f6f8] transition-transform duration-150 dark:border-white/[0.12] dark:bg-[rgb(20,24,27)] lg:translate-x-0 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-[5.25rem] items-center px-5">
          <Link href="/library" onClick={() => setMobileOpen(false)} className="group flex items-center">
            <BrandLockup size="lg" className="transition-transform group-hover:scale-[1.02]" />
          </Link>
        </div>

        <nav className="flex-1 overflow-y-auto px-2.5 py-5">
          <div className="space-y-1">
            {NAV_ITEMS.map((item, index) => (
              <NavLink
                key={item.href}
                item={item}
                active={isActivePath(pathname, item.href)}
                separated={index > 0 && item.group === "secondary" && NAV_ITEMS[index - 1]?.group !== "secondary"}
                onClick={() => setMobileOpen(false)}
                onLibraryPrefetch={item.href === "/library" ? handleLibraryPrefetch : undefined}
              />
            ))}
          </div>
        </nav>

        {showUserChrome ? (
          <div className="p-2">
            <ProfileCard
              accountName={accountName}
              href={publicProfileHref}
              initial={profileInitial}
              tierLabel={user.tier_label}
              onNavigate={() => setMobileOpen(false)}
            />
          </div>
        ) : null}
      </aside>

      {mobileOpen ? (
        <button
          type="button"
          aria-label="Close navigation"
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      ) : null}

      <div className="min-h-screen lg:pl-[15rem]">
        <header className="sticky top-0 z-30 border-b border-stone-200 bg-[#f4f6f8] px-4 py-3 dark:border-white/[0.12] dark:bg-[rgb(20,24,27)]">
          <div className="mx-auto flex max-w-[1240px] items-center justify-between gap-4">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setMobileOpen((value) => !value)}
              className="h-10 w-10 rounded-sm px-0 py-0 lg:hidden"
              aria-label="Open navigation"
              aria-expanded={mobileOpen}
            >
              <MenuIcon />
            </Button>
            <div className="hidden lg:block" />

            <div className="ml-auto flex items-center gap-2">
              {showUserChrome ? <ChatLauncher enabled={badgeQueriesEnabled} /> : null}
              <NotificationBell enabled={badgeQueriesEnabled} />
              <Button
                variant="secondary"
                size="sm"
                onClick={toggleTheme}
                className="inline-flex h-11 w-11 items-center justify-center rounded-full px-0 py-0"
                aria-label="Toggle theme"
              >
                {isDark ? <SunIcon /> : <MoonIcon />}
              </Button>
            </div>
          </div>
        </header>

        <main className="relative mx-auto max-w-[1240px] px-4 py-8 md:px-8 lg:px-10">
          {children}
        </main>
      </div>
    </div>
  )
}

function ProfileCard({
  accountName,
  href,
  initial,
  tierLabel,
  onNavigate,
}: {
  accountName: string
  href: Route | null
  initial: string
  tierLabel: string
  onNavigate: () => void
}) {
  const content = (
    <div className="flex items-center gap-3">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-stone-200 bg-stone-100 text-sm font-semibold dark:border-white/10 dark:bg-white/[0.06]">
        {initial}
      </div>
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold">{accountName}</p>
        <p className="truncate text-xs text-[rgb(var(--muted-foreground))]">{tierLabel}</p>
      </div>
    </div>
  )
  const className =
    "block rounded-sm border border-stone-200 bg-white p-3 text-left transition-colors hover:bg-stone-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500/40 dark:border-white/[0.08] dark:bg-white/[0.03] dark:hover:bg-white/[0.06]"

  if (!href) {
    return <div className={className}>{content}</div>
  }

  return (
    <Link href={href} onClick={onNavigate} className={className} aria-label="Open author public profile">
      {content}
    </Link>
  )
}

function NavLink({
  item,
  active,
  separated,
  onClick,
  onLibraryPrefetch,
}: {
  item: NavItem
  active: boolean
  separated: boolean
  onClick: () => void
  onLibraryPrefetch?: () => void
}) {
  return (
    <div className={separated ? "mt-7 border-t border-stone-200 pt-5 dark:border-white/[0.08]" : undefined}>
      <Link
        href={item.href}
        onClick={onClick}
        onMouseEnter={onLibraryPrefetch}
        onFocus={onLibraryPrefetch}
        className={`group relative flex min-h-12 items-center gap-3 rounded-sm px-4 text-sm font-medium transition-colors ${
          active
            ? "bg-stone-200 text-stone-950 before:absolute before:bottom-0 before:left-0 before:top-0 before:w-1 before:bg-teal-400 dark:bg-white/[0.08] dark:text-white"
            : "text-[rgb(var(--muted-foreground))] hover:bg-stone-200/70 hover:text-stone-950 dark:hover:bg-white/[0.05] dark:hover:text-white"
        }`}
      >
        <span className={active ? "text-teal-500" : "text-current"}>{item.icon("h-5 w-5")}</span>
        <span>{item.label}</span>
      </Link>
    </div>
  )
}

function MenuIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  )
}

function SunIcon() {
  return (
    <svg className="h-5 w-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.4-6.4l-.7.7M6.3 17.7l-.7.7m12.8 0l-.7-.7M6.3 6.3l-.7-.7M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg className="h-5 w-5 text-teal-800" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M20.4 15.4A9 9 0 018.6 3.6 9 9 0 1012 21a9 9 0 008.4-5.6z" />
    </svg>
  )
}

function UploadIcon(className = "h-5 w-5") {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 15V4m0 0L8 8m4-4l4 4M5 14v4a2 2 0 002 2h10a2 2 0 002-2v-4" />
    </svg>
  )
}

function LibraryIcon(className = "h-5 w-5") {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 5.5A2.5 2.5 0 017.5 3H19v15H7.5A2.5 2.5 0 005 20.5v-15z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 5.5A2.5 2.5 0 007.5 8H19M9 8v10" />
    </svg>
  )
}

function NotesIcon(className = "h-5 w-5") {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <rect x="5" y="4" width="14" height="16" rx="2" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 9h8M8 13h6M8 17h4" />
    </svg>
  )
}

function QuotesIcon(className = "h-5 w-5") {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <rect x="4" y="5" width="16" height="14" rx="2.5" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 10h.01M14 10h.01M8 14h8" />
    </svg>
  )
}

function StatsIcon(className = "h-5 w-5") {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 19V11M12 19V5M18 19v-8" />
    </svg>
  )
}

function SeriesIcon(className = "h-5 w-5") {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <rect x="5" y="5" width="6" height="6" rx="1.5" />
      <rect x="13" y="13" width="6" height="6" rx="1.5" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M11 8h2.5A2.5 2.5 0 0116 10.5V13" />
    </svg>
  )
}

function BetaReadsIcon(className = "h-5 w-5") {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
    </svg>
  )
}

function PricingIcon(className = "h-5 w-5") {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <rect x="5" y="4" width="14" height="16" rx="2" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 9h6M9 13h6M9 17h3" />
    </svg>
  )
}

function SettingsIcon(className = "h-5 w-5") {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 8.5a3.5 3.5 0 110 7 3.5 3.5 0 010-7z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M19 12a7.2 7.2 0 00-.1-1.2l2-1.5-2-3.4-2.4 1a7 7 0 00-2-1.1L14.2 3h-4.4l-.3 2.8a7 7 0 00-2 1.1l-2.4-1-2 3.4 2 1.5A7.2 7.2 0 005 12c0 .4 0 .8.1 1.2l-2 1.5 2 3.4 2.4-1a7 7 0 002 1.1l.3 2.8h4.4l.3-2.8a7 7 0 002-1.1l2.4 1 2-3.4-2-1.5c.1-.4.1-.8.1-1.2z" />
    </svg>
  )
}
