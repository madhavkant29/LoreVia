"use client"
import Link from "next/link"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const { theme, toggleTheme } = usePreferencesStore()
  const isDark = theme === "dark"

  return (
    <div
      className={`min-h-[100dvh] px-4 py-8 transition-colors ${
        isDark
          ? "bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.08),transparent_22%),radial-gradient(circle_at_88%_10%,rgba(255,255,255,0.05),transparent_26%),linear-gradient(180deg,#000000_0%,#050505_52%,#0b0b0b_100%)] text-slate-100"
          : "bg-[radial-gradient(circle_at_top_left,#efe3c8,transparent_22%),radial-gradient(circle_at_88%_10%,#dde9fb,transparent_26%),linear-gradient(180deg,#f7f3ec_0%,#f7f7f5_52%,#eef2f8_100%)] text-stone-950"
      }`}
    >
      <div className="mx-auto flex min-h-[calc(100dvh-4rem)] max-w-5xl flex-col gap-10">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <Link href="/" className={`flex items-center gap-3 ${isDark ? "text-white" : "text-stone-900"}`}>
            <img
              src="/logoandtext.png"
              alt="LoreVia"
              className="h-11 w-auto object-contain sm:h-12"
            />
          </Link>
          <div className="flex items-center gap-2">
            <button
              onClick={toggleTheme}
              className={`rounded-full border px-4 py-2 text-sm font-medium transition ${
                isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-300 bg-white/80 text-stone-700 hover:bg-white"
              }`}
            >
              {isDark ? "Light mode" : "Dark mode"}
            </button>
            <Link
              href="/"
              className={`rounded-full border px-4 py-2 text-sm font-medium transition ${
                isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-300 bg-white/80 text-stone-700 hover:bg-white"
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
