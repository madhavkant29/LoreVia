"use client"
import { useState } from "react"
import Link from "next/link"
import { authApi } from "@/lib/api/auth"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

export function Navbar() {
  const { user, logout } = useAuthStore()
  const { theme, toggleTheme } = usePreferencesStore()
  const isDark = theme === "dark"
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const handleLogout = async () => {
    try {
      await authApi.logout()
    } catch {}
    logout()
    if (typeof window !== "undefined") {
      window.location.href = "/login"
    }
  }

  const navItems = [
    { href: "/library", label: "Library" },
    { href: "/public", label: "Public" },
    { href: "/quotes", label: "Quotes" },
    { href: "/series", label: "Series" },
    { href: "/pricing", label: "Pricing" },
    { href: "/settings", label: "Settings" },
  ]

  return (
    <nav className={`sticky top-0 z-20 border-b px-4 py-4 backdrop-blur-xl transition-colors ${
      isDark
        ? "border-white/10 bg-black/70 text-white"
        : "border-white/60 bg-white/70 text-stone-900"
    }`}>
      <div className="mx-auto flex max-w-6xl flex-col gap-4">
        <div className="flex items-start justify-between gap-4">
          <Link href="/library" className="flex min-w-0 items-center gap-3">
            <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl text-sm font-semibold ${
              isDark ? "bg-white/10 text-amber-200" : "bg-stone-900 text-white"
            }`}>
              LV
            </div>
            <div className="min-w-0">
              <p className={`truncate font-serif text-xl tracking-tight ${isDark ? "text-white" : "text-stone-950"}`}>LoreVia</p>
              <p className={`text-xs ${isDark ? "text-gray-400" : "text-stone-500"}`}>Reading workspace</p>
            </div>
          </Link>

          <div className="flex shrink-0 items-center gap-2">
            <button
              onClick={() => setMobileMenuOpen((current) => !current)}
              className={`rounded-full px-3 py-2 text-sm transition-colors lg:hidden ${
                isDark ? "border border-white/10 text-gray-300 hover:bg-white/10 hover:text-white" : "border border-stone-200 text-stone-600 hover:bg-white hover:text-stone-950"
              }`}
              aria-label="Toggle navigation menu"
            >
              {mobileMenuOpen ? "Close" : "Menu"}
            </button>
            <button
              onClick={toggleTheme}
              className={`rounded-full px-3 py-2 text-sm transition-colors ${
                isDark ? "border border-white/10 text-gray-300 hover:bg-white/10 hover:text-white" : "border border-stone-200 text-stone-600 hover:bg-white hover:text-stone-950"
              }`}
            >
              {isDark ? "Light" : "Dark"}
            </button>
            {user && (
              <button
                onClick={handleLogout}
                className={`rounded-full px-3 py-2 text-sm transition-colors ${
                  isDark ? "text-gray-400 hover:bg-white/10 hover:text-white" : "text-stone-500 hover:bg-white hover:text-stone-900"
                }`}
              >
                Sign out
              </button>
            )}
          </div>
        </div>

        <div className={`${mobileMenuOpen ? "block" : "hidden"} lg:block`}>
          <div className={`rounded-3xl border p-3 lg:rounded-none lg:border-0 lg:bg-transparent lg:p-0 ${
            isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/80"
          }`}>
            <div className="grid gap-2 lg:flex lg:flex-wrap lg:items-center lg:justify-start">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileMenuOpen(false)}
                className={`shrink-0 rounded-full px-3 py-2 text-sm transition-colors ${
                  isDark ? "text-gray-300 hover:bg-white/10 hover:text-white" : "text-stone-600 hover:bg-white hover:text-stone-950"
                }`}
              >
                {item.label}
              </Link>
            ))}
            </div>
          </div>
        </div>
      </div>
    </nav>
  )
}
