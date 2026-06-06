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

  return (
    <div
      className={`min-h-screen transition-colors ${
        isDark
          ? "bg-black text-[#E0E0E0]"
          : "bg-stone-50 text-stone-950"
      }`}
    >
      <div className="mx-auto w-full px-3 pb-16 pt-6 sm:px-6 lg:px-8 xl:max-w-7xl">
        <section
          className={`overflow-hidden rounded-lg border ${
            isDark
              ? "border-white/10 bg-[#0D0D0D]"
              : "border-stone-200 bg-white"
          }`}
        >
          <div className="flex flex-col gap-6 px-6 py-7 sm:px-8 lg:flex-row lg:items-end lg:justify-between lg:px-10 lg:py-10">
            <div className="max-w-3xl">
              <p className={`text-3xs font-semibold uppercase tracking-[0.34em] ${isDark ? "text-[#A0A0A0]" : "text-indigo-600"}`}>Author Workflow</p>
              <h1 className={`mt-3 font-serif text-4xl tracking-tight sm:text-5xl ${isDark ? "text-[#E0E0E0]" : "text-stone-950"}`}>Add New Chapter</h1>
              <p className={`mt-4 max-w-2xl text-base leading-7 ${isDark ? "text-[#A0A0A0]" : "text-stone-600"}`}>
                Drop into LoreVia&apos;s incremental ingest flow, update character memory and plot threads, then review fresh continuity flags before you move on.
              </p>
              <p className={`mt-3 max-w-2xl text-sm leading-6 ${isDark ? "text-[#8C8C8C]" : "text-stone-500"}`}>
                Standalone scenes live in the manuscript workspace so they stay separate from chapter imports and can be linked later only if you want.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Link
                href="/library"
                className={`inline-flex items-center justify-center rounded-md px-5 py-3 text-sm font-semibold transition ${
                  isDark
                    ? "border border-white/12 bg-[#111111] text-[#E0E0E0] hover:bg-[#171717]"
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
                    ? "border border-white/12 bg-white/5 text-[#E0E0E0] hover:bg-white/10"
                    : "border border-stone-200 bg-stone-50 text-stone-800 hover:bg-stone-100"
                }`}
              >
                Reset Flow
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
                  Open Scene Workspace
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
