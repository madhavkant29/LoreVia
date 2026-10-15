"use client"

import { Suspense } from "react"
import dynamic from "next/dynamic"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"

import { usePreferencesStore } from "@/lib/stores/preferencesStore"

const UploadModal = dynamic(
  () => import("@/components/modals/UploadModal").then((module) => module.UploadModal),
  {
    ssr: false,
    loading: () => <div className="rounded-lg border p-8" />,
  }
)

export default function AddChapterPage() {
  return (
    <Suspense fallback={null}>
      <AddChapterPageInner />
    </Suspense>
  )
}

function AddChapterPageInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const initialBookId = searchParams.get("book") ?? ""
  const initialBookTitle = searchParams.get("title")?.trim() || "selected project"

  if (!initialBookId) {
    return (
      <main className={`min-h-[70vh] ${isDark ? "text-[#E0E0E0]" : "text-stone-950"}`}>
        <div className="mx-auto max-w-2xl py-16">
          <p className="app-eyebrow">Library</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-[-0.03em]">Choose a project first</h1>
          <p className={`mt-4 text-sm leading-7 ${isDark ? "text-[#A0A0A0]" : "text-stone-600"}`}>
            Chapters are added inside an existing project so LoreVia can preserve chapter order, characters, and continuity context.
          </p>
          <Link href="/library" className="app-button-primary mt-6">Return to Library</Link>
        </div>
      </main>
    )
  }

  return (
    <div
      className={`min-h-screen transition-colors ${
        isDark
          ? "bg-black text-[#E0E0E0]"
          : "bg-stone-50 text-stone-950"
      }`}
    >
      <div className="mx-auto w-full px-3 pb-16 pt-6 sm:px-6 lg:px-8 xl:max-w-7xl">
        <section className={`border-b pb-7 ${isDark ? "border-white/10" : "border-stone-300"}`}>
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="app-eyebrow">{initialBookTitle}</p>
              <h1 className={`mt-3 text-3xl font-semibold tracking-[-0.03em] sm:text-4xl ${isDark ? "text-[#E0E0E0]" : "text-stone-950"}`}>Add a chapter</h1>
              <p className={`mt-4 max-w-2xl text-base leading-7 ${isDark ? "text-[#A0A0A0]" : "text-stone-600"}`}>
                Import the next chapter into this project. Existing chapters remain in place, and analysis updates after processing.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Link
                href="/library"
                className={`inline-flex items-center justify-center rounded-md px-5 py-3 text-sm font-semibold transition ${
                  isDark
                    ? "border border-white/[0.12] bg-[#111111] text-[#E0E0E0] hover:bg-[#171717]"
                    : "border border-stone-200 bg-white text-stone-800 hover:bg-stone-50"
                }`}
              >
                Back to Library
              </Link>
              <button
                type="button"
                onClick={() => {
                  window.location.href = initialBookId ? `/library/add-chapter?book=${initialBookId}` : "/library/add-chapter"
                }}
                className={`inline-flex items-center justify-center rounded-md px-5 py-3 text-sm font-semibold transition ${
                  isDark
                    ? "border border-white/[0.12] bg-white/5 text-[#E0E0E0] hover:bg-white/10"
                    : "border border-stone-200 bg-stone-50 text-stone-800 hover:bg-stone-100"
                }`}
              >
                Clear form
              </button>
              {initialBookId ? (
                <Link
                  href={`/${initialBookId}/manuscript`}
                  className={`inline-flex items-center justify-center rounded-md px-5 py-3 text-sm font-semibold transition ${
                    isDark
                      ? "border border-emerald-400/20 bg-emerald-500/10 text-emerald-100 hover:bg-emerald-500/15"
                      : "border border-emerald-200 bg-emerald-50 text-emerald-800 hover:bg-emerald-100"
                  }`}
                >
                  Open manuscript
                </Link>
              ) : null}
            </div>
          </div>
        </section>
      </div>

      <div className="mx-auto w-full px-3 pb-16 sm:px-6 lg:px-8 xl:max-w-7xl">
        <UploadModal
          presentation="inline"
          initialMode="author"
          initialExistingBookId={initialBookId}
          onClose={() => router.push("/library")}
        />
      </div>
    </div>
  )
}
