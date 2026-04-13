"use client"

import Link from "next/link"
import { SUPPORT_EMAIL } from "@/lib/constants/contact"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

export default function PublicLibraryPage() {
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <section className={`rounded-[2rem] border p-8 shadow-[0_24px_80px_-48px_rgba(15,23,42,0.32)] ${isDark ? "border-white/10 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-950"}`}>
        <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-amber-200" : "text-amber-700"}`}>Public mode</p>
        <h1 className="mt-3 font-serif text-4xl">Paused while we redesign it properly.</h1>
        <p className={`mt-4 max-w-3xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
          Public reading is temporarily disabled while we redesign unlocks, community, comments, moderation, and trust systems together instead of shipping a half-open mode. The next version is planned around points, chapter unlocks, discussion, and stronger public UX.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link href="/library" className={`rounded-full px-5 py-3 text-sm font-semibold transition ${isDark ? "bg-amber-300 text-slate-950 hover:bg-amber-200" : "bg-slate-950 text-white hover:bg-slate-800"}`}>
            Back to library
          </Link>
          <a href={`mailto:${SUPPORT_EMAIL}`} className={`rounded-full px-5 py-3 text-sm font-semibold transition ${isDark ? "border border-white/10 text-white hover:bg-white/10" : "border border-slate-300 text-slate-800 hover:bg-slate-50"}`}>
            Request early access
          </a>
        </div>
      </section>
    </div>
  )
}
