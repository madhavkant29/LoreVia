"use client"
import Link from "next/link"
import { ThemeBrandImage } from "@/components/layout/ThemeBrandImage"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const { theme, toggleTheme } = usePreferencesStore()
  const isDark = theme === "dark"

  return (
    <div
      className={`auth-shell min-h-[100dvh] px-4 py-8 transition-colors ${
        isDark
          ? "bg-[#171b1d] text-slate-100"
          : "bg-[#f8f4ee] text-stone-950"
      }`}
    >
      <div className="mx-auto flex min-h-[calc(100dvh-4rem)] max-w-5xl flex-col gap-10">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[rgba(var(--border),0.9)] pb-4">
          <Link href="/" className={`flex items-center gap-3 ${isDark ? "text-white" : "text-stone-900"}`}>
            <ThemeBrandImage variant="icon" alt="LoreVia" className="h-9 w-9 object-contain" priority />
          </Link>
          <div className="flex items-center gap-4 text-sm font-medium">
            <button
              onClick={toggleTheme}
              className={isDark ? "text-slate-300 hover:text-white" : "text-stone-600 hover:text-stone-950"}
            >
              {isDark ? "Light mode" : "Dark mode"}
            </button>
            <Link
              href="/"
              className={isDark ? "text-slate-300 hover:text-white" : "text-stone-600 hover:text-stone-950"}
            >
              Home
            </Link>
          </div>
        </header>

        <div className="flex flex-1 items-center justify-center">
          <div className="w-full max-w-md">{children}</div>
        </div>
      </div>
    </div>
  )
}
