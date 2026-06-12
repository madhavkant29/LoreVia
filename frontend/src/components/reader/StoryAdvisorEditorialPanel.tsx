"use client"

import { memo, useEffect, useState } from "react"
import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import type { EditorialReview, EditorialReviewPassage } from "@/types/intelligence"

type StoryAdvisorEditorialPanelProps = {
  bookId: string
  isDark: boolean
  canUseAuthorMode: boolean
  onSaveNote: (payload: { chapterNumber: number | null; title: string | null; body: string }) => void
}

export const StoryAdvisorEditorialPanel = memo(function StoryAdvisorEditorialPanel({
  bookId,
  isDark,
  canUseAuthorMode,
  onSaveNote,
}: StoryAdvisorEditorialPanelProps) {
  const [bookMode, setBookMode] = useState<"reader" | "author">("author")
  const [editText, setEditText] = useState("")
  const [editChapter, setEditChapter] = useState<string>("")
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

  useEffect(() => {
    let active = true

    void booksApi.get(bookId).then((book) => {
      if (!active) return
      setBookMode(book.mode ?? "author")
    }).catch(() => {
      if (!active) return
      setBookMode("author")
    })

    return () => {
      active = false
    }
  }, [bookId])

  return (
    <div className="space-y-6">
      <p className={`max-w-2xl text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
        Paste a passage you've written. The advisor will cross-check it against your characters'
        personalities, established events, tone, and themes, and it will also flag grammar and formatting issues.
      </p>

      <div className={`rounded-lg border p-6 ${isDark ? "border-white/10 bg-black/80" : "border-stone-200 bg-white"}`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className={`text-3xs font-semibold uppercase tracking-[0.26em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>
              Manuscript import
            </p>
            <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
              Paste a chapter, upload a replacement chapter, import a folder of small PDFs, or convert this upload into an author workspace.
            </p>
          </div>
          <button
            onClick={async () => {
              if (!canUseAuthorMode) return
              if (bookMode === "author") return
              try {
                const updated = await booksApi.setMode(bookId, "author")
                setBookMode(updated.mode)
                setImportMessage("This upload now behaves like an author workspace.")
              } catch {
                setImportMessage("Could not switch this upload to author mode right now.")
              }
            }}
            disabled={!canUseAuthorMode}
            className={`rounded-sm border px-4 py-2 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-55 ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-stone-50 text-stone-700 hover:bg-white"}`}
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
            className={`rounded-sm border px-3 py-3 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-stone-50 text-stone-700"}`}
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
              onClick={async () => {
                if ((!editText.trim() && importFiles.length === 0) || importLoading) return
                setImportLoading(true)
                setImportMessage(null)
                try {
                  const result = await booksApi.importManuscript(bookId, {
                    text: editText.trim() || undefined,
                    chapterNumber: editChapter ? parseInt(editChapter) : undefined,
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
              }}
              disabled={importLoading || (!editText.trim() && importFiles.length === 0)}
              className="rounded-md bg-[#1f615d] px-5 py-2.5 text-sm font-semibold text-white transition-colors disabled:opacity-40"
            >
              {importLoading ? "Importing..." : replaceExisting ? "Update current upload" : "Add to current upload"}
            </button>
            {importMessage ? (
              <p className={`self-center text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{importMessage}</p>
            ) : null}
          </div>
        </div>
      </div>

      <div className={`rounded-lg border p-6 ${isDark ? "border-white/10 bg-black/80" : "border-stone-200 bg-white"}`}>
        <div className="mb-4 flex flex-col gap-4 sm:flex-row sm:items-end sm:gap-3">
          <div className="flex-1">
            <label className={`mb-2 block text-3xs font-semibold uppercase tracking-[0.26em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>
              Chapter number (optional)
            </label>
            <input
              type="number"
              min={1}
              value={editChapter}
              onChange={e => setEditChapter(e.target.value)}
              aria-label="Chapter number"
              className={`w-32 rounded-sm border px-3 py-2 text-sm outline-none transition ${isDark ? "border-white/10 bg-white/5 text-slate-200 focus:border-indigo-500/50" : "border-stone-200 bg-stone-50 text-stone-800 focus:border-violet-300"}`}
            />
            <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Use the source chapter number when this passage belongs to one.</p>
          </div>
          <button
            onClick={async () => {
              if (!editText.trim()) return
              setEditLoading(true)
              setEditError(null)
              setEditProgress(null)
              setEditResult(null)
              try {
                const res = await intelligenceApi.editorialReviewStream(
                  bookId,
                  editText,
                  editChapter ? parseInt(editChapter) : undefined,
                  { onStage: setEditProgress },
                )
                setEditResult(res.review)
                setEditPassages(res.retrieved_passages)
              } catch {
                setEditError("Review failed. Check your connection and try again.")
              } finally {
                setEditLoading(false)
                setEditProgress(null)
              }
            }}
            disabled={!editText.trim() || editLoading}
            className="shrink-0 self-end rounded-md bg-violet-700 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-violet-600 disabled:opacity-40"
          >
            {editLoading ? "Reviewing..." : "Run Editorial Review"}
          </button>
        </div>

        <label className="block">
          <span className={`mb-2 block text-3xs font-semibold uppercase tracking-[0.26em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Passage to review</span>
          <textarea
            value={editText}
            onChange={e => setEditText(e.target.value)}
            rows={10}
            className={`w-full resize-y rounded-md border px-4 py-3 text-sm leading-7 outline-none transition ${isDark ? "border-white/10 bg-white/[0.04] text-slate-200 focus:border-indigo-500/40" : "border-stone-200 bg-stone-50 text-stone-800 focus:border-violet-300"}`}
          />
          <span className={`mt-2 block text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Paste a paragraph, scene, or full chapter section.</span>
        </label>

        {editError ? (
          <p className={`mt-3 rounded-sm border px-4 py-2 text-sm ${isDark ? "border-red-500/25 bg-red-500/10 text-red-300" : "border-red-200 bg-red-50 text-red-700"}`}>
            {editError}
          </p>
        ) : null}

        {editLoading && editProgress ? (
          <p className={`mt-3 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{editProgress}</p>
        ) : null}

        {editLoading ? (
          <div className={`mt-4 animate-pulse space-y-2 rounded-md border p-4 ${isDark ? "border-white/[0.08] bg-white/[0.03]" : "border-stone-100 bg-stone-50"}`}>
            <div className={`h-2.5 w-40 rounded-full ${isDark ? "bg-white/10" : "bg-stone-200"}`} />
            <div className={`h-2.5 w-full rounded-full ${isDark ? "bg-white/[0.08]" : "bg-stone-100"}`} />
            <div className={`h-2.5 w-3/4 rounded-full ${isDark ? "bg-white/6" : "bg-stone-100"}`} />
          </div>
        ) : null}
      </div>

      {editResult ? (
        <div className="space-y-5">
          <div className={`rounded-lg border px-6 py-5 ${isDark ? "border-indigo-500/25 bg-indigo-500/8" : "border-violet-100 bg-violet-50"}`}>
            <p className={`mb-2 text-3xs font-bold uppercase tracking-[0.28em] ${isDark ? "text-indigo-300" : "text-violet-600"}`}>Overall Verdict</p>
            <p className={`text-base font-medium leading-7 ${isDark ? "text-slate-100" : "text-stone-800"}`}>{editResult.overall_verdict}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              <button
                onClick={async () => {
                  const blob = await intelligenceApi.continuityReport(
                    bookId,
                    editText,
                    "pdf",
                    editChapter ? parseInt(editChapter) : undefined,
                  )
                  const url = URL.createObjectURL(blob)
                  const link = document.createElement("a")
                  link.href = url
                  link.download = "continuity-report.pdf"
                  link.click()
                  URL.revokeObjectURL(url)
                }}
                className={`rounded-sm border px-4 py-2 text-xs font-semibold ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}
              >
                Download continuity report
              </button>
            </div>
          </div>

          <div className={`rounded-lg border px-5 py-4 ${
            editResult.thematic_fit.score === "strong"
              ? isDark ? "border-teal-500/25 bg-teal-500/8" : "border-teal-200 bg-teal-50"
              : editResult.thematic_fit.score === "weak"
                ? isDark ? "border-red-500/25 bg-red-500/8" : "border-red-200 bg-red-50"
                : isDark ? "border-amber-500/25 bg-amber-500/8" : "border-amber-100 bg-amber-50"
          }`}>
            <div className="mb-2 flex items-center gap-2">
              <p className={`text-3xs font-bold uppercase tracking-[0.28em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Thematic Fit</p>
              <span className={`rounded-full px-2 py-0.5 text-3xs font-bold uppercase tracking-[0.18em] ${
                editResult.thematic_fit.score === "strong"
                  ? isDark ? "bg-teal-500/20 text-teal-300" : "bg-teal-100 text-teal-700"
                  : editResult.thematic_fit.score === "weak"
                    ? isDark ? "bg-red-500/20 text-red-300" : "bg-red-100 text-red-700"
                    : isDark ? "bg-amber-500/20 text-amber-300" : "bg-amber-100 text-amber-700"
              }`}>
                {editResult.thematic_fit.score}
              </span>
            </div>
            <p className={`text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{editResult.thematic_fit.notes}</p>
          </div>

          {editResult.continuity_issues.length > 0 ? (
            <div>
              <p className={`mb-3 text-3xs font-bold uppercase tracking-[0.28em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>
                Continuity Issues ({editResult.continuity_issues.length})
              </p>
              <div className="space-y-3">
                {editResult.continuity_issues.map((issue, index) => (
                  <div key={index} className={`rounded-md border px-5 py-4 ${
                    issue.severity === "critical"
                      ? isDark ? "border-red-500/30 bg-red-500/10" : "border-red-200 bg-red-50"
                      : issue.severity === "moderate"
                        ? isDark ? "border-amber-500/30 bg-amber-500/8" : "border-amber-200 bg-amber-50"
                        : isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-100 bg-stone-50"
                  }`}>
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <span className={`rounded-full px-2 py-0.5 text-3xs font-bold uppercase tracking-[0.22em] ${
                        issue.severity === "critical"
                          ? isDark ? "bg-red-500/20 text-red-300" : "bg-red-100 text-red-700"
                          : issue.severity === "moderate"
                            ? isDark ? "bg-amber-500/20 text-amber-300" : "bg-amber-100 text-amber-700"
                            : isDark ? "bg-white/10 text-slate-400" : "bg-stone-100 text-stone-500"
                      }`}>{issue.severity}</span>
                      <span className={`text-3xs font-medium ${isDark ? "text-slate-500" : "text-stone-400"}`}>{issue.type.replace(/_/g, " ")}</span>
                      <button
                        type="button"
                        onClick={() => onSaveNote({
                          chapterNumber: editChapter ? parseInt(editChapter) : null,
                          title: `Continuity: ${issue.title}`.slice(0, 120),
                          body: [
                            `Continuity issue: ${issue.title}`,
                            `Severity: ${issue.severity}`,
                            `Type: ${issue.type.replace(/_/g, " ")}`,
                            "",
                            issue.description,
                            issue.suggestion ? `\nSuggestion: ${issue.suggestion}` : "",
                          ].join("\n").trim(),
                        })}
                        className={`ml-auto rounded-full px-3 py-1 text-3xs font-semibold transition ${isDark ? "bg-white/10 text-slate-200 hover:bg-white/15" : "bg-white text-stone-700 hover:bg-stone-50"}`}
                      >
                        Save note
                      </button>
                    </div>
                    <p className={`mb-1 text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{issue.title}</p>
                    <p className={`text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{issue.description}</p>
                    {issue.suggestion ? (
                      <p className={`mt-2 text-xs font-medium leading-5 ${isDark ? "text-indigo-300" : "text-violet-700"}`}>
                        &rarr; {issue.suggestion}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {editResult.grammar_issues.length > 0 ? (
            <div>
              <p className={`mb-3 text-3xs font-bold uppercase tracking-[0.28em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>
                Grammar & Spelling ({editResult.grammar_issues.length})
              </p>
              <div className="space-y-2.5">
                {editResult.grammar_issues.map((issue, index) => (
                  <div key={index} className={`rounded-md border px-4 py-4 ${isDark ? "border-white/[0.08] bg-white/[0.04]" : "border-stone-100 bg-stone-50"}`}>
                    <p className={`mb-1 text-3xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{issue.issue}</p>
                    <p className={`mb-1 text-sm line-through opacity-60 ${isDark ? "text-slate-400" : "text-stone-500"}`}>"{issue.original}"</p>
                    <p className={`text-sm font-medium ${isDark ? "text-teal-300" : "text-teal-700"}`}>&rarr; "{issue.fix}"</p>
                    <div className="mt-3">
                      <button
                        type="button"
                        onClick={() => onSaveNote({
                          chapterNumber: editChapter ? parseInt(editChapter) : null,
                          title: `Grammar: ${issue.issue}`.slice(0, 120),
                          body: [
                            `Grammar issue: ${issue.issue}`,
                            "",
                            `Original: "${issue.original}"`,
                            `Fix: "${issue.fix}"`,
                          ].join("\n"),
                        })}
                        className={`rounded-full px-3 py-1 text-3xs font-semibold transition ${isDark ? "bg-white/10 text-slate-200 hover:bg-white/15" : "bg-white text-stone-700 hover:bg-stone-50"}`}
                      >
                        Save note
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {editResult.formatting_notes.length > 0 ? (
            <div>
              <p className={`mb-3 text-3xs font-bold uppercase tracking-[0.28em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>
                Formatting Notes
              </p>
              <div className={`space-y-2 rounded-md border px-5 py-4 ${isDark ? "border-white/[0.08] bg-white/[0.04]" : "border-stone-100 bg-stone-50"}`}>
                {editResult.formatting_notes.map((note, index) => (
                  <div key={index} className="flex items-start gap-2.5">
                    <span className={`mt-0.5 shrink-0 text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>-</span>
                    <div className="flex-1">
                      <p className={`text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{note}</p>
                      <button
                        type="button"
                        onClick={() => onSaveNote({
                          chapterNumber: editChapter ? parseInt(editChapter) : null,
                          title: "Formatting note",
                          body: `Formatting note:\n${note}`,
                        })}
                        className={`mt-2 rounded-full px-3 py-1 text-3xs font-semibold transition ${isDark ? "bg-white/10 text-slate-200 hover:bg-white/15" : "bg-white text-stone-700 hover:bg-stone-50"}`}
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
              <p className={`mb-3 text-3xs font-bold uppercase tracking-[0.28em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                Cross-referenced passages
              </p>
              <div className="grid gap-2 sm:grid-cols-2">
                {editPassages.map((passage, index) => (
                  <div key={index} className={`rounded-md border p-4 ${isDark ? "border-white/[0.08] bg-white/[0.03]" : "border-stone-100 bg-stone-50"}`}>
                    <p className={`mb-1 text-3xs font-bold uppercase tracking-[0.22em] ${isDark ? "text-indigo-300" : "text-violet-600"}`}>
                      Ch. {passage.chapter_num}{passage.chapter_title ? `: ${passage.chapter_title}` : ""}
                    </p>
                    <p className={`text-xs leading-5 line-clamp-3 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{passage.excerpt}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {editResult.continuity_issues.length === 0 && editResult.grammar_issues.length === 0 ? (
            <div className={`rounded-lg border p-6 text-center ${isDark ? "border-teal-500/20 bg-teal-500/8" : "border-teal-200 bg-teal-50"}`}>
              <p className="mb-2 text-sm font-semibold uppercase tracking-[0.24em]">Clear</p>
              <p className={`font-semibold ${isDark ? "text-teal-200" : "text-teal-800"}`}>No continuity or grammar issues found</p>
              <p className={`mt-1 text-xs ${isDark ? "text-teal-400" : "text-teal-600"}`}>The passage is consistent with established story facts.</p>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
})
