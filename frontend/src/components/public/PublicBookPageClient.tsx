"use client"

import Link from "next/link"
import type { Route } from "next"

import { Dialog } from "@/components/ui/Dialog"
import { VisibilityBadge } from "@/components/ui/VisibilityBadge"
import { useQuery } from "@tanstack/react-query"
import React, { useEffect, useRef, useState } from "react"

import { publicApi } from "@/lib/api/public"
import { asQueryKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { resolveAssetUrl } from "@/lib/utils/assetUrls"
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
  const coverUrl = resolveAssetUrl(book.cover_url)
  const publicMetrics = analytics ? [
    { label: "Views", value: analytics.book_view_count.toLocaleString(), note: "All public book opens." },
    { label: "Readers, 30 days", value: analytics.unique_reader_count_30d.toLocaleString(), note: "Recent unique readers." },
    { label: "Chapter opens", value: analytics.chapter_view_count.toLocaleString(), note: "Public chapter reads." },
    { label: "Visible words", value: analytics.total_words.toLocaleString(), note: "Estimated readable words." },
    { label: "Open discussions", value: String(analytics.open_discussion_count), note: analytics.has_open_discussion ? "This book has an active public discussion." : "No active public discussion right now." },
    { label: "Comments", value: analytics.discussion_comment_count.toLocaleString(), note: "Discussion comments." },
    { label: "Reader interests", value: analytics.discussion_interest_count.toLocaleString(), note: "Collaboration notes." },
    { label: "Published", value: analytics.published_at ? new Date(analytics.published_at).toLocaleDateString() : "Not dated", note: `${analytics.chapter_count} visible chapters.` },
  ] : []

  return (
    <main className={`min-h-screen ${isDark ? "bg-[#0a0f14] text-white" : "bg-[#f4f5f2] text-stone-950"}`}>
      <div className="mx-auto max-w-5xl px-4 py-10">
        <div className="flex flex-wrap items-center gap-3">
          <Link href="/public" className={`text-sm ${isDark ? "text-slate-400 hover:text-white" : "text-stone-500 hover:text-stone-900"}`}>
            {"<- Back to public library"}
          </Link>
        </div>

        <section data-testid="public-book-masthead" className="mt-8 grid gap-8 border-b pb-10 sm:grid-cols-[11rem_minmax(0,1fr)] sm:items-start">
          <div className={`aspect-[2/3] w-40 overflow-hidden border sm:w-full ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-stone-100"}`}>
            {coverUrl ? (
              <img src={coverUrl} alt={`Cover of ${book.title}`} className="h-full w-full object-cover" />
            ) : (
              <div className={`flex h-full items-center justify-center px-4 text-center text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>Cover not provided</div>
            )}
          </div>
          <div className="max-w-3xl">
            <div className="flex flex-wrap items-center gap-3">
              <VisibilityBadge state="public_sample" />
              <p className={`text-sm font-medium ${isDark ? "text-teal-300" : "text-teal-700"}`}>
                {book.content_source_type === "public_domain" ? "Public-domain edition" : "Creator-published original"}
              </p>
            </div>
            <h1 className="mt-4 font-display text-4xl font-semibold tracking-[-0.035em] sm:text-5xl">{book.title}</h1>
            {book.author_username ? (
              <Link href={`/public/writers/${book.author_username}` as Route} className={`mt-3 inline-flex text-lg font-semibold ${isDark ? "text-teal-200 hover:text-white" : "text-teal-700 hover:text-teal-900"}`}>
                Published by @{book.author_username}
              </Link>
            ) : book.creator_display_name ? (
              <p className={`mt-3 text-lg ${isDark ? "text-slate-300" : "text-stone-600"}`}>by {book.creator_display_name}</p>
            ) : book.author ? (
              <p className={`mt-3 text-lg ${isDark ? "text-slate-300" : "text-stone-600"}`}>by {book.author}</p>
            ) : null}
            {book.description ? (
              <p className={`mt-5 text-base leading-8 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{book.description}</p>
            ) : null}
            <div className="mt-7 flex flex-wrap items-center gap-4 text-sm font-semibold">
              {book.chapters[0] ? (
                <Link href={`/public/${routeId}/chapter/${book.chapters[0].number}` as Route} className={`rounded-md px-5 py-2.5 ${isDark ? "bg-teal-300 text-slate-950 hover:bg-teal-200" : "bg-[#1f615d] text-white hover:bg-[#174c49]"}`}>Start reading</Link>
              ) : null}
              {book.active_forum_post_id ? (
                <Link href={`/public/forum/${book.active_forum_post_id}` as Route} className={isDark ? "text-teal-200 hover:text-white" : "text-teal-700 hover:text-teal-900"}>Open discussion</Link>
              ) : null}
            </div>
            {book.source_public_domain_note ? (
              <p className={`mt-6 border-l-2 pl-4 text-sm leading-7 ${isDark ? "border-teal-300/50 text-slate-300" : "border-teal-700/40 text-stone-600"}`}>{book.source_public_domain_note}</p>
            ) : null}
            {book.visibility_notice ? (
              <p className={`mt-4 border-l-2 pl-4 text-sm leading-7 ${isDark ? "border-amber-300/50 text-amber-100" : "border-amber-600/40 text-amber-900"}`}>{book.visibility_notice}</p>
            ) : null}
            {submittedMessage ? (
              <p className={`mt-4 border-l-2 pl-4 text-sm leading-7 ${isDark ? "border-emerald-300/50 text-emerald-100" : "border-emerald-600/40 text-emerald-900"}`}>{submittedMessage}</p>
            ) : null}
          </div>
        </section>

        <section className="mt-10" aria-labelledby="public-book-chapters">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <h2 id="public-book-chapters" className="text-2xl font-semibold">Chapters</h2>
            <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{book.total_chapters ?? book.chapters.length} available</p>
          </div>
          <div className={`mt-5 border-y ${isDark ? "border-white/10" : "border-stone-200"}`}>
            {book.chapters.map((chapter) => (
              <Link
                key={chapter.number}
                href={`/public/${routeId}/chapter/${chapter.number}` as Route}
                className={`grid gap-2 border-b py-4 last:border-b-0 sm:grid-cols-[4rem_minmax(0,1fr)_auto] sm:items-center ${isDark ? "border-white/10 hover:bg-white/[0.025]" : "border-stone-200 hover:bg-white/60"}`}
              >
                <span className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>{chapter.number}</span>
                <span>
                  <span className="font-semibold">{chapter.title || `Chapter ${chapter.number}`}</span>
                  {chapter.description ? <span className={`mt-1 block text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{chapter.description}</span> : null}
                </span>
                <span className={`text-sm font-semibold ${isDark ? "text-teal-200" : "text-teal-700"}`}>Read →</span>
              </Link>
            ))}
          </div>
        </section>

        {analytics ? (
          <details data-testid="public-book-activity" className={`mt-10 border-y ${isDark ? "border-white/10" : "border-stone-200"}`}>
            <summary className="cursor-pointer py-4 text-sm font-semibold">Public activity and publication details</summary>
            <div className={`grid border-t sm:grid-cols-2 lg:grid-cols-4 ${isDark ? "border-white/10" : "border-stone-200"}`}>
              {publicMetrics.map((metric) => (
                <div key={metric.label} className={`border-b py-5 sm:px-5 sm:odd:border-r lg:border-r lg:[&:nth-child(4n)]:border-r-0 ${isDark ? "border-white/10" : "border-stone-200"}`}>
                  <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{metric.label}</p>
                  <p className="mt-2 text-2xl font-semibold">{metric.value}</p>
                  <p className={`mt-2 text-xs leading-5 ${isDark ? "text-slate-500" : "text-stone-500"}`}>{metric.note}</p>
                </div>
              ))}
            </div>
          </details>
        ) : null}

        <div className={`mt-8 flex flex-wrap gap-4 border-t pt-5 text-sm ${isDark ? "border-white/10 text-slate-400" : "border-stone-200 text-stone-600"}`}>
          <button type="button" onClick={() => setReportOpen(true)} className="font-semibold hover:text-[rgb(var(--foreground))]">Report this book</button>
          <Link href="/copyright" className="hover:text-[rgb(var(--foreground))]">Copyright policy</Link>
        </div>
      </div>

      {reportOpen ? (
        <Dialog
          open
          onClose={() => setReportOpen(false)}
          eyebrow="Report"
          title="Report a copyright or policy issue"
          size="lg"
          closeOnOutside={!submitting}
        >
            <div className="mt-6 grid gap-4">
              <label className="grid gap-2 text-sm">
                <span>Report reason</span>
                <select value={reportType} onChange={(event) => setReportType(event.target.value as typeof reportType)} className={`rounded-md border px-4 py-3 ${isDark ? "border-white/10 bg-black text-white" : "border-stone-200 bg-white text-stone-950"}`}>
                  {REPORT_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </label>

              <label className="grid gap-2 text-sm">
                <span>Reason</span>
                <textarea value={reason} onChange={(event) => setReason(event.target.value)} rows={3} className={`rounded-md border px-4 py-3 ${isDark ? "border-white/10 bg-black text-white" : "border-stone-200 bg-white text-stone-950"}`} />
              </label>

              <label className="grid gap-2 text-sm">
                <span>Details</span>
                <textarea value={details} onChange={(event) => setDetails(event.target.value)} rows={4} className={`rounded-md border px-4 py-3 ${isDark ? "border-white/10 bg-black text-white" : "border-stone-200 bg-white text-stone-950"}`} />
              </label>

              {isCopyrightReport ? (
                <>
                  <label className="grid gap-2 text-sm">
                    <span>Your name</span>
                    <input value={reporterName} onChange={(event) => setReporterName(event.target.value)} className={`rounded-md border px-4 py-3 ${isDark ? "border-white/10 bg-black text-white" : "border-stone-200 bg-white text-stone-950"}`} />
                  </label>
                  <label className="grid gap-2 text-sm">
                    <span>Your email</span>
                    <input value={reporterEmail} onChange={(event) => setReporterEmail(event.target.value)} className={`rounded-md border px-4 py-3 ${isDark ? "border-white/10 bg-black text-white" : "border-stone-200 bg-white text-stone-950"}`} />
                  </label>
                  <label className="grid gap-2 text-sm">
                    <span>Original work description</span>
                    <textarea value={copyrightDescription} onChange={(event) => setCopyrightDescription(event.target.value)} rows={3} className={`rounded-md border px-4 py-3 ${isDark ? "border-white/10 bg-black text-white" : "border-stone-200 bg-white text-stone-950"}`} />
                  </label>
                  <label className="grid gap-2 text-sm">
                    <span>Original work URL</span>
                    <input value={copyrightUrl} onChange={(event) => setCopyrightUrl(event.target.value)} className={`rounded-md border px-4 py-3 ${isDark ? "border-white/10 bg-black text-white" : "border-stone-200 bg-white text-stone-950"}`} />
                  </label>
                  <label className={`flex items-start gap-3 rounded-md border px-4 py-3 text-sm leading-6 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-stone-50"}`}>
                    <input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} className="mt-1" />
                    <span>I believe this report is accurate and I am the rights owner or authorized to act on behalf of the rights owner.</span>
                  </label>
                </>
              ) : null}
            </div>

            <div className="mt-6 flex flex-wrap justify-end gap-3">
              <button type="button" onClick={() => setReportOpen(false)} className={`rounded-md px-4 py-2 text-sm ${isDark ? "bg-white/[0.06] text-white" : "bg-stone-100 text-stone-900"}`}>Cancel</button>
              <button
                type="button"
                onClick={() => void submitReport()}
                disabled={submitting || !reason.trim() || (isCopyrightReport && (!reporterEmail.trim() || !confirmed))}
                className={`rounded-md px-5 py-2 text-sm font-semibold disabled:opacity-50 ${isDark ? "bg-white text-stone-950" : "bg-stone-950 text-white"}`}
              >
                {submitting ? "Sending..." : "Submit report"}
              </button>
            </div>
        </Dialog>
      ) : null}
    </main>
  )
}
