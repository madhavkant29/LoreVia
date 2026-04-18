"use client"

import Link from "next/link"

import { usePreferencesStore } from "@/lib/stores/preferencesStore"

export default function PublicStudioPage() {
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <section
        className={`rounded-[2rem] border p-8 shadow-[0_24px_80px_-48px_rgba(15,23,42,0.35)] ${
          isDark
            ? "border-white/10 bg-[linear-gradient(145deg,rgba(15,23,42,0.96),rgba(30,41,59,0.88),rgba(37,99,235,0.18))] text-slate-100"
            : "border-stone-200 bg-[linear-gradient(145deg,#fffaf0,#fffdf8,#f6efe1)] text-stone-900"
        }`}
      >
        <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-sky-200" : "text-stone-500"}`}>
          Hidden for now
        </p>
        <h1 className={`mt-4 font-serif text-4xl ${isDark ? "text-white" : "text-stone-950"}`}>
          Public publishing is temporarily off the UI.
        </h1>
        <p className={`mt-4 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
          The backend support is still preserved, but the authoring and public-upload surface is intentionally hidden until moderation,
          discovery, and the full publishing workflow are ready to ship together.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/library"
            className={`rounded-full px-5 py-3 text-sm font-semibold transition ${
              isDark ? "bg-white text-slate-950 hover:bg-slate-200" : "bg-stone-900 text-white hover:bg-stone-800"
            }`}
          >
            Back to library
          </Link>
          <Link
            href="/series"
            className={`rounded-full px-5 py-3 text-sm font-semibold transition ${
              isDark ? "border border-white/15 text-slate-200 hover:bg-white/10" : "border border-stone-300 text-stone-700 hover:bg-white"
            }`}
          >
            Manage series instead
          </Link>
        </div>
      </section>
    </div>
  )
}
