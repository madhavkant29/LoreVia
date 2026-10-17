"use client"

import { ThemeBrandImage } from "@/components/layout/ThemeBrandImage"

export default function OfflinePage() {
  return (
    <main className="grid min-h-[100dvh] place-items-center bg-[#f8f4ee] px-6 text-stone-950">
      <section className="w-full max-w-lg border-y border-stone-300 py-8">
        <ThemeBrandImage variant="icon" mode="light" alt="LoreVia" className="h-10 w-10 object-contain" priority />
        <p className="mt-8 text-sm font-semibold text-teal-800">Connection unavailable</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-[-0.03em]">You are offline.</h1>
        <p className="mt-4 text-sm leading-7 text-stone-600">
          Drafts already open on this device continue saving locally. LoreVia will replay queued chapter edits when your connection returns and will pause for review if another session changed the same chapter.
        </p>
        <button type="button" onClick={() => window.location.reload()} className="mt-7 rounded-md bg-stone-950 px-5 py-3 text-sm font-semibold text-white hover:bg-stone-800">
          Try again
        </button>
      </section>
    </main>
  )
}
