"use client"

import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { useParams } from "next/navigation"
import { useCallback, useEffect, useMemo, useState } from "react"

import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { WorkspacePage } from "@/components/ui/Workspace"
import { capture } from "@/lib/analytics/posthog"
import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import { readerApi } from "@/lib/api/reader"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { asQueryKey, bookCacheKey, readerCacheKey } from "@/lib/query/cacheKeys"
import { useAuthStore } from "@/lib/stores/authStore"
import { useAdaptivePolling } from "@/lib/hooks/useAdaptivePolling"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import {
  betaReaderScopeLabel,
  buildBetaReaderFindingNote,
  buildBetaReaderReportNote,
  matchesBetaReaderFilters,
  matchesBetaReaderTermFilters,
} from "@/lib/utils/aiBetaReader"
import { getApiErrorDetail } from "@/lib/utils/apiErrors"
import { saveContextualVaultNote } from "@/lib/utils/notes"
import type { Book } from "@/types/book"
import type { Character } from "@/types/character"
import { EvidenceLinks, FindingCard } from "./reportComponents"
import type {
  BetaReaderAnalysisRequest,
  BetaReaderCheck,
  BetaReaderFinding,
  BetaReaderReport,
  BetaReaderRevisionCandidate,
  BetaReaderScope,
} from "@/types/intelligence"
import type { ChapterListResponse } from "@/types/reader"

type ResultTab = "reader" | "repetition" | "voices" | "revisions"

const CHECK_OPTIONS: Array<{ id: BetaReaderCheck; label: string; detail: string }> = [
  { id: "repetition", label: "Overused language", detail: "Words, phrases, bursts, and dialogue split" },
  { id: "voice", label: "Character voices", detail: "Pairwise distinctness from extracted dialogue" },
  { id: "reader_feedback", label: "Reader feedback", detail: "Strengths, questions, concerns, and priorities" },
]

const TAB_OPTIONS: Array<{ id: ResultTab; label: string }> = [
  { id: "reader", label: "Reader Report" },
  { id: "repetition", label: "Overused Language" },
  { id: "voices", label: "Character Voices" },
  { id: "revisions", label: "Revision Priorities" },
]

export default function AiBetaReaderPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const tier = useAuthStore((state) => state.user?.tier)
  const isDark = theme === "dark"
  const [scope, setScope] = useState<BetaReaderScope>("chapter")
  const [passage, setPassage] = useState("")
  const [chapterNumber, setChapterNumber] = useState<number | null>(null)
  const [chapterStart, setChapterStart] = useState<number | null>(null)
  const [chapterEnd, setChapterEnd] = useState<number | null>(null)
  const [characterIds, setCharacterIds] = useState<string[]>([])
  const [checks, setChecks] = useState<BetaReaderCheck[]>(CHECK_OPTIONS.map((item) => item.id))
  const [activeReport, setActiveReport] = useState<BetaReaderReport | null>(null)
  const [activeTab, setActiveTab] = useState<ResultTab>("reader")
  const [taskId, setTaskId] = useState<string | null>(null)
  const [progress, setProgress] = useState("Ready to read your manuscript.")
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [chapterFilter, setChapterFilter] = useState("all")
  const [characterFilter, setCharacterFilter] = useState("all")
  const [severityFilter, setSeverityFilter] = useState("all")
  const [typeFilter, setTypeFilter] = useState("all")
  const [creatingTaskId, setCreatingTaskId] = useState<string | null>(null)

  const { data: book = null, isLoading: bookLoading } = useQuery<Book | null>({
    queryKey: asQueryKey(bookCacheKey(bookId, "detail")),
    queryFn: () => booksApi.get(bookId),
  })
  const ownerPlanAvailable = book?.access_class !== "owner" || canUseAuthorFeatures(tier)
  const hasScanPermission = Boolean(
    book && (book.access_class === "owner" || book.collaboration_permissions?.can_run_ai_scans),
  )
  const canRun = hasScanPermission && ownerPlanAvailable
  const canCreateTask = Boolean(
    book && (book.access_class === "owner" || book.collaboration_permissions?.can_edit_manuscript),
  )
  const ready = book?.status === "ready"
  const { data: chapterList = null } = useQuery<ChapterListResponse | null>({
    queryKey: asQueryKey(readerCacheKey(bookId, "chapters")),
    queryFn: () => readerApi.getChapterList(bookId),
    enabled: canRun,
  })
  const { data: characters = [] } = useQuery<Pick<Character, "id" | "name">[]>({
    queryKey: asQueryKey(bookCacheKey(bookId, "characters:navigation")),
    queryFn: () =>
      booksApi.getCharacters<Pick<Character, "id" | "name">>(bookId, {
        fields: ["id", "name"],
      }),
    enabled: canRun,
  })
  const {
    data: reportsResponse,
    isLoading: reportsLoading,
    refetch: refetchReports,
  } = useQuery({
    queryKey: asQueryKey(bookCacheKey(bookId, "ai-beta-reader-reports")),
    queryFn: () => intelligenceApi.getBetaReaderReports(bookId),
    enabled: canRun,
  })
  const reports = useMemo(() => reportsResponse?.reports ?? [], [reportsResponse?.reports])
  const chapters = useMemo(() => chapterList?.chapters ?? [], [chapterList?.chapters])

  useEffect(() => {
    const preferred = chapterList?.current_chapter ?? chapters[0]?.number ?? null
    if (chapterNumber === null && preferred !== null) setChapterNumber(preferred)
    if (chapterStart === null && preferred !== null) setChapterStart(preferred)
    if (chapterEnd === null && preferred !== null) setChapterEnd(preferred)
  }, [chapterEnd, chapterList?.current_chapter, chapterNumber, chapterStart, chapters])

  useEffect(() => {
    if (!activeReport && reports[0]) setActiveReport(reports[0])
    if (activeReport) {
      const refreshed = reports.find((report) => report.report_id === activeReport.report_id)
      if (refreshed && refreshed.is_stale !== activeReport.is_stale) setActiveReport(refreshed)
    }
  }, [activeReport, reports])

  const pollBetaReaderJob = useCallback(async ({ signal }: { signal: AbortSignal }) => {
    if (!taskId) throw new Error("Missing beta-reader task")
    const job = await intelligenceApi.getBetaReaderJob(bookId, taskId, signal)
    if (job.status === "complete" && job.report) {
      setActiveReport(job.report)
      setRunning(false)
      setTaskId(null)
      setProgress("Report complete.")
      capture("ai_beta_reader_completed", { book_id: bookId, scope: job.report.scope })
      await refetchReports()
    } else if (job.status === "failed") {
      setRunning(false)
      setTaskId(null)
      setError("The AI Beta Reader could not complete this run. Your manuscript text was not exposed in the error.")
      capture("ai_beta_reader_failed", { book_id: bookId, error_code: job.error })
    } else {
      setProgress(job.progress?.message ?? "Preparing the manuscript analysis...")
    }
    return job
  }, [bookId, refetchReports, taskId])

  const betaReaderPolling = useAdaptivePolling({
    enabled: Boolean(taskId),
    poll: pollBetaReaderJob,
    getProgress: (job) => `${job.status}:${job.progress?.message ?? ""}`,
    isTerminal: (job) => job.status === "complete" || job.status === "failed",
    initialDelayMs: 900,
    maxDelayMs: 8_000,
    timeoutMs: 30 * 60 * 1_000,
    resetKey: taskId,
    onError: (pollError) => {
      setError(getApiErrorDetail(pollError) ?? "Could not resume the AI Beta Reader job.")
      capture("ai_beta_reader_failed", { book_id: bookId, stage: "polling" })
    },
  })

  useEffect(() => {
    if (!betaReaderPolling.timedOut) return
    setRunning(false)
    setTaskId(null)
    setError("The AI Beta Reader job timed out. You can safely try again.")
  }, [betaReaderPolling.timedOut])

  const requestPayload = (): BetaReaderAnalysisRequest => ({
    scope,
    text: scope === "passage" ? passage.trim() : null,
    chapter_number: scope === "chapter" || scope === "passage" ? chapterNumber : null,
    chapter_start: scope === "chapter_range" ? chapterStart : null,
    chapter_end: scope === "chapter_range" ? chapterEnd : null,
    character_ids: characterIds,
    checks,
  })

  const canSubmit = canRun && ready && checks.length > 0 && (
    scope === "passage" ? passage.trim().length > 0
      : scope === "chapter" ? chapterNumber !== null
        : scope === "chapter_range" ? chapterStart !== null && chapterEnd !== null && chapterStart <= chapterEnd
          : chapters.length > 0
  )

  const runAnalysis = async () => {
    if (!canSubmit || running) return
    setRunning(true)
    setError(null)
    setNotice(null)
    setProgress("Preparing the manuscript analysis...")
    capture("ai_beta_reader_run", { book_id: bookId, scope, checks })
    try {
      const response = await intelligenceApi.runBetaReader(bookId, requestPayload())
      if (response.status === "complete" && response.report) {
        setActiveReport(response.report)
        setRunning(false)
        setProgress("Loaded a current cached report.")
        setNotice("This exact manuscript scope was already analyzed, so LoreVia loaded the saved report.")
        capture("ai_beta_reader_completed", { book_id: bookId, scope, cached: true })
        return
      }
      setTaskId(response.task_id)
      setProgress("Queued on the intelligence worker...")
    } catch (runError) {
      setRunning(false)
      setError(getApiErrorDetail(runError) ?? "Could not start the AI Beta Reader.")
      capture("ai_beta_reader_failed", { book_id: bookId, stage: "enqueue" })
    }
  }

  const scopeLabel = activeReport
    ? betaReaderScopeLabel(activeReport.scope, activeReport.coverage.requested_chapters)
    : "Report"

  const saveReport = async () => {
    if (!activeReport) return
    try {
      const saved = await saveContextualVaultNote({
        bookId,
        title: `AI Beta Reader - ${scopeLabel}`,
        content: buildBetaReaderReportNote(activeReport),
        context: "custom",
        explicitFolder: `AI Beta Reader/${scopeLabel}`,
      })
      setNotice(`Saved report to ${saved.path}`)
      capture("ai_beta_reader_save_note", { book_id: bookId, report_id: activeReport.report_id })
    } catch (saveError) {
      setError(getApiErrorDetail(saveError) ?? "Could not save this report to notes.")
    }
  }

  const saveFinding = async (item: BetaReaderFinding | BetaReaderRevisionCandidate) => {
    if (!activeReport) return
    try {
      const saved = await saveContextualVaultNote({
        bookId,
        title: item.title,
        content: buildBetaReaderFindingNote(item),
        context: "custom",
        explicitFolder: `AI Beta Reader/${scopeLabel}`,
      })
      setNotice(`Saved finding to ${saved.path}`)
      capture("ai_beta_reader_save_note", { book_id: bookId, finding_id: item.id })
    } catch (saveError) {
      setError(getApiErrorDetail(saveError) ?? "Could not save this finding to notes.")
    }
  }

  const createTask = async (candidate: BetaReaderRevisionCandidate) => {
    if (!activeReport || !canCreateTask) return
    setCreatingTaskId(candidate.id)
    setError(null)
    try {
      const result = await intelligenceApi.createBetaReaderRevisionTask(
        bookId,
        activeReport.report_id,
        candidate.id,
      )
      setNotice(result.created ? "Revision task created in the revision board." : "That revision task already exists.")
      capture("ai_beta_reader_create_task", {
        book_id: bookId,
        candidate_id: candidate.id,
        created: result.created,
      })
    } catch (taskError) {
      setError(getApiErrorDetail(taskError) ?? "Could not create the revision task.")
    } finally {
      setCreatingTaskId(null)
    }
  }

  const filteredFindings = (activeReport?.findings ?? []).filter((item) => matchesBetaReaderFilters(item, {
    chapter: chapterFilter,
    severity: severityFilter,
    findingType: typeFilter,
  }))
  const filteredCandidates = (activeReport?.revision_candidates ?? []).filter((item) => matchesBetaReaderFilters(item, {
    chapter: chapterFilter,
    severity: severityFilter,
    findingType: typeFilter,
  }))
  const filteredTerms = (activeReport?.overused_terms ?? []).filter((item) => matchesBetaReaderTermFilters(item, {
    chapter: chapterFilter,
    findingType: typeFilter,
  }))
  const filteredVoices = (activeReport?.character_voices ?? []).filter(
    (item) => characterFilter === "all" || item.character_id === characterFilter,
  )

  if (bookLoading) {
    return <div className="min-h-screen px-6 py-20 text-[rgb(var(--muted))]">Loading AI Beta Reader...</div>
  }

  return (
    <WorkspacePage className={isDark ? "text-slate-100" : "text-stone-950"}>
      <div className="mx-auto max-w-7xl px-0 pb-20 pt-6 sm:px-2 lg:px-4">
        <WorkspaceFamilyHeader
          active="analysis"
          bookId={bookId}
          family="review-center"
          title={`${book?.title ?? "Book"} AI Beta Reader`}
          description="An AI-assisted author review for repeated language, character voice separation, and reader-style reactions. Human Beta Feedback remains a separate workspace."
          actions={(
            <>
              <Link href={`/${bookId}/beta-feedback`} className="app-button-secondary">Human Beta Feedback</Link>
              <Link href={`/${bookId}/voice`} className="app-button-secondary">Voice Consistency</Link>
            </>
          )}
        />

        {!canRun ? (
          <section className="app-panel mt-6 p-6" role="status">
            <p className="app-eyebrow">{ownerPlanAvailable ? "Permission required" : "Author plan required"}</p>
            <h2 className="mt-2 text-2xl font-semibold">{ownerPlanAvailable ? "AI scans are not enabled for this workspace access." : "AI Beta Reader is available on the Author plan and trial."}</h2>
            <p className="app-copy mt-3">{ownerPlanAvailable ? "Human beta readers do not receive AI access automatically. Ask the author for an author-workspace collaboration with AI scans enabled." : "Upgrade to Author to run manuscript-wide reader analysis. Your existing human beta feedback remains available."}</p>
            {!ownerPlanAvailable ? <Link href="/upgrade?plan=author" className="app-button-primary mt-4">Upgrade to Author</Link> : null}
          </section>
        ) : (
          <>
            <section className="app-panel mt-6 p-5">
              <div className="grid gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(18rem,0.8fr)]">
                <div>
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" role="radiogroup" aria-label="Analysis scope">
                    {(["passage", "chapter", "chapter_range", "full_book"] as BetaReaderScope[]).map((value) => (
                      <button
                        key={value}
                        type="button"
                        role="radio"
                        aria-checked={scope === value}
                        onClick={() => setScope(value)}
                        className={`rounded-md border px-3 py-3 text-left text-sm font-semibold ${scope === value ? "border-[rgb(var(--accent))] bg-[rgba(var(--accent),0.1)]" : "border-[rgb(var(--border))]"}`}
                      >
                        {value === "passage" ? "Passage" : value === "chapter" ? "Chapter" : value === "chapter_range" ? "Chapter range" : "Full manuscript"}
                      </button>
                    ))}
                  </div>

                  {scope === "passage" ? (
                    <div className="mt-4 grid gap-3 sm:grid-cols-[12rem_minmax(0,1fr)]">
                      <label className="text-sm">Optional chapter context
                        <select value={chapterNumber ?? ""} onChange={(event) => setChapterNumber(event.target.value ? Number(event.target.value) : null)} className="app-input mt-2 w-full">
                          <option value="">No chapter</option>
                          {chapters.map((chapter) => <option key={chapter.number} value={chapter.number}>Chapter {chapter.number}</option>)}
                        </select>
                      </label>
                      <label className="text-sm">Passage (12,000 characters maximum)
                        <textarea value={passage} maxLength={12_000} onChange={(event) => setPassage(event.target.value)} className="app-input mt-2 min-h-40 w-full" aria-label="Passage for AI beta reader" />
                        <span className="mt-1 block text-xs text-[rgb(var(--muted))]">{passage.length.toLocaleString()} / 12,000</span>
                      </label>
                    </div>
                  ) : scope === "chapter" ? (
                    <label className="mt-4 block max-w-sm text-sm">Chapter
                      <select value={chapterNumber ?? ""} onChange={(event) => setChapterNumber(event.target.value ? Number(event.target.value) : null)} className="app-input mt-2 w-full">
                        <option value="">Select chapter</option>
                        {chapters.map((chapter) => <option key={chapter.number} value={chapter.number}>Chapter {chapter.number}{chapter.title ? ` — ${chapter.title}` : ""}</option>)}
                      </select>
                    </label>
                  ) : scope === "chapter_range" ? (
                    <div className="mt-4 grid max-w-xl gap-3 sm:grid-cols-2">
                      <label className="text-sm">First chapter
                        <select value={chapterStart ?? ""} onChange={(event) => setChapterStart(event.target.value ? Number(event.target.value) : null)} className="app-input mt-2 w-full">
                          {chapters.map((chapter) => <option key={chapter.number} value={chapter.number}>Chapter {chapter.number}</option>)}
                        </select>
                      </label>
                      <label className="text-sm">Last chapter
                        <select value={chapterEnd ?? ""} onChange={(event) => setChapterEnd(event.target.value ? Number(event.target.value) : null)} className="app-input mt-2 w-full">
                          {chapters.map((chapter) => <option key={chapter.number} value={chapter.number}>Chapter {chapter.number}</option>)}
                        </select>
                      </label>
                    </div>
                  ) : (
                    <p className="app-copy mt-4">All {chapters.length} extracted chapters will be counted deterministically and read in bounded batches.</p>
                  )}

                  <fieldset className="mt-5">
                    <legend className="app-eyebrow">Checks</legend>
                    <div className="mt-3 grid gap-3 sm:grid-cols-3">
                      {CHECK_OPTIONS.map((option) => (
                        <label key={option.id} className="flex gap-3 rounded-md border border-[rgb(var(--border))] p-3 text-sm">
                          <input
                            type="checkbox"
                            checked={checks.includes(option.id)}
                            onChange={(event) => setChecks((current) => event.target.checked ? [...current, option.id] : current.filter((item) => item !== option.id))}
                          />
                          <span><strong className="block">{option.label}</strong><span className="mt-1 block text-xs text-[rgb(var(--muted))]">{option.detail}</span></span>
                        </label>
                      ))}
                    </div>
                  </fieldset>
                </div>

                <aside className="rounded-md border border-[rgb(var(--border))] bg-[rgba(var(--foreground),0.025)] p-4">
                  <p className="app-eyebrow">Optional voice comparison</p>
                  <div className="mt-3 max-h-48 space-y-2 overflow-y-auto">
                    {characters.length ? characters.map((character) => (
                      <label key={character.id} className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={characterIds.includes(character.id)}
                          onChange={(event) => setCharacterIds((current) => event.target.checked ? [...current, character.id] : current.filter((id) => id !== character.id))}
                        />
                        {character.name}
                      </label>
                    )) : <p className="text-sm text-[rgb(var(--muted))]">No extracted characters are ready yet.</p>}
                  </div>
                  {!ready ? <p className="mt-4 rounded-md bg-amber-500/10 p-3 text-sm text-amber-700" role="status">Manuscript processing must finish before this analysis can run.</p> : null}
                  {checks.length === 0 ? <p className="mt-4 text-sm text-rose-600">Select at least one check.</p> : null}
                  <button type="button" onClick={() => void runAnalysis()} disabled={!canSubmit || running} className="app-button-primary mt-5 w-full">
                    {running ? "Reading..." : activeReport ? "Run again" : "Run AI Beta Reader"}
                  </button>
                  <p className="mt-3 text-sm" aria-live="polite">{progress}</p>
                </aside>
              </div>
              {error ? <p className="mt-4 rounded-md border border-rose-300 bg-rose-500/10 p-3 text-sm text-rose-700" role="alert">{error} <button type="button" onClick={() => void runAnalysis()} className="ml-2 font-semibold underline">Retry</button></p> : null}
              {notice ? <p className="mt-4 rounded-md border border-emerald-300 bg-emerald-500/10 p-3 text-sm text-emerald-700" role="status">{notice}</p> : null}
            </section>

            <section className="mt-6 grid gap-5 xl:grid-cols-[15rem_minmax(0,1fr)]">
              <aside className="app-panel p-4">
                <p className="app-eyebrow">Recent reports</p>
                <div className="mt-3 space-y-2">
                  {reportsLoading ? <p className="text-sm text-[rgb(var(--muted))]">Loading reports...</p> : null}
                  {!reportsLoading && reports.length === 0 ? <p className="text-sm text-[rgb(var(--muted))]">No saved AI reports yet.</p> : null}
                  {reports.map((report) => (
                    <button key={report.report_id} type="button" onClick={() => setActiveReport(report)} className={`w-full rounded-md border p-3 text-left text-sm ${activeReport?.report_id === report.report_id ? "border-[rgb(var(--accent))]" : "border-[rgb(var(--border))]"}`}>
                      <strong className="block">{betaReaderScopeLabel(report.scope, report.coverage.requested_chapters)}</strong>
                      <span className="mt-1 block text-xs text-[rgb(var(--muted))]">{new Date(report.created_at).toLocaleString()}</span>
                      {report.is_stale ? <span className="mt-1 block text-xs font-semibold text-amber-600">Manuscript changed</span> : null}
                    </button>
                  ))}
                </div>
              </aside>

              <div className="app-panel min-w-0 p-5">
                {!activeReport ? (
                  <div className="py-14 text-center">
                    <p className="text-xl font-semibold">Your reader report will appear here.</p>
                    <p className="app-copy mt-2">Choose a scope and run at least one check.</p>
                  </div>
                ) : (
                  <>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="app-eyebrow">{scopeLabel}</p>
                        <h2 className="mt-2 text-2xl font-semibold">AI Beta Reader report</h2>
                        <p className="app-copy mt-2">{activeReport.coverage.word_count.toLocaleString()} words · {activeReport.coverage.analyzed_chapters.length || "Passage"} chapter coverage</p>
                      </div>
                      <button type="button" onClick={() => void saveReport()} className="app-button-secondary">Save report to notes</button>
                    </div>
                    {activeReport.is_stale ? <p className="mt-4 rounded-md border border-amber-300 bg-amber-500/10 p-3 text-sm text-amber-700" role="status">This report is from an earlier manuscript version. It remains available for reference; run again for current results.</p> : null}
                    {activeReport.warnings.length ? <div className="mt-4 rounded-md border border-amber-300 bg-amber-500/10 p-3 text-sm text-amber-700">{activeReport.warnings.map((warning) => <p key={warning}>{warning}</p>)}</div> : null}

                    <div className="mt-5 flex flex-wrap gap-2" role="tablist" aria-label="AI Beta Reader results">
                      {TAB_OPTIONS.map((tab) => <button key={tab.id} type="button" role="tab" aria-selected={activeTab === tab.id} onClick={() => setActiveTab(tab.id)} className={activeTab === tab.id ? "app-button-primary" : "app-button-secondary"}>{tab.label}</button>)}
                    </div>

                    <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                      <label className="text-xs">Chapter<select value={chapterFilter} onChange={(event) => setChapterFilter(event.target.value)} className="app-input mt-1 w-full"><option value="all">All chapters</option>{activeReport.coverage.analyzed_chapters.map((chapter) => <option key={chapter} value={chapter}>Chapter {chapter}</option>)}</select></label>
                      <label className="text-xs">Character<select value={characterFilter} onChange={(event) => setCharacterFilter(event.target.value)} className="app-input mt-1 w-full"><option value="all">All characters</option>{activeReport.character_voices.map((voice) => <option key={voice.character_id} value={voice.character_id}>{voice.character_name}</option>)}</select></label>
                      <label className="text-xs">Severity<select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)} className="app-input mt-1 w-full"><option value="all">All severities</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></label>
                      <label className="text-xs">Finding type<select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)} className="app-input mt-1 w-full"><option value="all">All types</option>{Array.from(new Set([...activeReport.findings.map((item) => item.category), ...activeReport.revision_candidates.map((item) => item.category), ...activeReport.overused_terms.map((item) => item.kind)])).map((type) => <option key={type} value={type}>{type.replaceAll("_", " ")}</option>)}</select></label>
                    </div>

                    {activeTab === "reader" ? (
                      <div className="mt-5 space-y-5">
                        <div className="rounded-md border border-[rgb(var(--border))] p-4"><p className="app-eyebrow">Overall impression</p><p className="mt-3 leading-7">{activeReport.overall_impression}</p></div>
                        {(activeReport.reader_vibe || activeReport.story_understanding) ? (
                          <div className="grid gap-4 lg:grid-cols-2">
                            {activeReport.reader_vibe ? <div className="rounded-md border border-[rgb(var(--border))] p-4"><h3 className="font-semibold">Reader vibe</h3><p className="app-copy mt-3">{activeReport.reader_vibe}</p></div> : null}
                            {activeReport.story_understanding ? <div className="rounded-md border border-[rgb(var(--border))] p-4"><h3 className="font-semibold">Story understanding</h3><p className="app-copy mt-3">{activeReport.story_understanding}</p></div> : null}
                          </div>
                        ) : null}
                        <div className="grid gap-4 lg:grid-cols-2">
                          <div className="rounded-md border border-[rgb(var(--border))] p-4"><h3 className="font-semibold">Strengths</h3>{activeReport.strengths.length ? <ul className="mt-3 list-disc space-y-2 pl-5 text-sm">{activeReport.strengths.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="app-copy mt-3">No model-generated strengths were available for this run.</p>}</div>
                          <div className="rounded-md border border-[rgb(var(--border))] p-4"><h3 className="font-semibold">Reader questions</h3>{activeReport.reader_questions.length ? <ul className="mt-3 list-disc space-y-2 pl-5 text-sm">{activeReport.reader_questions.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="app-copy mt-3">No reader questions were returned.</p>}</div>
                        </div>
                        <div className="rounded-md border border-[rgb(var(--border))] p-4"><h3 className="font-semibold">Prioritized revisions</h3>{activeReport.prioritized_revisions.length ? <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm">{activeReport.prioritized_revisions.map((item) => <li key={item}>{item}</li>)}</ol> : <p className="app-copy mt-3">No prioritized revisions were returned.</p>}</div>
                        {filteredFindings.map((finding) => <FindingCard key={finding.id} bookId={bookId} finding={finding} onSave={() => void saveFinding(finding)} />)}
                      </div>
                    ) : null}

                    {activeTab === "repetition" ? <div className="mt-5 space-y-4">{filteredTerms.length ? filteredTerms.map((term) => <article key={term.id} className="rounded-md border border-[rgb(var(--border))] p-4"><div className="flex flex-wrap justify-between gap-3"><div><h3 className="text-lg font-semibold">“{term.term}”</h3><p className="mt-1 text-sm text-[rgb(var(--muted))]">{term.kind} · {term.rate_per_1000} per 1,000 words{term.burst_detected ? " · local burst" : ""}</p></div><div className="text-right text-sm"><strong className="block text-xl">{term.count}</strong><span>{term.narration_count} narration / {term.dialogue_count} dialogue</span></div></div><EvidenceLinks bookId={bookId} findingId={term.id} evidence={term.evidence} /></article>) : <p className="app-copy">No repeated terms match these filters.</p>}</div> : null}

                    {activeTab === "voices" ? <div className="mt-5 grid gap-4 lg:grid-cols-2">{filteredVoices.length ? filteredVoices.map((voice) => <article key={voice.id} className="rounded-md border border-[rgb(var(--border))] p-4"><div className="flex items-start justify-between gap-3"><h3 className="text-lg font-semibold">{voice.character_name}</h3><span className="rounded-full bg-[rgba(var(--accent),0.12)] px-2 py-1 text-xs font-semibold">{voice.confidence} confidence</span></div>{voice.distinctness_score === null ? <p className="app-copy mt-3">Not enough attributed dialogue for a reliable comparison.</p> : <><p className="mt-4 text-3xl font-semibold">{voice.distinctness_score}% <span className="text-sm font-normal text-[rgb(var(--muted))]">distinct</span></p><p className="app-copy mt-2">Closest to {voice.closest_character_name} ({voice.similarity_score}% similarity).</p><p className="mt-3 text-sm">Shared signals: {voice.shared_signals.join(", ") || "None"}</p>{voice.shared_phrases.length ? <p className="mt-2 text-sm">Shared phrases: {voice.shared_phrases.join(", ")}</p> : null}</>}<p className="mt-3 text-xs text-[rgb(var(--muted))]">{voice.sample_dialogue_count} dialogue samples · {voice.sample_word_count} words</p></article>) : <p className="app-copy">No voice comparisons match this filter.</p>}</div> : null}

                    {activeTab === "revisions" ? <div className="mt-5 space-y-4">{filteredCandidates.length ? filteredCandidates.map((candidate) => <article key={candidate.id} className="rounded-md border border-[rgb(var(--border))] p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="app-eyebrow">{candidate.severity} · {candidate.category.replaceAll("_", " ")}</p><h3 className="mt-2 text-lg font-semibold">{candidate.title}</h3></div><div className="flex gap-2"><button type="button" onClick={() => void saveFinding(candidate)} className="app-button-secondary">Save note</button>{canCreateTask ? <button type="button" disabled={creatingTaskId === candidate.id} onClick={() => void createTask(candidate)} className="app-button-primary">{creatingTaskId === candidate.id ? "Creating..." : "Create revision task"}</button> : null}</div></div><p className="app-copy mt-3">{candidate.description}</p><p className="mt-3 text-sm"><strong>Revision direction:</strong> {candidate.recommendation}</p><EvidenceLinks bookId={bookId} findingId={candidate.id} evidence={candidate.evidence} /></article>) : <p className="app-copy">No revision candidates match these filters.</p>}</div> : null}
                  </>
                )}
              </div>
            </section>
          </>
        )}
      </div>
    </WorkspacePage>
  )
}
