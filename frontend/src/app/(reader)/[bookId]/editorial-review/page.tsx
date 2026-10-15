"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import dynamic from "next/dynamic"
import Link from "next/link"
import type { Route } from "next"
import { useParams } from "next/navigation"

import { booksApi } from "@/lib/api/books"
import { intelligenceApi, MAX_ADVISOR_PASSAGE_CHARS } from "@/lib/api/intelligence"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { saveContextualVaultNote } from "@/lib/utils/notes"
import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { WorkspacePage } from "@/components/ui/Workspace"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"
import { Skeleton } from "@/components/ui/Skeleton"
import type { Book } from "@/types/book"
import type { EditorialReview, EditorialReviewPassage } from "@/types/intelligence"

type ReviewRun = {
  id: string
  label: string
  chapterNumber: number | null
  text: string
  result: EditorialReview
  passages: EditorialReviewPassage[]
}

const EditorialReviewResults = dynamic(
  () => import("@/components/reader/EditorialReviewResults").then((module) => module.EditorialReviewResults),
  {
    ssr: false,
    loading: () => (
      <div className="border-y border-white/10 py-5" role="status" aria-label="Loading editorial review results" aria-busy="true">
        <span className="sr-only">Loading editorial review results</span>
        <Skeleton className="h-3 w-28 bg-white/10" />
        <Skeleton className="mt-4 h-4 w-3/4 bg-white/10" />
        <Skeleton className="mt-2 h-4 w-1/2 bg-white/10" />
      </div>
    ),
  }
)

export default function EditorialReviewPage() {
  const { bookId } = useParams<{ bookId: string }>()
  return <EditorialReviewWorkspace key={bookId} bookId={bookId} />
}

function EditorialReviewWorkspace({ bookId }: { bookId: string }) {
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const bookQuery = useQuery<Book | null>({
    queryKey: asQueryKey(bookCacheKey(bookId, "detail")),
    queryFn: () => booksApi.get(bookId),
  })

  const book = bookQuery.data
  const request = useRef<AbortController | null>(null)
  useEffect(() => () => request.current?.abort(), [])

  const [editText, setEditText] = useState("")
  const [editChapter, setEditChapter] = useState("")
  const [editLoading, setEditLoading] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)
  const [editProgress, setEditProgress] = useState<string | null>(null)
  const [runs, setRuns] = useState<ReviewRun[]>([])
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)

  const chapterNumber = editChapter ? Number(editChapter) : null
  const chapterValid = chapterNumber === null || (Number.isSafeInteger(chapterNumber) && chapterNumber > 0)
  const passageTooLong = editText.trim().length > MAX_ADVISOR_PASSAGE_CHARS
  const canReview = Boolean(editText.trim()) && chapterValid && !passageTooLong && !editLoading
  const selectedRun = runs.find((run) => run.id === selectedRunId)
  const sourceChanged = selectedRun && (editText.trim() !== selectedRun.text || chapterNumber !== selectedRun.chapterNumber)

  const saveNote = useCallback(async (title: string, body: string, targetChapterNumber: number | null) => {
    await saveContextualVaultNote({
      bookId,
      title,
      content: body,
      context: "story_advisor",
      folderSegments: targetChapterNumber ? ["Editorial Review", `Chapter ${targetChapterNumber}`] : ["Editorial Review"],
    })
  }, [bookId])

  const runEditorialReview = async () => {
    const sourceText = editText.trim()
    if (!canReview || request.current) return
    const controller = new AbortController()
    request.current = controller
    setEditLoading(true)
    setEditError(null)
    setEditProgress(null)
    try {
      const result = await intelligenceApi.editorialReviewStream(
        bookId,
        sourceText,
        chapterNumber ?? undefined,
        { onStage: setEditProgress, signal: controller.signal },
      )
      if (controller.signal.aborted) return
      const runNumber = runs.length + 1
      const run: ReviewRun = {
        id: `${runNumber}-${Date.now()}`,
        label: chapterNumber ? `Chapter ${chapterNumber}` : `Passage ${runNumber}`,
        chapterNumber,
        text: sourceText,
        result: result.review,
        passages: result.retrieved_passages,
      }
      setRuns((current) => [run, ...current])
      setSelectedRunId(run.id)
    } catch (error) {
      if (controller.signal.aborted) return
      const message = error instanceof Error ? error.message : ""
      setEditError(message.startsWith("429:")
        ? "Review limit reached. Try again later or check your plan's review allowance. Your passage is still here."
        : message.startsWith("403:")
          ? "Review access is unavailable for this account or manuscript. Check your plan and manuscript access. Your passage is still here."
          : "Review failed. Check your connection and try again.")
    } finally {
      request.current = null
      setEditLoading(false)
      setEditProgress(null)
    }
  }

  const selectRun = (run: ReviewRun) => {
    setSelectedRunId(run.id)
    setEditError(null)
  }

  return (
    <WorkspacePage>
      <main data-editorial-workspace className="min-w-0 pb-12 pt-6">
        <WorkspaceFamilyHeader
          active="editorial-review"
          bookId={bookId}
          family="review-center"
          title="Editorial review"
          description={`Review a passage from ${book?.title || "this manuscript"} beside continuity, grammar, thematic, and source evidence.`}
          actions={(
            <>
            <Link href={`/${bookId}/manuscript` as Route} className="app-button-secondary">
              Open manuscript
            </Link>
            <button type="button" className="app-button-secondary" onClick={() => window.dispatchEvent(new CustomEvent(SUPPORT_HELP_EVENT))}>Help</button>
            </>
          )}
        />

        {bookQuery.isError ? <div role="alert" className="mt-4 border-l-2 border-amber-500 pl-3 text-sm">Manuscript details could not load. <button type="button" className="app-button-secondary" onClick={() => void bookQuery.refetch()}>Retry manuscript details</button></div> : null}

        <div className="mt-6 grid gap-8 xl:grid-cols-[minmax(0,0.95fr)_minmax(30rem,1.05fr)] xl:items-start">
          <section aria-label="Passage" className="min-w-0">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <h2 className="text-xl font-semibold">Passage</h2>
                <p className={`mt-1 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>
                  Paste only the material you want reviewed. Import and chapter replacement stay in the manuscript workspace.
                </p>
              </div>
              <label className={`block text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>
                Chapter number (optional)
                <input
                  type="number"
                  min={1}
                  step={1}
                  disabled={editLoading}
                  aria-invalid={!chapterValid}
                  aria-describedby={!chapterValid ? "chapter-error" : undefined}
                  value={editChapter}
                  onChange={(event) => setEditChapter(event.target.value)}
                  className={`mt-1 block w-36 rounded-sm border px-3 py-2 text-sm outline-none ${isDark ? "border-white/10 bg-[#08101a] text-slate-100 focus:border-teal-400/60" : "border-stone-200 bg-white text-stone-900 focus:border-teal-700"}`}
                />
              </label>
            </div>

            {!chapterValid ? <p id="chapter-error" role="alert" className="mt-3 text-sm text-red-600 dark:text-red-300">Enter a whole chapter number of 1 or higher, or leave it blank.</p> : null}
            <div className={`mt-4 overflow-hidden border-y ${isDark ? "border-white/10" : "border-stone-200"}`}>
              <textarea
                aria-label="Passage text"
                value={editText}
                onChange={(event) => setEditText(event.target.value)}
                rows={14}
                disabled={editLoading}
                aria-describedby="passage-limit"
                aria-invalid={passageTooLong}
                placeholder="Paste a paragraph, scene, or chapter section…"
                className={`block h-72 min-h-48 xl:h-[28rem] w-full resize-y border-0 bg-transparent px-1 py-4 text-sm leading-7 outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-teal-500 ${isDark ? "text-slate-100 placeholder:text-slate-400" : "text-stone-900 placeholder:text-stone-600"}`}
              />
              <div className={`flex flex-col gap-3 border-t py-3 sm:flex-row sm:items-center sm:justify-between ${isDark ? "border-white/10" : "border-stone-200"}`}>
                <span id="passage-limit" className="text-sm text-[rgb(var(--muted-foreground))]">{editText.trim().length.toLocaleString()} / 12,000 characters{passageTooLong ? ". Shorten the passage before reviewing; no text will be cut automatically." : ""}</span>
                <button
                  type="button"
                  onClick={() => void runEditorialReview()}
                  disabled={!canReview}
                  className={`inline-flex min-h-10 items-center justify-center rounded-sm px-5 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-45 ${isDark ? "bg-teal-300 text-slate-950 hover:bg-teal-200" : "bg-[#1f615d] text-white hover:bg-[#174c49]"}`}
                >
                  {editLoading ? "Reviewing…" : "Run review"}
                </button>
              </div>
            </div>

            {editError ? <StatusLine isDark={isDark} message={editError} tone="error" /> : null}
            {editLoading ? <StatusLine isDark={isDark} message={editProgress || "Reviewing the passage against manuscript evidence…"} tone="info" /> : null}
            {selectedRun ? <a href="#editorial-findings" className="mt-4 inline-block app-link">View selected review</a> : null}
          </section>

          <aside className={`min-w-0 xl:border-l xl:pl-8 ${isDark ? "xl:border-white/10" : "xl:border-stone-200"}`} aria-label="Editorial review findings">
            <section aria-label="Runs this session">
              <div className="flex items-baseline justify-between gap-3">
                <h2 className="text-sm font-semibold">Runs this session</h2>
                <span className={`text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>{runs.length}</span>
              </div>
              <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">Reviews stay here until you leave or refresh. Save useful findings to Notes.</p>
              {runs.length > 0 ? (
                <div className={`mt-3 divide-y border-y ${isDark ? "divide-white/10 border-white/10" : "divide-stone-200 border-stone-200"}`}>
                  {runs.map((run, index) => (
                    <button
                      key={run.id}
                      type="button"
                      onClick={() => selectRun(run)}
                      disabled={editLoading}
                      aria-pressed={selectedRunId === run.id}
                      className={`flex w-full items-center justify-between gap-4 py-3 text-left text-sm ${selectedRunId === run.id ? (isDark ? "text-teal-200" : "text-teal-800") : (isDark ? "text-slate-300" : "text-stone-700")}`}
                    >
                      <span className="font-medium">{run.label}</span>
                      <span className={`text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>Run {runs.length - index}</span>
                    </button>
                  ))}
                </div>
              ) : (
                <p className={`mt-3 border-y py-4 text-sm leading-6 ${isDark ? "border-white/10 text-slate-400" : "border-stone-200 text-stone-600"}`}>
                  Paste a passage and run a review to begin.
                </p>
              )}
            </section>

            <section id="editorial-findings" tabIndex={-1} className="mt-8 scroll-mt-6" aria-label="Findings">
              <h2 className="text-xl font-semibold">Findings</h2>
              {!selectedRun ? (
                <p className={`mt-3 border-y py-6 text-sm leading-7 ${isDark ? "border-white/10 text-slate-400" : "border-stone-200 text-stone-600"}`}>
                  Run a review to see the verdict, issues, suggested edits, and cross-referenced manuscript passages beside the source text.
                </p>
              ) : (
                <div className="mt-4">
                  <p className="text-sm text-[rgb(var(--muted-foreground))]">Showing {selectedRun.label}. {sourceChanged ? "The editor has changed; this review still refers to its original passage." : "Matches the passage in the editor."}</p>
                  <details className="my-4 border-l-2 border-[rgb(var(--border))] pl-3"><summary className="cursor-pointer py-2 text-sm font-medium">Reviewed passage</summary><p className="whitespace-pre-wrap break-words text-sm leading-7">{selectedRun.text}</p></details>
                  <EditorialReviewResults
                    key={selectedRun.id}
                    bookId={bookId}
                    chapterNumber={selectedRun.chapterNumber}
                    editText={selectedRun.text}
                    editPassages={selectedRun.passages}
                    editResult={selectedRun.result}
                    isDark={isDark}
                    onSaveNote={saveNote}
                  />
                </div>
              )}
            </section>
          </aside>
        </div>
      </main>
    </WorkspacePage>
  )
}

function StatusLine({ isDark, message, tone }: { isDark: boolean; message: string; tone: "error" | "success" | "info" }) {
  const toneClass = tone === "error"
    ? isDark ? "border-red-400 text-red-200" : "border-red-500 text-red-700"
    : tone === "success"
      ? isDark ? "border-teal-300 text-teal-200" : "border-teal-700 text-teal-800"
      : isDark ? "border-slate-500 text-slate-300" : "border-stone-400 text-stone-600"

  return <p role={tone === "error" ? "alert" : "status"} className={`mt-4 border-l-2 pl-3 text-sm leading-6 ${toneClass}`}>{message}</p>
}
