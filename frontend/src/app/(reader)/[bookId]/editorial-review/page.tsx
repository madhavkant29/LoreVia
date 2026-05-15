"use client"

import { useCallback, useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { useParams } from "next/navigation"

import { AuthorToolsNav } from "@/components/layout/AuthorToolsNav"
import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { saveContextualVaultNote } from "@/lib/utils/notes"
import type { Book } from "@/types/book"
import type { EditorialContinuityIssue, EditorialGrammarIssue, EditorialReview, EditorialReviewPassage } from "@/types/intelligence"

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
    setBookMode(book.mode ?? "author")
  }, [book])

  const saveNote = useCallback(async (title: string, body: string, chapterNumber: number | null) => {
    try {
      const saved = await saveContextualVaultNote({
        bookId,
        title,
        content: body,
        context: "story_advisor",
        folderSegments: chapterNumber ? ["Editorial Review", `Chapter ${chapterNumber}`] : ["Editorial Review"],
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
    setEditResult(null)
    try {
      const result = await intelligenceApi.editorialReview(
        bookId,
        editText,
        editChapter ? Number.parseInt(editChapter, 10) : undefined
      )
      setEditResult(result.review)
      setEditPassages(result.retrieved_passages)
    } catch {
      setEditError("Review failed. Check your connection and try again.")
    } finally {
      setEditLoading(false)
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
    <div className={`min-h-screen ${isDark ? "bg-[linear-gradient(180deg,#05030a_0%,#0a0f18_55%,#111827_100%)] text-slate-100" : "bg-[linear-gradient(180deg,#faf3ea_0%,#f2f1fb_45%,#eef5fb_100%)] text-stone-950"}`}>
      <div className="mx-auto max-w-[108rem] px-4 pb-20 pt-6 sm:px-6 lg:px-8">
        <div className="grid gap-6 xl:grid-cols-[17rem_minmax(0,1fr)]">
          <AuthorToolsNav
            bookId={bookId}
            active="editorial-review"
            isDark={isDark}
            title="Editorial review"
            description="Run a focused editorial pass with continuity, grammar, formatting, and theme checks in one place."
          />

          <main className="space-y-6">
            <section className={`rounded-[1.8rem] border p-6 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-white/70 bg-white/88"}`}>
              <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                <div className="max-w-3xl">
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.28em] ${isDark ? "text-indigo-300" : "text-indigo-700"}`}>Editorial workspace</p>
                  <h1 className={`mt-2 font-serif text-4xl ${isDark ? "text-white" : "text-stone-950"}`}>{book?.title || "Book"} editorial review</h1>
                  <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                    Paste a scene, passage, or full chapter to cross-check continuity, tighten presentation, and save review notes back into the shared workspace.
                  </p>
                </div>
                <div className="flex flex-wrap gap-3">
                  <Link href={`/${bookId}/advisor`} className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-white/10 text-slate-100" : "bg-white text-stone-800"}`}>
                    Open story advisor
                  </Link>
                  <Link href={`/${bookId}/notes`} className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-white/10 text-slate-100" : "bg-white text-stone-800"}`}>
                    Open notes
                  </Link>
                  <Link href={`/${bookId}/manuscript`} className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-indigo-500 text-white" : "bg-stone-900 text-white"}`}>
                    Open manuscript
                  </Link>
                </div>
              </div>
            </section>

            <section className={`rounded-[1.8rem] border p-6 ${isDark ? "border-white/10 bg-black/45" : "border-stone-200 bg-white/90"}`}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.26em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Manuscript import</p>
                  <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                    Paste a chapter, upload replacements, or import smaller source files directly from this page before you review them.
                  </p>
                </div>
                <button
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
                  className={`rounded-[0.8rem] border px-4 py-2 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-55 ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-stone-50 text-stone-700 hover:bg-white"}`}
                >
                  {bookMode === "author" ? "Author mode active" : canUseAuthorMode ? "Convert reader upload to author upload" : "Author mode locked"}
                </button>
              </div>

              <div className="mt-5 flex flex-col gap-4">
                <input
                  type="file"
                  multiple
                  accept=".pdf,.epub,.docx,.txt,.md"
                  onChange={(event) => setImportFiles(Array.from(event.target.files ?? []))}
                  className={`rounded-[0.9rem] border px-3 py-3 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-stone-50 text-stone-700"}`}
                />
                <div className="flex flex-wrap gap-3">
                  <label className={`flex items-center gap-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                    <input type="checkbox" checked={replaceExisting} onChange={(event) => setReplaceExisting(event.target.checked)} />
                    Update current chapter
                  </label>
                  <label className={`flex items-center gap-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                    <input type="checkbox" checked={splitIntoChapters} onChange={(event) => setSplitIntoChapters(event.target.checked)} />
                    Split PDFs into chapters
                  </label>
                  <label className={`flex items-center gap-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                    <input type="checkbox" checked={chunkLongDocuments} onChange={(event) => setChunkLongDocuments(event.target.checked)} />
                    Chunk long documents
                  </label>
                </div>
                <div className="flex flex-wrap gap-3">
                  <button
                    onClick={() => void importManuscript()}
                    disabled={importLoading || (!editText.trim() && importFiles.length === 0)}
                    className="rounded-[0.8rem] bg-[linear-gradient(135deg,#0f766e,#115e59)] px-5 py-2.5 text-sm font-semibold text-white transition disabled:opacity-40"
                  >
                    {importLoading ? "Importing..." : replaceExisting ? "Update current upload" : "Add to current upload"}
                  </button>
                  {importMessage ? (
                    <p className={`self-center text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{importMessage}</p>
                  ) : null}
                </div>
              </div>
            </section>

            <section className={`rounded-[1.8rem] border p-6 ${isDark ? "border-white/10 bg-black/45" : "border-stone-200 bg-white/90"}`}>
              <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:gap-3">
                <div className="w-full sm:max-w-[11rem]">
                  <label className={`block text-[11px] font-semibold uppercase tracking-[0.26em] mb-2 ${isDark ? "text-slate-400" : "text-stone-400"}`}>
                    Chapter number
                  </label>
                  <input
                    type="number"
                    min={1}
                    value={editChapter}
                    onChange={(event) => setEditChapter(event.target.value)}
                    placeholder="e.g. 42"
                    className="w-full rounded-[0.95rem] border border-stone-300 bg-stone-50 px-3 py-2 text-sm text-stone-900 outline-none transition placeholder:text-stone-500 focus:border-indigo-400"
                  />
                </div>
                <button
                  onClick={() => void runEditorialReview()}
                  disabled={!editText.trim() || editLoading}
                  className="rounded-[0.8rem] bg-[linear-gradient(135deg,#4f46e5,#4338ca)] px-5 py-2.5 text-sm font-semibold text-white shadow-[0_8px_24px_-12px_rgba(79,70,229,0.7)] transition disabled:opacity-40 hover:-translate-y-[1px]"
                >
                  {editLoading ? "Reviewing..." : "Run Editorial Review"}
                </button>
              </div>

              <textarea
                value={editText}
                onChange={(event) => setEditText(event.target.value)}
                placeholder="Paste your passage here: a paragraph, a scene, or a full chapter section."
                rows={14}
                className="mt-4 w-full resize-y rounded-[1rem] border border-stone-300 bg-[#f8f6f1] px-4 py-3 text-sm leading-7 text-stone-900 outline-none transition placeholder:text-stone-500 focus:border-indigo-400"
              />

              {editError ? (
                <p className={`mt-3 rounded-[0.8rem] border px-4 py-2 text-sm ${isDark ? "border-red-500/25 bg-red-500/10 text-red-300" : "border-red-200 bg-red-50 text-red-700"}`}>
                  {editError}
                </p>
              ) : null}

              {saveStatus ? (
                <p className={`mt-3 rounded-[0.8rem] border px-4 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-stone-50 text-stone-700"}`}>
                  {saveStatus}
                </p>
              ) : null}

              {editLoading ? (
                <div className={`mt-4 animate-pulse space-y-2 rounded-[1rem] border p-4 ${isDark ? "border-white/8 bg-white/3" : "border-stone-100 bg-stone-50"}`}>
                  <div className={`h-2.5 w-40 rounded-full ${isDark ? "bg-white/10" : "bg-stone-200"}`} />
                  <div className={`h-2.5 w-full rounded-full ${isDark ? "bg-white/8" : "bg-stone-100"}`} />
                  <div className={`h-2.5 w-3/4 rounded-full ${isDark ? "bg-white/6" : "bg-stone-100"}`} />
                </div>
              ) : null}
            </section>

            {editResult ? (
              <section className="space-y-5">
                <div className={`rounded-[1.5rem] border px-6 py-5 ${isDark ? "border-indigo-500/25 bg-indigo-500/8" : "border-violet-100 bg-violet-50"}`}>
                  <p className={`mb-2 text-[11px] font-bold uppercase tracking-[0.28em] ${isDark ? "text-indigo-200" : "text-indigo-700"}`}>Overall Verdict</p>
                  <p className={`text-base leading-7 font-medium ${isDark ? "text-slate-100" : "text-stone-900"}`}>{editResult.overall_verdict}</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <button
                      onClick={async () => {
                        const chapterNumber = editChapter ? Number.parseInt(editChapter, 10) : null
                        await saveNote(
                          chapterNumber ? `Editorial Review - Chapter ${chapterNumber}` : "Editorial Review",
                          editResult.overall_verdict,
                          chapterNumber
                        )
                      }}
                      className={`rounded-[0.8rem] border px-4 py-2 text-xs font-semibold ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}
                    >
                      Save summary note
                    </button>
                    <button
                      onClick={async () => {
                        const blob = await intelligenceApi.continuityReport(
                          bookId,
                          editText,
                          "pdf",
                          editChapter ? Number.parseInt(editChapter, 10) : undefined
                        )
                        const url = URL.createObjectURL(blob)
                        const link = document.createElement("a")
                        link.href = url
                        link.download = "continuity-report.pdf"
                        link.click()
                        URL.revokeObjectURL(url)
                      }}
                      className={`rounded-[0.8rem] border px-4 py-2 text-xs font-semibold ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}
                    >
                      Download continuity report
                    </button>
                  </div>
                </div>

                <div className={`rounded-[1.5rem] border px-5 py-4 ${
                  editResult.thematic_fit.score === "strong"
                    ? isDark ? "border-teal-500/25 bg-teal-500/8" : "border-teal-200 bg-teal-50"
                    : editResult.thematic_fit.score === "weak"
                      ? isDark ? "border-red-500/25 bg-red-500/8" : "border-red-200 bg-red-50"
                      : isDark ? "border-amber-500/25 bg-amber-500/8" : "border-amber-100 bg-amber-50"
                }`}>
                  <div className="mb-2 flex items-center gap-2">
                    <p className={`text-[11px] font-bold uppercase tracking-[0.28em] ${isDark ? "text-slate-300" : "text-stone-500"}`}>Thematic Fit</p>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.18em] ${
                      editResult.thematic_fit.score === "strong"
                        ? isDark ? "bg-teal-500/20 text-teal-300" : "bg-teal-100 text-teal-700"
                        : editResult.thematic_fit.score === "weak"
                          ? isDark ? "bg-red-500/20 text-red-300" : "bg-red-100 text-red-700"
                          : isDark ? "bg-amber-500/20 text-amber-300" : "bg-amber-100 text-amber-700"
                    }`}>
                      {editResult.thematic_fit.score}
                    </span>
                  </div>
                  <p className={`text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{editResult.thematic_fit.notes}</p>
                </div>

                {editResult.continuity_issues.length > 0 ? (
                  <IssueList
                    isDark={isDark}
                    chapterNumber={editChapter ? Number.parseInt(editChapter, 10) : null}
                    issues={editResult.continuity_issues}
                    onSave={async (issue) => {
                      await saveNote(
                        `Continuity: ${issue.title}`.slice(0, 120),
                        [
                          `Continuity issue: ${issue.title}`,
                          `Severity: ${issue.severity}`,
                          `Type: ${issue.type.replace(/_/g, " ")}`,
                          "",
                          issue.description,
                          issue.suggestion ? `Suggestion: ${issue.suggestion}` : "",
                        ].filter(Boolean).join("\n"),
                        editChapter ? Number.parseInt(editChapter, 10) : null
                      )
                    }}
                  />
                ) : null}

                {editResult.grammar_issues.length > 0 ? (
                  <GrammarList
                    isDark={isDark}
                    chapterNumber={editChapter ? Number.parseInt(editChapter, 10) : null}
                    issues={editResult.grammar_issues}
                    onSave={async (issue) => {
                      await saveNote(
                        `Grammar: ${issue.issue}`.slice(0, 120),
                        [
                          `Grammar issue: ${issue.issue}`,
                          "",
                          `Original: "${issue.original}"`,
                          `Fix: "${issue.fix}"`,
                        ].join("\n"),
                        editChapter ? Number.parseInt(editChapter, 10) : null
                      )
                    }}
                  />
                ) : null}

                {editResult.formatting_notes.length > 0 ? (
                  <div>
                    <p className={`mb-3 text-[11px] font-bold uppercase tracking-[0.28em] ${isDark ? "text-slate-300" : "text-stone-500"}`}>
                      Formatting Notes
                    </p>
                    <div className={`space-y-2 rounded-[1.2rem] border px-5 py-4 ${isDark ? "border-white/8 bg-white/4" : "border-stone-100 bg-stone-50"}`}>
                      {editResult.formatting_notes.map((note, index) => (
                        <div key={`${note}-${index}`} className="flex items-start gap-2.5">
                          <span className={`mt-0.5 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>•</span>
                          <div className="flex-1">
                            <p className={`text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{note}</p>
                            <button
                              type="button"
                              onClick={() => void saveNote("Formatting note", `Formatting note:\n${note}`, editChapter ? Number.parseInt(editChapter, 10) : null)}
                              className={`mt-2 rounded-full px-3 py-1 text-[11px] font-semibold transition ${isDark ? "bg-white/10 text-slate-200 hover:bg-white/15" : "bg-white text-stone-700 hover:bg-stone-50"}`}
                            >
                              Save note
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                {editPassages.length > 0 ? (
                  <div>
                    <p className={`mb-3 text-[11px] font-bold uppercase tracking-[0.28em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                      Cross-referenced passages
                    </p>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {editPassages.map((passage, index) => (
                        <div key={`${passage.chapter_num}-${index}`} className={`rounded-[1rem] border p-4 ${isDark ? "border-white/8 bg-white/3" : "border-stone-100 bg-stone-50"}`}>
                          <p className={`mb-1 text-[10px] font-bold uppercase tracking-[0.22em] ${isDark ? "text-indigo-200" : "text-indigo-700"}`}>
                            Ch. {passage.chapter_num}{passage.chapter_title ? `: ${passage.chapter_title}` : ""}
                          </p>
                          <p className={`text-xs leading-5 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{passage.excerpt}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                {editResult.continuity_issues.length === 0 && editResult.grammar_issues.length === 0 ? (
                  <div className={`rounded-[1.5rem] border p-6 text-center ${isDark ? "border-teal-500/20 bg-teal-500/8" : "border-teal-200 bg-teal-50"}`}>
                    <p className="mb-2 text-sm font-semibold uppercase tracking-[0.24em]">Clear</p>
                    <p className={`font-semibold ${isDark ? "text-teal-200" : "text-teal-800"}`}>No continuity or grammar issues found</p>
                    <p className={`mt-1 text-xs ${isDark ? "text-teal-300" : "text-teal-700"}`}>The passage looks consistent with the existing manuscript context.</p>
                  </div>
                ) : null}
              </section>
            ) : null}
          </main>
        </div>
      </div>
    </div>
  )
}

function IssueList({
  chapterNumber,
  isDark,
  issues,
  onSave,
}: {
  chapterNumber: number | null
  isDark: boolean
  issues: EditorialContinuityIssue[]
  onSave: (issue: EditorialContinuityIssue) => Promise<void>
}) {
  return (
    <div>
      <p className={`mb-3 text-[11px] font-bold uppercase tracking-[0.28em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>
        Continuity Issues ({issues.length})
      </p>
      <div className="space-y-3">
        {issues.map((issue, index) => (
          <div key={`${issue.title}-${index}`} className={`rounded-[1.2rem] border px-5 py-4 ${
            issue.severity === "critical"
              ? isDark ? "border-red-500/30 bg-red-500/10" : "border-red-200 bg-red-50"
              : issue.severity === "moderate"
                ? isDark ? "border-amber-500/30 bg-amber-500/8" : "border-amber-200 bg-amber-50"
                : isDark ? "border-white/10 bg-white/4" : "border-stone-100 bg-stone-50"
          }`}>
            <div className="mb-2 flex items-center gap-2 flex-wrap">
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.22em] ${
                issue.severity === "critical"
                  ? isDark ? "bg-red-500/20 text-red-300" : "bg-red-100 text-red-700"
                  : issue.severity === "moderate"
                    ? isDark ? "bg-amber-500/20 text-amber-300" : "bg-amber-100 text-amber-700"
                    : isDark ? "bg-white/10 text-slate-300" : "bg-stone-100 text-stone-600"
              }`}>
                {issue.severity}
              </span>
              <span className={`text-[10px] font-medium ${isDark ? "text-slate-400" : "text-stone-500"}`}>{issue.type.replace(/_/g, " ")}</span>
              <button
                type="button"
                onClick={() => void onSave(issue)}
                className={`ml-auto rounded-full px-3 py-1 text-[11px] font-semibold transition ${isDark ? "bg-white/10 text-slate-200 hover:bg-white/15" : "bg-white text-stone-700 hover:bg-stone-50"}`}
              >
                Save note{chapterNumber ? ` (Ch. ${chapterNumber})` : ""}
              </button>
            </div>
            <p className={`mb-1 text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{issue.title}</p>
            <p className={`text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{issue.description}</p>
            {issue.suggestion ? (
              <p className={`mt-2 text-xs leading-5 font-medium ${isDark ? "text-indigo-200" : "text-indigo-700"}`}>
                → {issue.suggestion}
              </p>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  )
}

function GrammarList({
  chapterNumber,
  isDark,
  issues,
  onSave,
}: {
  chapterNumber: number | null
  isDark: boolean
  issues: EditorialGrammarIssue[]
  onSave: (issue: EditorialGrammarIssue) => Promise<void>
}) {
  return (
    <div>
      <p className={`mb-3 text-[11px] font-bold uppercase tracking-[0.28em] ${isDark ? "text-slate-300" : "text-stone-500"}`}>
        Grammar & Spelling ({issues.length})
      </p>
      <div className="space-y-2.5">
        {issues.map((issue, index) => (
          <div key={`${issue.issue}-${index}`} className={`rounded-[1.1rem] border px-4 py-4 ${isDark ? "border-white/8 bg-white/4" : "border-stone-100 bg-stone-50"}`}>
            <p className={`mb-1 text-[10px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>{issue.issue}</p>
            <p className={`mb-1 text-sm line-through opacity-70 ${isDark ? "text-slate-300" : "text-stone-600"}`}>"{issue.original}"</p>
            <p className={`text-sm font-medium ${isDark ? "text-teal-300" : "text-teal-700"}`}>→ "{issue.fix}"</p>
            <button
              type="button"
              onClick={() => void onSave(issue)}
              className={`mt-3 rounded-full px-3 py-1 text-[11px] font-semibold transition ${isDark ? "bg-white/10 text-slate-200 hover:bg-white/15" : "bg-white text-stone-700 hover:bg-stone-50"}`}
            >
              Save note{chapterNumber ? ` (Ch. ${chapterNumber})` : ""}
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
