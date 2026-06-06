"use client"

import type { ChangeEvent, ReactNode } from "react"
import { useCallback, useEffect, useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import dynamic from "next/dynamic"
import Link from "next/link"
import type { Route } from "next"
import { useParams } from "next/navigation"

import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { saveContextualVaultNote } from "@/lib/utils/notes"
import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { SidebarSkeleton, Skeleton } from "@/components/ui/Skeleton"
import type { Book } from "@/types/book"
import type { EditorialReview, EditorialReviewPassage } from "@/types/intelligence"

const EDITORIAL_ACCEPT = ".pdf,.epub,.docx,.txt,.md"

const AuthorToolsNav = dynamic(
  () => import("@/components/layout/AuthorToolsNav").then((module) => module.AuthorToolsNav),
  {
    ssr: false,
    loading: () => <SidebarSkeleton className="min-h-[28rem]" />,
  }
)

const EditorialReviewResults = dynamic(
  () => import("@/components/reader/EditorialReviewResults").then((module) => module.EditorialReviewResults),
  {
    ssr: false,
    loading: () => (
      <section className="space-y-4">
        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-6" role="status" aria-label="Loading editorial review results" aria-busy="true">
          <span className="sr-only">Loading editorial review results</span>
          <Skeleton className="h-3 w-28 bg-white/10" />
          <Skeleton className="mt-4 h-4 w-3/4 bg-white/10" />
          <Skeleton className="mt-2 h-4 w-1/2 bg-white/10" />
        </div>
      </section>
    ),
  }
)

export default function EditorialReviewPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const userTier = useAuthStore((state) => state.user?.tier)
  const canUseAuthorMode = canUseAuthorFeatures(userTier)
  const isDark = theme === "dark"

  const { data: book = null } = useQuery<Book | null>({
    queryKey: asQueryKey(bookCacheKey(bookId, "detail")),
    queryFn: () => booksApi.get(bookId),
  })
  const [bookMode, setBookMode] = useState<"reader" | "author">("author")
  const [editText, setEditText] = useState("")
  const [editChapter, setEditChapter] = useState("")
  const [editLoading, setEditLoading] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)
  const [editProgress, setEditProgress] = useState<string | null>(null)
  const [editResult, setEditResult] = useState<EditorialReview | null>(null)
  const [editPassages, setEditPassages] = useState<EditorialReviewPassage[]>([])
  const [importFiles, setImportFiles] = useState<File[]>([])
  const [replaceExisting, setReplaceExisting] = useState(false)
  const [chunkLongDocuments, setChunkLongDocuments] = useState(false)
  const [splitIntoChapters, setSplitIntoChapters] = useState(true)
  const [importLoading, setImportLoading] = useState(false)
  const [importMessage, setImportMessage] = useState<string | null>(null)
  const [saveStatus, setSaveStatus] = useState<string | null>(null)

  useEffect(() => {
    if (!book) return
    setBookMode(book.workspace_shell ?? book.mode ?? "author")
  }, [book])

  const fileNames = useMemo(
    () => (importFiles.length > 0 ? importFiles.map((file) => file.name).join(", ") : "No file chosen"),
    [importFiles]
  )
  const chapterNumber = editChapter ? Number.parseInt(editChapter, 10) : null
  const textCharacterCount = useMemo(() => editText.length.toLocaleString(), [editText])
  const canImport = Boolean(editText.trim() || importFiles.length > 0)
  const canReview = Boolean(editText.trim()) && !editLoading

  const saveNote = useCallback(async (title: string, body: string, targetChapterNumber: number | null) => {
    try {
      const saved = await saveContextualVaultNote({
        bookId,
        title,
        content: body,
        context: "story_advisor",
        folderSegments: targetChapterNumber ? ["Editorial Review", `Chapter ${targetChapterNumber}`] : ["Editorial Review"],
      })
      setSaveStatus(`Saved note to ${saved.path}`)
    } catch {
      setSaveStatus("Could not save note. Please try again.")
    } finally {
      window.setTimeout(() => setSaveStatus(null), 2400)
    }
  }, [bookId])

  const runEditorialReview = async () => {
    if (!editText.trim()) return
    setEditLoading(true)
    setEditError(null)
    setEditProgress(null)
    setEditResult(null)
    try {
      const result = await intelligenceApi.editorialReviewStream(
        bookId,
        editText,
        editChapter ? Number.parseInt(editChapter, 10) : undefined,
        { onStage: setEditProgress }
      )
      setEditResult(result.review)
      setEditPassages(result.retrieved_passages)
    } catch {
      setEditError("Review failed. Check your connection and try again.")
    } finally {
      setEditLoading(false)
      setEditProgress(null)
    }
  }

  const importManuscript = async () => {
    if ((!editText.trim() && importFiles.length === 0) || importLoading) return
    setImportLoading(true)
    setImportMessage(null)
    try {
      const result = await booksApi.importManuscript(bookId, {
        text: editText.trim() || undefined,
        chapterNumber: editChapter ? Number.parseInt(editChapter, 10) : undefined,
        replaceExisting,
        chunkLongDocuments,
        splitIntoChapters,
        files: importFiles,
      })
      setBookMode(result.mode)
      setImportMessage(`Imported chapters ${result.imported_chapters.join(", ")}.`)
    } catch {
      setImportMessage("Import failed. Check the files or chapter number and try again.")
    } finally {
      setImportLoading(false)
    }
  }

  return (
    <div className={`min-h-screen ${isDark ? "bg-[#071211] text-slate-100" : "bg-stone-50 text-stone-950"}`}>
      <div className="min-h-screen">
      <div className="mx-auto max-w-[110rem] px-4 pb-16 pt-5 sm:px-6 lg:px-7">
        <div className="grid gap-5 xl:grid-cols-[16.75rem_minmax(0,1fr)]">
          <AuthorToolsNav
            bookId={bookId}
            active="editorial-review"
            isDark={isDark}
            bookData={book}
            title="Editorial review"
            description="Run a focused editorial pass with continuity, grammar, formatting, and theme checks in one place."
            variant="rail"
            railSize="compact"
          />

          <main className="min-w-0 space-y-5">
            <WorkspaceFamilyHeader
              active="editorial-review"
              bookId={bookId}
              family="review-center"
              title={`${book?.title || "Book"} editorial review`}
              description="Paste a scene, passage, or chapter to cross-check continuity, tighten presentation, and save review notes back into the shared workspace."
              actions={(
                <>
                  <HeaderActionLink href={`/${bookId}/advisor` as Route} isDark={isDark}>
                    Open story advisor
                  </HeaderActionLink>
                  <HeaderActionLink href={`/${bookId}/notes` as Route} isDark={isDark}>
                    Open notes
                  </HeaderActionLink>
                  <HeaderActionLink href={`/${bookId}/manuscript` as Route} isDark={isDark} primary>
                    Open manuscript
                  </HeaderActionLink>
                </>
              )}
            />

            <section className={surfaceCardClass(isDark, "px-5 py-6 sm:px-6")}>
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="max-w-3xl">
                  <p className={`text-3xs font-semibold uppercase tracking-[0.32em] ${isDark ? "text-teal-300" : "text-teal-700"}`}>Manuscript import</p>
                  <p className={`mt-3 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                    Paste a chapter, upload replacements, or import smaller source files directly from this page before you review them.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={async () => {
                    if (!canUseAuthorMode || bookMode === "author") return
                    try {
                      const updated = await booksApi.setMode(bookId, "author")
                      setBookMode(updated.mode)
                      setImportMessage("This upload now behaves like an author workspace.")
                    } catch {
                      setImportMessage("Could not switch this upload to author mode right now.")
                    }
                  }}
                  disabled={!canUseAuthorMode || bookMode === "author"}
                  className={`inline-flex items-center gap-2 rounded-full border px-3.5 py-2 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-70 ${
                    bookMode === "author"
                      ? isDark
                        ? "border-emerald-400/20 bg-emerald-500/10 text-emerald-200"
                        : "border-emerald-200 bg-emerald-50 text-emerald-700"
                      : isDark
                        ? "border-white/10 bg-white/[0.04] text-slate-200 hover:bg-white/[0.08]"
                        : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"
                  }`}
                >
                  <span className={`h-2 w-2 rounded-full ${bookMode === "author" ? "bg-emerald-400" : isDark ? "bg-slate-500" : "bg-stone-400"}`} />
                  {bookMode === "author" ? "Author mode active" : canUseAuthorMode ? "Convert to author mode" : "Author mode locked"}
                </button>
              </div>

              <div className="mt-6 space-y-5">
                <div className={`overflow-hidden rounded-md border ${isDark ? "border-white/10 bg-[#08101a]" : "border-stone-200 bg-stone-50/80"}`}>
                  <label
                    htmlFor="editorial-review-files"
                    className={`flex cursor-pointer flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between ${isDark ? "hover:bg-white/[0.03]" : "hover:bg-white/70"}`}
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border ${isDark ? "border-white/10 bg-white/[0.04] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                        <UploadIcon />
                      </span>
                      <span className="min-w-0">
                        <span className={`block text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Choose files</span>
                        <span className={`mt-1 block truncate text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{fileNames}</span>
                      </span>
                    </div>
                    <span className={`text-xs font-medium uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>PDF, EPUB, DOCX, TXT, MD</span>
                  </label>
                  <input
                    id="editorial-review-files"
                    type="file"
                    multiple
                    accept={EDITORIAL_ACCEPT}
                    onChange={(event) => setImportFiles(Array.from(event.target.files ?? []))}
                    className="sr-only"
                  />
                </div>

                <fieldset className="space-y-3">
                  <legend className="sr-only">Manuscript import options</legend>
                  <div className="flex flex-wrap gap-x-6 gap-y-3">
                    <CheckboxField
                      checked={replaceExisting}
                      isDark={isDark}
                      label="Update current chapter"
                      onChange={(event) => setReplaceExisting(event.target.checked)}
                    />
                    <CheckboxField
                      checked={splitIntoChapters}
                      isDark={isDark}
                      label="Split POVs into chapters"
                      onChange={(event) => setSplitIntoChapters(event.target.checked)}
                    />
                    <CheckboxField
                      checked={chunkLongDocuments}
                      isDark={isDark}
                      label="Chunk long documents"
                      onChange={(event) => setChunkLongDocuments(event.target.checked)}
                    />
                  </div>
                </fieldset>

                <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                  <button
                    type="button"
                    onClick={() => void importManuscript()}
                    disabled={importLoading || !canImport}
                    className={`inline-flex items-center justify-center rounded-md px-4 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-45 ${
                      isDark
                        ? "border border-teal-400/30 bg-teal-500/12 text-teal-100 hover:bg-teal-500/18"
                        : "border border-teal-200 bg-teal-700 text-white hover:bg-teal-800"
                    }`}
                  >
                    {importLoading ? "Importing..." : replaceExisting ? "Update current upload" : "Add to current upload"}
                  </button>
                  {importMessage ? <StatusBanner isDark={isDark} message={importMessage} tone={inferStatusTone(importMessage)} /> : null}
                </div>
              </div>
            </section>

            <section className={surfaceCardClass(isDark, "px-5 py-6 sm:px-6")}>
              <div className="flex flex-col gap-5">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                  <div className="grid gap-4 sm:grid-cols-[minmax(0,11.5rem)_auto] sm:items-end">
                    <label className="block">
                      <span className={`block text-3xs font-semibold uppercase tracking-[0.32em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Chapter number</span>
                      <input
                        type="number"
                        min={1}
                        value={editChapter}
                        onChange={(event) => setEditChapter(event.target.value)}
                        className={`mt-3 w-full rounded-md border px-3.5 py-3 text-sm outline-none transition ${
                          isDark
                            ? "border-white/10 bg-[#08101a] text-slate-100 focus:border-violet-400/60 focus:bg-[#0a1420]"
                            : "border-stone-200 bg-white text-stone-900 focus:border-violet-400"
                        }`}
                      />
                      <span className={`mt-2 block text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Use the source chapter number when there is one.</span>
                    </label>

                    <button
                      type="button"
                      onClick={() => void runEditorialReview()}
                      disabled={!canReview}
                      className={`inline-flex min-h-[3rem] items-center justify-center rounded-md px-5 py-3 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-45 ${
                        isDark
                          ? "bg-violet-600 text-white hover:bg-violet-500"
                          : "bg-violet-700 text-white hover:bg-violet-800"
                      }`}
                    >
                      {editLoading ? "Reviewing..." : "Run Editorial Review"}
                    </button>
                  </div>

                  <div className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>
                    {editLoading ? "Review in progress" : "Ready for continuity and presentation checks"}
                  </div>
                </div>

                <label className="block">
                  <span className={`mb-3 block text-3xs font-semibold uppercase tracking-[0.32em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Passage text</span>
                  <div className={`overflow-hidden rounded-md border ${isDark ? "border-white/10 bg-[#08101a]" : "border-stone-200 bg-white"}`}>
                    <textarea
                      value={editText}
                      onChange={(event) => setEditText(event.target.value)}
                      rows={18}
                      className={`block min-h-[22rem] w-full resize-y border-0 bg-transparent px-4 py-4 text-sm leading-7 outline-none ring-0 focus:ring-0 ${
                        isDark ? "text-slate-100" : "text-stone-900"
                      }`}
                    />
                    <div className={`flex items-center justify-between gap-3 border-t px-4 py-3 text-xs ${isDark ? "border-white/8 text-slate-500" : "border-stone-200 text-stone-500"}`}>
                      <span>{chapterNumber ? `Review target: Chapter ${chapterNumber}` : "Review target: custom passage. Paste a paragraph, scene, or full chapter section."}</span>
                      <span>{textCharacterCount} characters</span>
                    </div>
                  </div>
                </label>

                {editError ? <StatusBanner isDark={isDark} message={editError} tone="error" /> : null}
                {editLoading && editProgress ? <StatusBanner isDark={isDark} message={editProgress} tone="info" /> : null}
                {saveStatus ? <StatusBanner isDark={isDark} message={saveStatus} tone={inferStatusTone(saveStatus)} /> : null}

                {editLoading ? (
                  <div className={`space-y-3 rounded-md border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/80"}`} role="status" aria-label="Loading editorial review" aria-busy="true">
                    <span className="sr-only">Loading editorial review</span>
                    <Skeleton className={`h-2.5 w-40 ${isDark ? "bg-white/10" : "bg-stone-200"}`} />
                    <Skeleton className={`h-2.5 w-full ${isDark ? "bg-white/8" : "bg-stone-200/80"}`} />
                    <Skeleton className={`h-2.5 w-3/4 ${isDark ? "bg-white/6" : "bg-stone-200/70"}`} />
                  </div>
                ) : null}
              </div>
            </section>

            {editResult ? (
              <EditorialReviewResults
                bookId={bookId}
                chapterNumber={chapterNumber}
                editText={editText}
                editPassages={editPassages}
                editResult={editResult}
                isDark={isDark}
                onSaveNote={saveNote}
              />
            ) : null}
          </main>
        </div>
      </div>
      </div>
    </div>
  )
}

function HeaderActionLink({
  children,
  href,
  isDark,
  primary = false,
}: {
  children: ReactNode
  href: Route
  isDark: boolean
  primary?: boolean
}) {
  return (
    <Link
      href={href}
      className={`inline-flex min-h-[2.9rem] items-center justify-center rounded-md border px-4 py-2.5 text-sm font-semibold transition ${
        primary
          ? isDark
            ? "border-teal-300 bg-teal-300 text-slate-950 hover:bg-teal-200"
            : "border-[#1f615d] bg-[#1f615d] text-white hover:bg-[#174c49]"
          : isDark
            ? "border-white/10 bg-white/[0.04] text-slate-100 hover:bg-white/[0.08]"
            : "border-stone-200 bg-white text-stone-800 hover:bg-stone-50"
      }`}
    >
      {children}
    </Link>
  )
}

function CheckboxField({
  checked,
  isDark,
  label,
  onChange,
}: {
  checked: boolean
  isDark: boolean
  label: string
  onChange: (event: ChangeEvent<HTMLInputElement>) => void
}) {
  return (
    <label className={`inline-flex items-center gap-3 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className={`h-4 w-4 rounded border ${isDark ? "border-white/20 bg-[#08101a] text-violet-400" : "border-stone-300 text-violet-700"}`}
      />
      <span>{label}</span>
    </label>
  )
}

function StatusBanner({
  isDark,
  message,
  tone,
}: {
  isDark: boolean
  message: string
  tone: "error" | "success" | "info"
}) {
  const toneClass = tone === "error"
    ? isDark ? "border-red-500/25 bg-red-500/10 text-red-200" : "border-red-200 bg-red-50 text-red-700"
    : tone === "success"
      ? isDark ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-200" : "border-emerald-200 bg-emerald-50 text-emerald-700"
      : isDark ? "border-white/10 bg-white/[0.04] text-slate-300" : "border-stone-200 bg-stone-50 text-stone-700"

  return (
    <p aria-live="polite" className={`rounded-md border px-4 py-2.5 text-sm ${toneClass}`}>
      {message}
    </p>
  )
}

function UploadIcon() {
  return (
    <svg aria-hidden="true" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 15V4" />
      <path strokeLinecap="round" strokeLinejoin="round" d="m7.5 8.5 4.5-4.5 4.5 4.5" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 16.5v1A2.5 2.5 0 0 0 7.5 20h9a2.5 2.5 0 0 0 2.5-2.5v-1" />
    </svg>
  )
}

function inferStatusTone(message: string): "error" | "success" | "info" {
  const lower = message.toLowerCase()
  if (lower.includes("failed") || lower.includes("could not")) return "error"
  if (lower.includes("saved") || lower.includes("imported") || lower.includes("active")) return "success"
  return "info"
}

function surfaceCardClass(isDark: boolean, extra = "") {
  return `rounded-lg border ${isDark ? "border-white/10 bg-[rgba(8,14,22,0.9)]" : "border-stone-200 bg-white/92"} ${extra}`
}
