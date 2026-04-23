"use client"
import { useState } from "react"
import Link from "next/link"
import type { Route } from "next"
import { usePathname, useRouter } from "next/navigation"
import { authApi } from "@/lib/api/auth"
import { NotificationBell } from "@/components/layout/NotificationBell"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

export function Navbar() {
  const { user, logout } = useAuthStore()
  const { theme, toggleTheme } = usePreferencesStore()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
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
    router.replace("/login")
  }

  const navItems: Array<{ href: Route; label: string }> = [
    { href: "/library", label: "Library" },
    { href: "/notes", label: "Notes" },
    { href: "/stats", label: "Stats" },
    { href: "/series", label: "Series" },
    { href: "/pricing", label: "Pricing" },
    { href: "/settings", label: "Settings" },
  ]

  return (
    <nav className="sticky top-0 z-30 border-b border-border bg-background/80 px-4 py-4 backdrop-blur-xl transition-all duration-300">
      <div className="mx-auto flex max-w-7xl flex-col gap-4">
        <div className="flex items-center justify-between gap-4">
          <Link href="/library" className="group flex items-center">
            <img 
              src="/image.png" 
              alt="LoreVia" 
              className="h-10 w-10 rounded-xl object-cover shadow-lg shadow-brand-500/20 transition-transform group-hover:scale-105"
            />
          </Link>

          <div className="flex items-center gap-2">
            <NotificationBell />
            <button
              onClick={toggleTheme}
              className="group relative flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-card hover:bg-muted transition-colors"
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

            {user && (
              <button
                onClick={handleLogout}
                className="hidden sm:flex rounded-xl px-4 py-2 text-sm font-semibold text-muted-foreground hover:text-foreground hover:bg-muted transition-all"
              >
                Sign out
              </button>
            )}

            <button
              onClick={() => setMobileMenuOpen((v) => !v)}
              className="lg:hidden flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-card text-foreground"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={mobileMenuOpen ? "M6 18L18 6M6 6l12 12" : "M4 6h16M4 12h16M4 18h16"} />
              </svg>
            </button>
          </div>
        </div>

        <div className={`${mobileMenuOpen ? "block" : "hidden"} lg:block`}>
          <div className="flex flex-wrap items-center gap-1">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileMenuOpen(false)}
                className={`relative px-4 py-2 text-sm font-bold tracking-tight transition-all rounded-lg ${
                  pathname === item.href
                    ? "text-brand-600 bg-brand-500/5 dark:text-brand-400"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted"
                }`}
              >
                {item.label}
                {pathname === item.href && (
                  <span className="absolute bottom-0 left-4 right-4 h-0.5 bg-brand-500 rounded-full" />
                )}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </nav>
  )
}
