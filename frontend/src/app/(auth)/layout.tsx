"use client"
import Link from "next/link"
import { ThemeBrandImage } from "@/components/layout/ThemeBrandImage"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const { theme, toggleTheme } = usePreferencesStore()
  const isDark = theme === "dark"

  return (
    <div
      className={`min-h-[100dvh] px-4 py-8 transition-colors ${
        isDark
          ? "bg-[#171b1d] text-slate-100"
          : "bg-[#f8f4ee] text-stone-950"
      }`}
    >
      <div className="mx-auto flex min-h-[calc(100dvh-4rem)] max-w-5xl flex-col gap-10">
        <header className="flex flex-wrap items-center justify-between gap-3 rounded-[1.25rem] border border-[rgba(var(--border),0.9)] bg-[rgba(255,252,247,0.82)] px-4 py-3 shadow-[0_18px_36px_-30px_rgba(58,49,37,0.18)] dark:bg-white/[0.04]">
          <Link href="/" className={`flex items-center gap-3 ${isDark ? "text-white" : "text-stone-900"}`}>
            <ThemeBrandImage variant="lockup" alt="LoreVia" className="h-11 w-auto object-contain sm:h-12" priority />
          </Link>
          <div className="flex items-center gap-2">
            <button
              onClick={toggleTheme}
              className={`rounded-full border px-4 py-2 text-sm font-medium transition ${
                isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-[rgba(var(--border),0.9)] bg-white/90 text-stone-700 hover:bg-white"
              }`}
            >
              {isDark ? "Light mode" : "Dark mode"}
            </button>
            <Link
              href="/"
              className={`rounded-full border px-4 py-2 text-sm font-medium transition ${
                isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-[rgba(var(--border),0.9)] bg-white/90 text-stone-700 hover:bg-white"
              }`}
            >
              Back to home
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
