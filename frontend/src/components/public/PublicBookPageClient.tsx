"use client"

import Link from "next/link"
import type { Route } from "next"
import { useQuery } from "@tanstack/react-query"
import React, { useEffect, useRef, useState } from "react"

import { publicApi } from "@/lib/api/public"
import { asQueryKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { PublicBookDetail } from "@/types/book"

const REPORT_OPTIONS = [
  { value: "copyright", label: "Copyright infringement" },
  { value: "plagiarism", label: "Plagiarism" },
  { value: "impersonation", label: "Impersonation" },
  { value: "spam", label: "Spam" },
  { value: "illegal_content", label: "Illegal content" },
  { value: "other", label: "Other" },
] as const

export function PublicBookPageClient({
  bookId,
  initialBook = null,
}: {
  bookId: string
  initialBook?: PublicBookDetail | null
}) {
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const [reportOpen, setReportOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [submittedMessage, setSubmittedMessage] = useState<string | null>(null)
  const [reportType, setReportType] = useState<(typeof REPORT_OPTIONS)[number]["value"]>("copyright")
  const [reason, setReason] = useState("")
  const [details, setDetails] = useState("")
  const [reporterName, setReporterName] = useState("")
  const [reporterEmail, setReporterEmail] = useState("")
  const [copyrightDescription, setCopyrightDescription] = useState("")
  const [copyrightUrl, setCopyrightUrl] = useState("")
  const [confirmed, setConfirmed] = useState(false)
  const trackedBookIdRef = useRef<string | null>(null)

  const { data: book = initialBook, isLoading: loading } = useQuery<PublicBookDetail | null>({
    queryKey: asQueryKey(`public:book:${bookId}`),
    queryFn: () => publicApi.getBook(bookId),
    staleTime: 60_000,
    initialData: initialBook ?? undefined,
  })

  async function submitReport() {
    if (!book) return
    setSubmitting(true)
    try {
      const response = await publicApi.createContentReport({
        bookId: book.id,
        reportType,
        reason,
        details,
        reporterEmail,
        copyrightOwnerName: reporterName,
        copyrightWorkDescription: copyrightDescription,
        copyrightOriginalUrl: copyrightUrl,
        reportedContentUrl: typeof window !== "undefined" ? window.location.href : undefined,
      })
      setSubmittedMessage(response.message ?? "Thank you. We will review this report.")
      setReportOpen(false)
    } finally {
      setSubmitting(false)
    }
  }

  const routeId = book?.public_slug || book?.id || bookId

  useEffect(() => {
    if (!book) return
    if (trackedBookIdRef.current === book.id) return
    trackedBookIdRef.current = book.id
    void publicApi.trackView(routeId, { eventType: "book_view" })
  }, [book, routeId])

  if (loading) {
    return <div className={`mx-auto max-w-5xl px-4 py-20 text-center ${isDark ? "text-slate-400" : "text-stone-500"}`}>Loading public book...</div>
  }

  if (!book) {
    return <div className={`mx-auto max-w-5xl px-4 py-20 text-center ${isDark ? "text-slate-400" : "text-stone-500"}`}>Public book not found.</div>
  }

  const isCopyrightReport = reportType === "copyright"
  const analytics = book.analytics

  return (
    <main className={`min-h-screen ${isDark ? "bg-black text-white" : "bg-stone-50 text-stone-950"}`}>
      <div className="mx-auto max-w-5xl px-4 py-10">
        <div className="flex flex-wrap items-center gap-3">
          <Link href="/library" className={`text-sm ${isDark ? "text-slate-400 hover:text-white" : "text-stone-500 hover:text-stone-900"}`}>
            {"<- Back to library"}
          </Link>
        </div>

        <div className="mt-8 max-w-3xl">
          <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-cyan-300" : "text-cyan-700"}`}>
            {book.content_source_type === "public_domain" ? "Public-domain demo" : "Public book"}
          </p>
          <h1 className="mt-4 text-4xl font-semibold tracking-tight">{book.title}</h1>
          {book.author_username ? (
            <Link href={`/public/writers/${book.author_username}` as Route} className={`mt-3 inline-flex text-lg font-semibold ${isDark ? "text-cyan-200 hover:text-white" : "text-cyan-700 hover:text-cyan-900"}`}>
              Published by @{book.author_username}
            </Link>
          ) : book.creator_display_name ? (
            <p className={`mt-3 text-lg ${isDark ? "text-slate-300" : "text-stone-600"}`}>Published by {book.creator_display_name}</p>
          ) : null}
          {book.description ? (
            <p className={`mt-5 text-base leading-8 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{book.description}</p>
          ) : null}
          {book.source_public_domain_note ? (
            <p className={`mt-5 rounded-2xl border px-4 py-3 text-sm leading-7 ${isDark ? "border-white/10 bg-white/[0.04] text-slate-300" : "border-stone-200 bg-white text-stone-600"}`}>
              {book.source_public_domain_note}
            </p>
          ) : null}
          {book.visibility_notice ? (
            <p className={`mt-5 rounded-2xl border px-4 py-3 text-sm leading-7 ${isDark ? "border-amber-400/20 bg-amber-500/10 text-amber-100" : "border-amber-200 bg-amber-50 text-amber-900"}`}>
              {book.visibility_notice}
            </p>
          ) : null}
          {submittedMessage ? (
            <p className={`mt-5 rounded-2xl border px-4 py-3 text-sm leading-7 ${isDark ? "border-emerald-400/20 bg-emerald-500/10 text-emerald-100" : "border-emerald-200 bg-emerald-50 text-emerald-900"}`}>
              {submittedMessage}
            </p>
          ) : null}
          <div className="mt-6 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => setReportOpen(true)}
              className={`rounded-full border px-4 py-2 text-sm font-semibold ${isDark ? "border-white/10 bg-white/[0.04] hover:bg-white/[0.08]" : "border-stone-200 bg-white hover:bg-stone-100"}`}
            >
              Report this book
            </button>
            <Link
              href="/copyright"
              className={`rounded-full border px-4 py-2 text-sm ${isDark ? "border-white/10 text-slate-300 hover:text-white" : "border-stone-200 text-stone-600 hover:text-stone-900"}`}
            >
              Copyright policy
            </Link>
          </div>
          {analytics ? (
            <div className={`mt-6 grid gap-3 sm:grid-cols-3 xl:grid-cols-4`}>
              <div className={`rounded-2xl border px-4 py-4 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white"}`}>
                <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Views</p>
                <p className="mt-2 text-2xl font-semibold">{analytics.book_view_count.toLocaleString()}</p>
              </div>
              <div className={`rounded-2xl border px-4 py-4 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white"}`}>
                <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Readers 30d</p>
                <p className="mt-2 text-2xl font-semibold">{analytics.unique_reader_count_30d.toLocaleString()}</p>
              </div>
              <div className={`rounded-2xl border px-4 py-4 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white"}`}>
                <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Chapter opens</p>
                <p className="mt-2 text-2xl font-semibold">{analytics.chapter_view_count.toLocaleString()}</p>
              </div>
              <div className={`rounded-2xl border px-4 py-4 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white"}`}>
                <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Published</p>
                <p className="mt-2 text-base font-semibold">{analytics.published_at ? new Date(analytics.published_at).toLocaleDateString() : "Not dated"}</p>
              </div>
            </div>
          ) : null}
        </div>

        {analytics ? (
          <section className="mt-10">
            <div className={`rounded-2xl border p-6 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white"}`}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 className="text-2xl font-semibold">Public book analytics</h2>
                <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Catalog and discussion metrics anyone can see</p>
              </div>
              <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
                <AnalyticsMetricCard isDark={isDark} label="Chapter count" value={String(analytics.chapter_count)} note="Visible public chapters." />
                <AnalyticsMetricCard isDark={isDark} label="Visible words" value={analytics.total_words.toLocaleString()} note="Estimated readable words." />
                <AnalyticsMetricCard isDark={isDark} label="Open discussions" value={String(analytics.open_discussion_count)} note={analytics.has_open_discussion ? "This book has an active public discussion." : "No active public discussion right now."} />
                <AnalyticsMetricCard isDark={isDark} label="Comments" value={analytics.discussion_comment_count.toLocaleString()} note="Public discussion comments tied to this book." />
                <AnalyticsMetricCard isDark={isDark} label="Reader interests" value={analytics.discussion_interest_count.toLocaleString()} note="Public collaboration interest messages." />
              </div>
            </div>
          </section>
        ) : null}

        <section className="mt-10">
          <div className={`rounded-2xl border p-6 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white"}`}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-2xl font-semibold">Chapters</h2>
              <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{book.total_chapters ?? book.chapters.length} available</p>
            </div>
            <div className="mt-6 grid gap-3">
              {book.chapters.map((chapter) => (
                <Link
                  key={chapter.number}
                  href={`/public/${routeId}/chapter/${chapter.number}` as Route}
                  className={`rounded-xl border px-4 py-4 transition ${isDark ? "border-white/10 bg-white/[0.03] hover:bg-white/[0.06]" : "border-stone-200 bg-stone-50 hover:bg-stone-100"}`}
                >
                  <p className="font-semibold">{chapter.title || `Chapter ${chapter.number}`}</p>
                  {chapter.description ? (
                    <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{chapter.description}</p>
                  ) : null}
                </Link>
              ))}
            </div>
          </div>
        </section>
      </div>

      {reportOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4 py-8">
          <div className={`w-full max-w-2xl rounded-3xl border p-6 ${isDark ? "border-white/10 bg-[#0f1116]" : "border-stone-200 bg-white"}`}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-cyan-300" : "text-cyan-700"}`}>Report</p>
                <h2 className="mt-2 text-2xl font-semibold">Report a copyright or policy issue</h2>
              </div>
              <button type="button" onClick={() => setReportOpen(false)} className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Close</button>
            </div>

            <div className="mt-6 grid gap-4">
              <label className="grid gap-2 text-sm">
                <span>Report reason</span>
                <select value={reportType} onChange={(event) => setReportType(event.target.value as typeof reportType)} className={`rounded-2xl border px-4 py-3 ${isDark ? "border-white/10 bg-black text-white" : "border-stone-200 bg-white text-stone-950"}`}>
                  {REPORT_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </label>

              <label className="grid gap-2 text-sm">
                <span>Reason</span>
                <textarea value={reason} onChange={(event) => setReason(event.target.value)} rows={3} className={`rounded-2xl border px-4 py-3 ${isDark ? "border-white/10 bg-black text-white" : "border-stone-200 bg-white text-stone-950"}`} />
              </label>

              <label className="grid gap-2 text-sm">
                <span>Details</span>
                <textarea value={details} onChange={(event) => setDetails(event.target.value)} rows={4} className={`rounded-2xl border px-4 py-3 ${isDark ? "border-white/10 bg-black text-white" : "border-stone-200 bg-white text-stone-950"}`} />
              </label>

              {isCopyrightReport ? (
                <>
                  <label className="grid gap-2 text-sm">
                    <span>Your name</span>
                    <input value={reporterName} onChange={(event) => setReporterName(event.target.value)} className={`rounded-2xl border px-4 py-3 ${isDark ? "border-white/10 bg-black text-white" : "border-stone-200 bg-white text-stone-950"}`} />
                  </label>
                  <label className="grid gap-2 text-sm">
                    <span>Your email</span>
                    <input value={reporterEmail} onChange={(event) => setReporterEmail(event.target.value)} className={`rounded-2xl border px-4 py-3 ${isDark ? "border-white/10 bg-black text-white" : "border-stone-200 bg-white text-stone-950"}`} />
                  </label>
                  <label className="grid gap-2 text-sm">
                    <span>Original work description</span>
                    <textarea value={copyrightDescription} onChange={(event) => setCopyrightDescription(event.target.value)} rows={3} className={`rounded-2xl border px-4 py-3 ${isDark ? "border-white/10 bg-black text-white" : "border-stone-200 bg-white text-stone-950"}`} />
                  </label>
                  <label className="grid gap-2 text-sm">
                    <span>Original work URL</span>
                    <input value={copyrightUrl} onChange={(event) => setCopyrightUrl(event.target.value)} className={`rounded-2xl border px-4 py-3 ${isDark ? "border-white/10 bg-black text-white" : "border-stone-200 bg-white text-stone-950"}`} />
                  </label>
                  <label className={`flex items-start gap-3 rounded-2xl border px-4 py-3 text-sm leading-6 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-stone-50"}`}>
                    <input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} className="mt-1" />
                    <span>I believe this report is accurate and I am the rights owner or authorized to act on behalf of the rights owner.</span>
                  </label>
                </>
              ) : null}
            </div>

            <div className="mt-6 flex flex-wrap justify-end gap-3">
              <button type="button" onClick={() => setReportOpen(false)} className={`rounded-full px-4 py-2 text-sm ${isDark ? "bg-white/[0.06] text-white" : "bg-stone-100 text-stone-900"}`}>Cancel</button>
              <button
                type="button"
                onClick={() => void submitReport()}
                disabled={submitting || !reason.trim() || (isCopyrightReport && (!reporterEmail.trim() || !confirmed))}
                className={`rounded-full px-5 py-2 text-sm font-semibold disabled:opacity-50 ${isDark ? "bg-white text-stone-950" : "bg-stone-950 text-white"}`}
              >
                {submitting ? "Sending..." : "Submit report"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  )
}

function AnalyticsMetricCard({ isDark, label, value, note }: { isDark: boolean; label: string; value: string; note: string }) {
  return (
    <article className={`rounded-2xl border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50"}`}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>{label}</p>
      <p className="mt-3 text-2xl font-semibold">{value}</p>
      <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{note}</p>
    </article>
  )
}
