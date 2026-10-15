"use client"

import { useQuery, useQueryClient } from "@tanstack/react-query"
import { isAxiosError } from "axios"
import Link from "next/link"
import { useParams } from "next/navigation"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { WorkspacePage } from "@/components/ui/Workspace"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"
import { capture } from "@/lib/analytics/posthog"
import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import { readerApi } from "@/lib/api/reader"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { useAdaptivePolling } from "@/lib/hooks/useAdaptivePolling"
import { asQueryKey, bookCacheKey, readerCacheKey } from "@/lib/query/cacheKeys"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { betaReaderScopeLabel, buildBetaReaderFindingNote, buildBetaReaderReportNote } from "@/lib/utils/aiBetaReader"
import { getApiErrorDetail } from "@/lib/utils/apiErrors"
import { saveContextualVaultNote } from "@/lib/utils/notes"
import type { Book } from "@/types/book"
import type { Character } from "@/types/character"
import type {
  BetaReaderAnalysisRequest,
  BetaReaderCheck,
  BetaReaderFinding,
  BetaReaderReport,
  BetaReaderRevisionCandidate,
  BetaReaderScope,
} from "@/types/intelligence"
import type { ChapterListResponse } from "@/types/reader"
import { BetaReaderReportView } from "./BetaReaderReportView"

type WorkspaceStep = "configure" | "run" | "review"

const CHECK_OPTIONS: Array<{ id: BetaReaderCheck; label: string; detail: string }> = [
  { id: "repetition", label: "Overused language", detail: "Repeated words, phrases, local bursts, and dialogue split" },
  { id: "voice", label: "Character voices", detail: "Distinctness based on extracted dialogue" },
  { id: "reader_feedback", label: "Reader response", detail: "Strengths, questions, concerns, and revision priorities" },
]

const SCOPE_OPTIONS: Array<{ id: BetaReaderScope; label: string; detail: string }> = [
  { id: "passage", label: "Passage", detail: "Review pasted text with optional chapter context" },
  { id: "chapter", label: "Chapter", detail: "Review one extracted chapter" },
  { id: "chapter_range", label: "Chapter range", detail: "Review a connected section of the manuscript" },
  { id: "full_book", label: "Full manuscript", detail: "Review all extracted chapters; larger manuscripts take longer" },
]

export default function AiBetaReaderPage() {
  const { bookId } = useParams<{ bookId: string }>()
  return <BetaReaderWorkspace key={bookId} bookId={bookId} />
}

function BetaReaderWorkspace({ bookId }: { bookId: string }) {
  const queryClient = useQueryClient()
  const { theme } = usePreferencesStore()
  const tier = useAuthStore((state) => state.user?.tier)
  const isDark = theme === "dark"
  const [workspaceStep, setWorkspaceStep] = useState<WorkspaceStep>("review")
  const [scope, setScope] = useState<BetaReaderScope>("chapter")
  const [passage, setPassage] = useState("")
  const [chapterNumber, setChapterNumber] = useState<number | null>(null)
  const [chapterStart, setChapterStart] = useState<number | null>(null)
  const [chapterEnd, setChapterEnd] = useState<number | null>(null)
  const [characterIds, setCharacterIds] = useState<string[]>([])
  const [checks, setChecks] = useState<BetaReaderCheck[]>(CHECK_OPTIONS.map((item) => item.id))
  const [activeReport, setActiveReport] = useState<BetaReaderReport | null>(null)
  const [taskId, setTaskId] = useState<string | null>(null)
  const [progress, setProgress] = useState("Ready to read your manuscript.")
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const workspaceRoot = useRef<HTMLElement | null>(null)
  const previousStep = useRef<WorkspaceStep>("review")
  const [jobMemoryAvailable, setJobMemoryAvailable] = useState(true)
  const defaultChapterSet = useRef(false)
  const [jobMemoryReady, setJobMemoryReady] = useState(false)
  const [savingNote, setSavingNote] = useState(false)
  const savingNoteRef = useRef(false)
  const taskRequestRef = useRef(false)
  const runRequestRef = useRef(false)
  const [creatingTaskId, setCreatingTaskId] = useState<string | null>(null)

  const bookQuery = useQuery<Book | null>({
    queryKey: asQueryKey(bookCacheKey(bookId, "detail")),
    queryFn: () => booksApi.get(bookId),
  })
  const book = bookQuery.data
  const bookLoading = bookQuery.isLoading
  const ownerPlanAvailable = book?.access_class !== "owner" || canUseAuthorFeatures(tier)
  const hasScanPermission = Boolean(book && (book.access_class === "owner" || book.collaboration_permissions?.can_run_ai_scans))
  const canRun = hasScanPermission && ownerPlanAvailable
  const canCreateTask = Boolean(book && (book.access_class === "owner" || book.collaboration_permissions?.can_edit_manuscript))
  const ready = book?.status === "ready"
  const configurationOpen = workspaceStep === "configure"
  const chapterQuery = useQuery<ChapterListResponse | null>({
    queryKey: asQueryKey(readerCacheKey(bookId, "chapters")),
    queryFn: () => readerApi.getChapterList(bookId),
    enabled: canRun && configurationOpen,
  })
  const chapterList = chapterQuery.data
  const characterQuery = useQuery<Pick<Character, "id" | "name">[]>({
    queryKey: asQueryKey(bookCacheKey(bookId, "characters:navigation")),
    queryFn: () => booksApi.getCharacters<Pick<Character, "id" | "name">>(bookId, { fields: ["id", "name"] }),
    enabled: canRun && configurationOpen,
  })
  const characters = characterQuery.data ?? []
  const reportsQuery = useQuery({
    queryKey: asQueryKey(bookCacheKey(bookId, "ai-beta-reader-reports")),
    queryFn: () => intelligenceApi.getBetaReaderReports(bookId),
    enabled: canRun,
  })
  const { data: reportsResponse, isLoading: reportsLoading, refetch: refetchReports } = reportsQuery
  const reports = useMemo(() => reportsResponse?.reports ?? [], [reportsResponse?.reports])
  const chapters = useMemo(() => chapterList?.chapters ?? [], [chapterList?.chapters])

  const rememberReport = useCallback((report: BetaReaderReport) => {
    queryClient.setQueryData<{ reports: BetaReaderReport[] }>(asQueryKey(bookCacheKey(bookId, "ai-beta-reader-reports")), (current) => ({
      reports: [report, ...(current?.reports ?? []).filter((item) => item.report_id !== report.report_id)],
    }))
    setActiveReport(report)
  }, [bookId, queryClient])

  useEffect(() => {
    if (defaultChapterSet.current || !chapters.length) return
    defaultChapterSet.current = true
    const preferred = chapters.some((chapter) => chapter.number === chapterList?.current_chapter) ? chapterList!.current_chapter! : chapters[0].number
    if (scope !== "passage") setChapterNumber(preferred)
    setChapterStart(preferred)
    setChapterEnd(preferred)
  }, [chapterList, chapters, scope])

  useEffect(() => {
    try {
      const saved = JSON.parse(sessionStorage.getItem(`lorevia:beta-reader-job:${bookId}`) ?? "null")
      if (saved && typeof saved.taskId === "string" && saved.taskId && SCOPE_OPTIONS.some((option) => option.id === saved.scope)) {
        setTaskId(saved.taskId)
        setScope(saved.scope)
        setRunning(true)
        setWorkspaceStep("run")
        setProgress("Reconnecting to your reader pass…")
      }
    } catch { setJobMemoryAvailable(false) }
    setJobMemoryReady(true)
  }, [bookId])

  useEffect(() => {
    if (!jobMemoryReady) return
    try {
      const key = `lorevia:beta-reader-job:${bookId}`
      if (taskId) sessionStorage.setItem(key, JSON.stringify({ taskId, scope }))
      else sessionStorage.removeItem(key)
    } catch { setJobMemoryAvailable(false) }
  }, [bookId, jobMemoryReady, scope, taskId])

  useEffect(() => {
    if (!activeReport && reports[0]) setActiveReport(reports[0])
    if (activeReport) {
      const refreshed = reports.find((report) => report.report_id === activeReport.report_id)
      if (refreshed && refreshed !== activeReport) setActiveReport(refreshed)
    }
  }, [activeReport, reports])

  const pollBetaReaderJob = useCallback(async ({ signal }: { signal: AbortSignal }) => {
    if (!taskId) throw new Error("Missing beta-reader task")
    const job = await intelligenceApi.getBetaReaderJob(bookId, taskId, signal)
    if (signal.aborted) return job
    setError(null)
    if (job.status === "complete" && job.report) {
      rememberReport(job.report)
      setRunning(false)
      setTaskId(null)
      setProgress("Report complete.")
      setWorkspaceStep("review")
      capture("ai_beta_reader_completed", { book_id: bookId, scope: job.report.scope })
      await refetchReports()
    } else if (job.status === "complete") {
      setRunning(false)
      setTaskId(null)
      setWorkspaceStep("review")
      setError("The reader pass finished without returning a report. Refresh the saved reports before trying another run.")
      await refetchReports()
    } else if (job.status === "failed") {
      setRunning(false)
      setTaskId(null)
      setWorkspaceStep("configure")
      setError("The reader pass could not finish. Your saved reports remain available. Try again with the same scope or a smaller passage.")
      capture("ai_beta_reader_failed", { book_id: bookId, error_code: job.error })
    } else {
      setProgress(job.progress?.message ?? "Preparing the manuscript analysis...")
    }
    return job
  }, [bookId, refetchReports, rememberReport, taskId])

  const betaReaderPolling = useAdaptivePolling({
    enabled: Boolean(taskId) && canRun,
    poll: pollBetaReaderJob,
    getProgress: (job) => `${job.status}:${job.progress?.message ?? ""}`,
    isTerminal: (job) => job.status === "complete" || job.status === "failed",
    initialDelayMs: 900,
    maxDelayMs: 8_000,
    timeoutMs: 30 * 60 * 1_000,
    resetKey: taskId,
    onError: (pollError) => {
      if (isAxiosError(pollError) && pollError.response?.status === 404) {
        setRunning(false)
        setTaskId(null)
        setWorkspaceStep("review")
        setError("This reader pass could no longer be found. Check saved reports before starting another run.")
        return
      }
      setError(getApiErrorDetail(pollError) ?? "Could not check progress. Your reader pass may still be running. Reconnecting automatically; you can also check again now.")
      capture("ai_beta_reader_failed", { book_id: bookId, stage: "polling" })
    },
  })

  useEffect(() => {
    if (!betaReaderPolling.timedOut) return
    setError("Progress checks have paused after 30 minutes. The reader pass may still be running. Check again before starting another pass.")
  }, [betaReaderPolling.timedOut])

  useEffect(() => {
    if (previousStep.current === workspaceStep) return
    previousStep.current = workspaceStep
    workspaceRoot.current?.querySelector<HTMLElement>("[data-beta-step-heading]")?.focus()
  }, [workspaceStep])

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
    scope === "passage" ? passage.trim().length > 0 && passage.trim().length <= 12_000
      : scope === "chapter" ? chapters.some((chapter) => chapter.number === chapterNumber)
        : scope === "chapter_range" ? chapterStart !== null && chapterEnd !== null && chapterStart <= chapterEnd && chapters.some((chapter) => chapter.number === chapterStart) && chapters.some((chapter) => chapter.number === chapterEnd)
          : chapters.length > 0
  )

  const runAnalysis = async () => {
    if (!canSubmit || running || runRequestRef.current) return
    runRequestRef.current = true
    setRunning(true)
    setWorkspaceStep("run")
    setError(null)
    setNotice(null)
    setProgress("Preparing the manuscript analysis...")
    capture("ai_beta_reader_run", { book_id: bookId, scope, checks })
    try {
      const response = await intelligenceApi.runBetaReader(bookId, requestPayload())
      if (response.status === "complete" && response.report) {
        rememberReport(response.report)
        setRunning(false)
        setProgress("Loaded a current saved report.")
        setNotice("This exact manuscript scope was already analyzed, so LoreVia loaded the saved report.")
        setWorkspaceStep("review")
        capture("ai_beta_reader_completed", { book_id: bookId, scope, cached: true })
        return
      }
      if (!response.task_id) throw new Error("No reader pass identifier returned")
      setTaskId(response.task_id)
      setProgress("Reader pass queued. Waiting for analysis to start…")
    } catch (runError) {
      setRunning(false)
      setWorkspaceStep("configure")
      setError(getApiErrorDetail(runError) ?? "Could not start the AI Beta Reader.")
      capture("ai_beta_reader_failed", { book_id: bookId, stage: "enqueue" })
    } finally {
      runRequestRef.current = false
    }
  }

  const scopeLabel = activeReport ? betaReaderScopeLabel(activeReport.scope, activeReport.coverage.requested_chapters) : "Report"
  const saveReport = async () => {
    if (!activeReport || savingNoteRef.current) return
    savingNoteRef.current = true
    setSavingNote(true)
    setError(null)
    setNotice(null)
    try {
      const saved = await saveContextualVaultNote({ bookId, title: `AI Beta Reader - ${scopeLabel}`, content: buildBetaReaderReportNote(activeReport), context: "custom", explicitFolder: `AI Beta Reader/${scopeLabel}` })
      setNotice(`Saved report to ${saved.path}`)
      capture("ai_beta_reader_save_note", { book_id: bookId, report_id: activeReport.report_id })
    } catch (saveError) {
      setError(getApiErrorDetail(saveError) ?? "Could not save this report to notes.")
    } finally {
      savingNoteRef.current = false
      setSavingNote(false)
    }
  }
  const saveFinding = async (item: BetaReaderFinding | BetaReaderRevisionCandidate) => {
    if (!activeReport || savingNoteRef.current) return
    savingNoteRef.current = true
    setSavingNote(true)
    setError(null)
    setNotice(null)
    try {
      const saved = await saveContextualVaultNote({ bookId, title: item.title, content: buildBetaReaderFindingNote(item), context: "custom", explicitFolder: `AI Beta Reader/${scopeLabel}` })
      setNotice(`Saved finding to ${saved.path}`)
      capture("ai_beta_reader_save_note", { book_id: bookId, finding_id: item.id })
    } catch (saveError) {
      setError(getApiErrorDetail(saveError) ?? "Could not save this finding to notes.")
    } finally {
      savingNoteRef.current = false
      setSavingNote(false)
    }
  }
  const createTask = async (candidate: BetaReaderRevisionCandidate) => {
    if (!activeReport || !canCreateTask || taskRequestRef.current) return
    taskRequestRef.current = true
    setNotice(null)
    setCreatingTaskId(candidate.id)
    setError(null)
    try {
      const result = await intelligenceApi.createBetaReaderRevisionTask(bookId, activeReport.report_id, candidate.id)
      setNotice(result.created ? "Revision task created in the revision board." : "That revision task already exists.")
      capture("ai_beta_reader_create_task", { book_id: bookId, candidate_id: candidate.id, created: result.created })
    } catch (taskError) {
      setError(getApiErrorDetail(taskError) ?? "Could not create the revision task.")
    } finally {
      taskRequestRef.current = false
      setCreatingTaskId(null)
    }
  }


  return (
    <WorkspacePage className={isDark ? "text-slate-100" : "text-stone-950"}>
      <main ref={workspaceRoot} data-beta-reader-workspace className="mx-auto min-w-0 max-w-7xl px-0 pb-20 pt-6 sm:px-2 lg:px-4 [overflow-wrap:anywhere]">
        <WorkspaceFamilyHeader
          active="ai-beta-reader"
          bookId={bookId}
          family="review-center"
          title={`${book?.title ?? "Book"} AI Beta Reader`}
          description="Run a structured reader pass for repetition, character voice, and revision priorities. Human beta feedback stays separate."
          actions={<><Link href={`/${bookId}/beta-feedback`} className="app-button-secondary">Human Beta Feedback</Link><Link href={`/${bookId}/voice`} className="app-button-secondary">Voice Consistency</Link><button type="button" className="app-button-secondary" onClick={() => window.dispatchEvent(new CustomEvent(SUPPORT_HELP_EVENT))}>Help</button></>}
        />

        {bookLoading ? <p role="status" className="py-12 text-sm">Loading manuscript access…</p> : bookQuery.isError ? <div role="alert" className="mt-6 border-l-2 border-rose-500 pl-3 text-sm">Could not load manuscript access. <button type="button" className="app-button-secondary" onClick={() => void bookQuery.refetch()}>Retry manuscript</button></div> : !canRun ? (
          <section className="mt-6 border-y border-[rgb(var(--border))] py-6" role="status">
            <p className="text-sm font-medium text-[rgb(var(--muted-foreground))]">{ownerPlanAvailable ? "Permission required" : "Author plan required"}</p>
            <h2 className="mt-2 text-2xl font-semibold">{ownerPlanAvailable ? "AI scans are not enabled for this workspace access." : "AI Beta Reader is available on the Author plan and trial."}</h2>
            <p className="app-copy mt-3">{ownerPlanAvailable ? "Human beta readers do not receive AI access automatically. Ask the author for an author-workspace collaboration with AI scans enabled." : "Upgrade to Author to run manuscript-wide reader analysis. Your existing human beta feedback remains available."}</p>
            {!ownerPlanAvailable ? <Link href="/upgrade?plan=author" className="app-button-primary mt-4">Upgrade to Author</Link> : null}
          </section>
        ) : (
          <section className="mt-6 min-w-0">
            <ol className="grid grid-cols-3 border-y border-[rgb(var(--border))]" aria-label="AI Beta Reader workflow">
              {(["configure", "run", "review"] as WorkspaceStep[]).map((step, index) => (
                <li key={step} className={`flex items-center gap-2 px-2 py-3 sm:px-5 ${index > 0 ? "border-l border-[rgb(var(--border))]" : ""}`} aria-current={workspaceStep === step ? "step" : undefined}>
                  <span className={`text-sm font-semibold ${workspaceStep === step ? "text-[rgb(var(--accent))]" : "text-[rgb(var(--muted-foreground))]"}`}>{index + 1}</span>
                  <div><p className="font-semibold capitalize">{step}</p><p className="hidden text-sm text-[rgb(var(--muted-foreground))] sm:block">{step === "configure" ? "Choose scope and checks" : step === "run" ? "Process the selected text" : "Read and act on evidence"}</p></div>
                </li>
              ))}
            </ol>

            {error ? <p className="mx-5 mt-5 border-l-2 border-rose-500 py-1 pl-3 text-sm text-[rgb(var(--foreground))]" role="alert">{error}</p> : null}
            {notice ? <p className="mx-5 mt-5 border-l-2 border-emerald-500 py-1 pl-3 text-sm text-[rgb(var(--foreground))]" role="status">{notice}</p> : null}

            {workspaceStep === "configure" ? (
              <div className="mx-auto max-w-4xl p-5 sm:p-7">
                <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[rgb(var(--border))] pb-5">
                  <div><h2 data-beta-step-heading tabIndex={-1} className="text-2xl font-semibold">Configure a reader pass</h2><p className="app-copy mt-2">Start with the smallest manuscript scope that can answer your revision question.</p></div>
                  {activeReport ? <button type="button" onClick={() => setWorkspaceStep("review")} className="text-sm font-semibold text-[rgb(var(--accent))] hover:underline">Return to current report</button> : null}
                </div>

                <fieldset className="py-6">
                  <legend className="font-semibold">Manuscript scope</legend>
                  <div className="mt-3 divide-y divide-[rgb(var(--border))] border-y border-[rgb(var(--border))]">
                    {SCOPE_OPTIONS.map((option) => <label key={option.id} className="flex cursor-pointer items-start gap-3 py-3"><input type="radio" name="beta-reader-scope" value={option.id} checked={scope === option.id} onChange={() => setScope(option.id)} className="mt-1" /><span><strong className="block text-sm">{option.label}</strong><span className="mt-0.5 block text-sm text-[rgb(var(--muted-foreground))]">{option.detail}</span></span></label>)}
                  </div>
                </fieldset>

                {chapterQuery.isLoading ? <p role="status" className="py-3 text-sm">Loading chapters…</p> : chapterQuery.isError ? <p role="alert" className="py-3 text-sm">Could not load chapters. <button type="button" className="app-button-secondary" onClick={() => void chapterQuery.refetch()}>Retry chapters</button></p> : !chapters.length ? <p className="py-3 text-sm">No extracted chapters are available. You can review a pasted passage or <Link className="underline" href={`/${bookId}/chapters`}>open Chapters</Link>.</p> : null}
                <div className="border-b border-[rgb(var(--border))] pb-6">
                  {scope === "passage" ? (
                    <div className="grid gap-4 sm:grid-cols-[12rem_minmax(0,1fr)]"><label className="text-sm">Chapter context<select value={chapterNumber ?? ""} onChange={(event) => setChapterNumber(event.target.value ? Number(event.target.value) : null)} className="app-input mt-2 w-full"><option value="">No chapter</option>{chapters.map((chapter) => <option key={chapter.number} value={chapter.number}>Chapter {chapter.number}</option>)}</select></label><label className="text-sm">Passage<textarea value={passage} aria-invalid={passage.trim().length > 12_000} aria-describedby="beta-passage-limit" onChange={(event) => setPassage(event.target.value)} className="app-input mt-2 min-h-40 w-full" aria-label="Passage for AI beta reader" /><span id="beta-passage-limit" className="mt-1 block text-sm text-[rgb(var(--muted-foreground))]">{passage.trim().length.toLocaleString()} / 12,000 characters{passage.trim().length > 12_000 ? ". Shorten this passage before running the review." : ""}</span></label></div>
                  ) : scope === "chapter" ? (
                    <label className="block max-w-sm text-sm">Chapter<select value={chapterNumber ?? ""} onChange={(event) => setChapterNumber(event.target.value ? Number(event.target.value) : null)} className="app-input mt-2 w-full"><option value="">Select chapter</option>{chapters.map((chapter) => <option key={chapter.number} value={chapter.number}>Chapter {chapter.number}{chapter.title ? ` — ${chapter.title}` : ""}</option>)}</select></label>
                  ) : scope === "chapter_range" ? (
                    <div className="grid max-w-xl gap-4 sm:grid-cols-2"><label className="text-sm">First chapter<select value={chapterStart ?? ""} onChange={(event) => setChapterStart(event.target.value ? Number(event.target.value) : null)} className="app-input mt-2 w-full">{chapters.map((chapter) => <option key={chapter.number} value={chapter.number}>Chapter {chapter.number}</option>)}</select></label><label className="text-sm">Last chapter<select value={chapterEnd ?? ""} onChange={(event) => setChapterEnd(event.target.value ? Number(event.target.value) : null)} className="app-input mt-2 w-full">{chapters.map((chapter) => <option key={chapter.number} value={chapter.number}>Chapter {chapter.number}</option>)}</select></label></div>
                  ) : <p className="app-copy">Review all {chapters.length} extracted chapters. Larger manuscripts may take longer to process.</p>}
                </div>

                {scope === "chapter_range" && chapterStart !== null && chapterEnd !== null && chapterStart > chapterEnd ? <p role="alert" className="mt-3 text-sm">The last chapter must come after, or be the same as, the first chapter.</p> : null}

                <fieldset className="py-6">
                  <legend className="font-semibold">Checks to include</legend>
                  <div className="mt-3 divide-y divide-[rgb(var(--border))] border-y border-[rgb(var(--border))]">
                    {CHECK_OPTIONS.map((option) => <label key={option.id} className="flex cursor-pointer items-start gap-3 py-3"><input type="checkbox" checked={checks.includes(option.id)} onChange={(event) => setChecks((current) => event.target.checked ? [...current, option.id] : current.filter((item) => item !== option.id))} className="mt-1" /><span><strong className="block text-sm">{option.label}</strong><span className="mt-0.5 block text-sm text-[rgb(var(--muted-foreground))]">{option.detail}</span></span></label>)}
                  </div>
                </fieldset>

                <details className="border-y border-[rgb(var(--border))] py-4"><summary className="cursor-pointer text-sm font-semibold">Limit voice comparison to selected characters</summary><div className="mt-4 grid gap-2 sm:grid-cols-2">{characterQuery.isLoading ? <p role="status">Loading characters…</p> : characterQuery.isError ? <p role="alert">Could not load characters. <button type="button" className="app-button-secondary" onClick={() => void characterQuery.refetch()}>Retry characters</button></p> : characters.length ? characters.map((character) => <label key={character.id} className="flex items-center gap-2 py-2 text-sm"><input type="checkbox" checked={characterIds.includes(character.id)} disabled={!characterIds.includes(character.id) && characterIds.length >= 20} onChange={(event) => setCharacterIds((current) => event.target.checked ? [...current, character.id] : current.filter((id) => id !== character.id))} />{character.name}</label>) : <p className="text-sm text-[rgb(var(--muted-foreground))]">No extracted characters are ready yet.</p>}</div><p className="mt-3 text-sm text-[rgb(var(--muted-foreground))]">{characterIds.length} of 20 selected. Leave all unchecked to compare all available voices.</p></details>

                {!ready ? <p className="mt-5 border-l-2 border-amber-500 py-1 pl-3 text-sm text-[rgb(var(--muted-foreground))]" role="status">Manuscript processing must finish before this analysis can run.</p> : null}
                {checks.length === 0 ? <p className="mt-5 text-sm text-[rgb(var(--foreground))]">Select at least one check.</p> : null}
                <div className="mt-6 flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-[rgb(var(--muted-foreground))]">The report is saved automatically when the run completes.</p><button type="button" onClick={() => void runAnalysis()} disabled={!canSubmit || running} className="app-button-primary">Run reader pass</button></div>
              </div>
            ) : null}

            {workspaceStep === "run" ? (
              <div className="mx-auto max-w-2xl px-5 py-20 text-center" aria-live="polite"><p className="text-sm font-medium text-[rgb(var(--accent))]">Reader pass in progress</p><h2 data-beta-step-heading tabIndex={-1} className="mt-2 text-2xl font-semibold">Reviewing {scope === "full_book" ? "the full manuscript" : scope.replaceAll("_", " ")}</h2><p className="app-copy mt-3">{progress}</p><p className="mt-6 text-sm text-[rgb(var(--muted-foreground))]">Your report will be saved automatically. {jobMemoryAvailable ? "Progress resumes in this tab after a refresh." : "Keep this tab open to follow progress."} This screen will move to Review when the report is ready.</p>{taskId ? <button type="button" onClick={() => betaReaderPolling.refresh()} disabled={betaReaderPolling.isPolling} className="app-button-secondary mt-5">Check progress now</button> : null}</div>
            ) : null}

            {workspaceStep === "review" ? (
              <div className="grid min-h-[32rem] lg:grid-cols-[15rem_minmax(0,1fr)]">
                <aside className="border-b border-[rgb(var(--border))] p-5 lg:border-b-0 lg:border-r"><div className="flex items-center justify-between gap-3"><h2 className="font-semibold">Saved reports</h2><button type="button" onClick={() => setWorkspaceStep("configure")} className="text-sm font-semibold text-[rgb(var(--accent))] hover:underline">New run</button></div><div className="mt-3 divide-y divide-[rgb(var(--border))] border-y border-[rgb(var(--border))]">{reportsQuery.isError ? <p role="alert" className="py-3 text-sm">Could not load saved reports. <button type="button" className="app-button-secondary mt-2" onClick={() => void refetchReports()}>Retry saved reports</button></p> : null}{reportsLoading ? <p className="py-3 text-sm text-[rgb(var(--muted-foreground))]">Loading reports...</p> : null}{!reportsLoading && !reportsQuery.isError && reports.length === 0 ? <p className="py-3 text-sm text-[rgb(var(--muted-foreground))]">No saved reports yet.</p> : null}{reports.map((report) => <button key={report.report_id} type="button" onClick={() => setActiveReport(report)} aria-pressed={activeReport?.report_id === report.report_id} className={`w-full py-3 text-left text-sm ${activeReport?.report_id === report.report_id ? "text-[rgb(var(--foreground))]" : "text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))]"}`}><strong className="block">{betaReaderScopeLabel(report.scope, report.coverage.requested_chapters)}</strong><span className="mt-1 block text-sm">{new Date(report.created_at).toLocaleString()}</span>{report.is_stale ? <span className="mt-1 block text-sm text-[rgb(var(--muted-foreground))]">Earlier manuscript version</span> : null}</button>)}</div></aside>
                <div className="min-w-0 p-5 sm:p-7">{!activeReport && (reportsLoading || reportsQuery.isError) ? <p role="status" className="py-16 text-sm">{reportsLoading ? "Loading saved reports…" : "Retry the report list or start a new run."}</p> : !activeReport ? <div className="py-16 text-center"><h2 className="text-xl font-semibold">No reader report yet</h2><p className="app-copy mt-2">Configure a run to review reader response, repetition, voice, and revision evidence.</p><button type="button" onClick={() => setWorkspaceStep("configure")} className="app-button-primary mt-5">Configure first run</button></div> : <BetaReaderReportView key={activeReport.report_id} bookId={bookId} report={activeReport} canCreateTask={canCreateTask} creatingTaskId={creatingTaskId} savingNote={savingNote} onSaveReport={() => void saveReport()} onSaveFinding={(item) => void saveFinding(item)} onCreateTask={(candidate) => void createTask(candidate)} />}</div>
              </div>
            ) : null}
          </section>
        )}
      </main>
    </WorkspacePage>
  )
}
