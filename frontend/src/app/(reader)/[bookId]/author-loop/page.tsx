"use client"

import dynamic from "next/dynamic"
import Link from "next/link"
import type { Route } from "next"
import { useParams } from "next/navigation"
import { useEffect, useMemo, useRef, useState } from "react"
import type { ReactNode } from "react"
import { useQuery } from "@tanstack/react-query"

import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"
import { RevisionMilestonesPanel, type RevisionComparisonView } from "@/components/author/RevisionMilestonesPanel"
import { betaReadsApi } from "@/lib/api/betaReads"
import { booksApi } from "@/lib/api/books"
import { useBookDetail } from "@/lib/hooks/useBookDetail"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { buildAuthorLoopIssueCards, buildCharacterReviewStats, deadlineFromWindow } from "@/lib/utils/authorLoop"
import { useAuthorLoopActions } from "./authorLoopPage.actions"
import type { BetaReadAssignment, BetaReadAssignmentDetail, BetaReadFeedbackItem } from "@/types/betaRead"
import type { Book, StoryHealth, WriterWorkspace } from "@/types/book"
import type { Character } from "@/types/character"

const UploadModal = dynamic(
  () => import("@/components/modals/UploadModal").then((module) => module.UploadModal),
  { ssr: false, loading: () => <p className="py-5 text-sm text-slate-500">Loading upload tools…</p> },
)

type AuthorLoopStepId = "upload" | "bible" | "continuity" | "issues" | "invite" | "feedback"

const STEPS: Array<{ id: AuthorLoopStepId; label: string; description: string }> = [
  { id: "upload", label: "Manuscript", description: "Confirm the current draft." },
  { id: "bible", label: "Characters", description: "Clean up extracted profiles." },
  { id: "continuity", label: "Continuity", description: "Review manuscript health." },
  { id: "issues", label: "Revision queue", description: "Turn evidence into work." },
  { id: "invite", label: "Invite readers", description: "Choose scope and questions." },
  { id: "feedback", label: "Reader feedback", description: "Triage returned notes." },
]

const STEP_IDS = new Set<AuthorLoopStepId>(STEPS.map((step) => step.id))

function surfaceClass(isDark: boolean) {
  return `border-y py-6 ${isDark ? "border-white/10" : "border-stone-200"}`
}

function mutedClass(isDark: boolean) {
  return isDark ? "text-slate-400" : "text-stone-500"
}

export default function AuthorLoopPage() {
  const { bookId } = useParams<{ bookId: string }>()
  return <AuthorLoopWorkspace key={bookId} bookId={bookId} />
}

function AuthorLoopWorkspace({ bookId }: { bookId: string }) {
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const writerWorkspaceKey = asQueryKey(bookCacheKey(bookId, "writer-workspace"))

  const [activeStep, setActiveStep] = useState<AuthorLoopStepId>("upload")
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [showUploadWorkspace, setShowUploadWorkspace] = useState(false)
  const [readerEmail, setReaderEmail] = useState("")
  const [scopeKind, setScopeKind] = useState("full_book")
  const [chapterStart, setChapterStart] = useState("1")
  const [chapterEnd, setChapterEnd] = useState("3")
  const [deadline, setDeadline] = useState(deadlineFromWindow(7))
  const [authorQuestions, setAuthorQuestions] = useState("Where did you get confused?\nWhich scene stayed with you?\nWhat felt under-explained?")
  const [selectedAssignmentId, setSelectedAssignmentId] = useState<string | null>(null)
  const [stepStorageReady, setStepStorageReady] = useState(false)
  const [stepStorageAvailable, setStepStorageAvailable] = useState(true)
  const [inviteDirty, setInviteDirty] = useState(false)
  const [uploadDirty, setUploadDirty] = useState(false)
  const [snapshotLabel, setSnapshotLabel] = useState("")
  const [snapshotBusy, setSnapshotBusy] = useState(false)
  const [snapshotComparison, setSnapshotComparison] = useState<RevisionComparisonView | null>(null)

  useEffect(() => {
    const storageKey = `lorevia:author-loop:${bookId}:step`
    const hashStep = window.location.hash === "#revision-control"
      ? "issues"
      : window.location.hash === "#beta-consensus"
        ? "feedback"
        : null
    let storedStep: string | null = null
    try { storedStep = window.localStorage.getItem(storageKey) } catch { setStepStorageAvailable(false) }
    if (hashStep) setActiveStep(hashStep)
    else if (storedStep && STEP_IDS.has(storedStep as AuthorLoopStepId)) setActiveStep(storedStep as AuthorLoopStepId)
    setStepStorageReady(true)
  }, [bookId])

  useEffect(() => {
    if (!stepStorageReady) return
    try { window.localStorage.setItem(`lorevia:author-loop:${bookId}:step`, activeStep) } catch { setStepStorageAvailable(false) }
  }, [activeStep, bookId, stepStorageReady])

  const bookQuery = useBookDetail(bookId, {
    refetchInterval: (query) => {
      const currentBook = query.state.data as Book | undefined
      const canPoll = typeof document === "undefined" || document.visibilityState === "visible"
      return canPoll && currentBook && ["queued", "processing", "pending"].includes(currentBook.status) ? 4_000 : false
    },
    refetchIntervalInBackground: false,
  })
  const { data: book = null } = bookQuery
  const characterQuery = useQuery<Character[]>({
    queryKey: asQueryKey(bookCacheKey(bookId, "characters:author-loop")),
    queryFn: () => booksApi.getCharacters<Character>(bookId, { fields: ["id", "name", "first_chapter", "aliases", "description"], include: [] }),
    enabled: activeStep === "bible",
    retry: false,
  })
  const { data: characterData } = characterQuery
  const characters = useMemo(() => Array.isArray(characterData) ? characterData : [], [characterData])
  const healthQuery = useQuery<StoryHealth | null>({
    queryKey: asQueryKey(bookCacheKey(bookId, "story-health")),
    queryFn: () => booksApi.getStoryHealth(bookId),
    enabled: activeStep === "continuity",
    retry: false,
  })
  const { data: storyHealth = null } = healthQuery
  const reportsQuery = useQuery({
    queryKey: asQueryKey(bookCacheKey(bookId, "chapter-reports:12")),
    queryFn: () => booksApi.getChapterReports(bookId, 12),
    enabled: activeStep === "issues",
    retry: false,
  })
  const { data: chapterReports = [] } = reportsQuery
  const revisionQuery = useQuery({
    queryKey: asQueryKey(bookCacheKey(bookId, "revision-intelligence")),
    queryFn: () => booksApi.getRevisionIntelligence(bookId),
    enabled: activeStep === "issues",
    retry: false,
  })
  const { data: revisionIntelligence = null } = revisionQuery
  const workspaceQuery = useQuery<WriterWorkspace | null>({
    queryKey: writerWorkspaceKey,
    queryFn: () => booksApi.getWriterWorkspace(bookId),
    enabled: activeStep === "issues" || activeStep === "feedback",
    retry: false,
    refetchOnWindowFocus: false,
  })
  const { data: writerWorkspace = null } = workspaceQuery
  const assignmentsQuery = useQuery<BetaReadAssignment[]>({
    queryKey: asQueryKey(`author-loop:${bookId}:beta-assignments`),
    queryFn: () => betaReadsApi.listBookAssignments(bookId),
    enabled: activeStep === "invite" || activeStep === "feedback",
    retry: false,
  })
  const { data: assignments = [] } = assignmentsQuery
  const assignmentRemoved = !!selectedAssignmentId && !!assignmentsQuery.data && !assignments.some((assignment) => assignment.id === selectedAssignmentId)
  const activeAssignmentId = !assignmentRemoved && selectedAssignmentId ? selectedAssignmentId : assignments[0]?.id ?? null
  const assignmentQuery = useQuery<BetaReadAssignmentDetail | null>({
    queryKey: activeAssignmentId ? asQueryKey(`author-loop:${bookId}:beta-detail:${activeAssignmentId}`) : ["author-loop:no-assignment"],
    queryFn: () => betaReadsApi.getBookAssignmentDetail(bookId, activeAssignmentId as string),
    enabled: activeStep === "feedback" && Boolean(activeAssignmentId),
    retry: false,
  })
  const { data: selectedAssignment = null } = assignmentQuery

  const issueCards = useMemo(() => buildAuthorLoopIssueCards(revisionIntelligence, chapterReports, writerWorkspace), [chapterReports, revisionIntelligence, writerWorkspace])
  const characterStats = useMemo(() => buildCharacterReviewStats(characters), [characters])
  const activeIndex = STEPS.findIndex((step) => step.id === activeStep)
  const activeStepMeta = STEPS[activeIndex]

  const selectStep = (step: AuthorLoopStepId) => {
    setActiveStep(step)
    window.history.replaceState(window.history.state, "", `${location.pathname}${location.search}${step === "issues" ? "#revision-control" : step === "feedback" ? "#beta-consensus" : ""}`)
    window.scrollTo({ top: 0, behavior: "smooth" })
  }

  const { creatingAssignment, savingIssueId, savingFeedbackId, copyingLink, guestLink, lastDismissedId, taskCreated, busy, handleIssueStatus, handleCreateAssignment, handleCopyGuestLink, handleFeedbackStatus } = useAuthorLoopActions({
    bookId, totalChapters: book?.total_chapters ?? 0, writerWorkspace, issueCards, selectedAssignment,
    draft: { readerEmail, scopeKind, chapterStart, chapterEnd, deadline, authorQuestions }, setReaderEmail: (value) => { setReaderEmail(value); setInviteDirty(false) }, setSelectedAssignmentId, setStatusMessage,
  })
  const leaveGuard = useRef(false)
  leaveGuard.current = busy || inviteDirty || uploadDirty || snapshotBusy || !!snapshotLabel.trim()
  useEffect(() => {
    const unload = (event: BeforeUnloadEvent) => { if (leaveGuard.current) { event.preventDefault(); event.returnValue = "" } }
    const click = (event: MouseEvent) => {
      const link = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>("a[href]") : null
      if (!leaveGuard.current || !link || link.target === "_blank" || link.hasAttribute("download") || event.ctrlKey || event.metaKey || new URL(link.href).pathname === location.pathname) return
      if (!window.confirm("Leave Revision workflow? Unsaved upload drafts, invitation details and snapshot labels may be lost, and any in-progress update may still complete.")) { event.preventDefault(); event.stopPropagation() }
    }
    window.addEventListener("beforeunload", unload); document.addEventListener("click", click, true)
    return () => { window.removeEventListener("beforeunload", unload); document.removeEventListener("click", click, true) }
  }, [])
  const requests = [{ label: "manuscript", query: bookQuery }, ...(activeStep === "bible" ? [{ label: "characters", query: characterQuery }] : []), ...(activeStep === "continuity" ? [{ label: "continuity", query: healthQuery }] : []), ...(activeStep === "issues" ? [{ label: "chapter reports", query: reportsQuery }, { label: "revision findings", query: revisionQuery }, { label: "saved revision decisions", query: workspaceQuery }] : []), ...(["invite", "feedback"].includes(activeStep) ? [{ label: "reader assignments", query: assignmentsQuery }] : []), ...(activeStep === "feedback" && activeAssignmentId ? [{ label: "reader feedback", query: assignmentQuery }, { label: "revision tasks", query: workspaceQuery }] : [])]
  const waiting = requests.some(({ query }) => query.isLoading)
  const unavailable = requests.some(({ label, query }) => query.isError && !query.data && !(activeStep === "feedback" && ["reader feedback", "revision tasks"].includes(label)))
  const savingDecision = busy || snapshotBusy || !writerWorkspace || workspaceQuery.isError
  return (
    <div data-author-loop-workspace className={`min-h-screen ${isDark ? "text-slate-100" : "text-stone-950"}`}>
      <div className="mx-auto max-w-6xl px-4 pb-24 pt-5 sm:px-6 lg:px-8">
        <WorkspaceFamilyHeader active="author-loop" bookId={bookId} family="review-center" title="Revision workflow" description={`Work from ${book?.title ?? "your manuscript"} toward reader-ready revisions, one step at a time.`} actions={<><Link href={`/${bookId}/analysis` as Route} prefetch={false} className="app-button-secondary">Back to findings</Link><button type="button" className="app-button-secondary" onClick={() => window.dispatchEvent(new Event(SUPPORT_HELP_EVENT))}>Help</button></>} />

        <nav aria-label="Revision workflow steps" className={`mt-5 border-y ${isDark ? "border-white/10" : "border-stone-200"}`}>
          <label className={`block px-1 py-3 text-xs font-medium sm:hidden ${mutedClass(isDark)}`}>
            Workflow step
            <select aria-label="Workflow step" value={activeStep} onChange={(event) => selectStep(event.target.value as AuthorLoopStepId)} className={`mt-2 ${inputClass(isDark)}`}>
              {STEPS.map((step, index) => <option key={step.id} value={step.id}>{index + 1}. {step.label}</option>)}
            </select>
          </label>
          <div className="app-scroll hidden max-w-full overflow-x-auto sm:block">
            <ol className="flex min-w-max">
              {STEPS.map((step, index) => <li key={step.id} className={index > 0 ? (isDark ? "border-l border-white/10" : "border-l border-stone-200") : ""}><button type="button" aria-current={activeStep === step.id ? "step" : undefined} onClick={() => selectStep(step.id)} className={`min-w-36 px-4 py-3 text-left transition-colors ${activeStep === step.id ? (isDark ? "bg-white/[0.07] text-white" : "bg-stone-100 text-stone-950") : mutedClass(isDark)}`}><span className="block text-xs tabular-nums">{index + 1} of {STEPS.length}</span><span className="mt-1 block text-sm font-semibold">{step.label}</span></button></li>)}
            </ol>
          </div>
        </nav>

        <div className="mt-7 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between"><div><p className={`text-xs font-medium ${mutedClass(isDark)}`}>Step {activeIndex + 1}</p><p className="mt-1 text-2xl font-semibold tracking-tight">{activeStepMeta.label}</p><p className={`mt-1 text-sm ${mutedClass(isDark)}`}>{activeStepMeta.description}</p></div><p className={`text-xs ${mutedClass(isDark)}`}>{stepStorageAvailable ? "Your current step is saved on this device." : "Device storage is unavailable. Your step will reset when you leave."}</p></div>
        {statusMessage ? (
          <div role="status" className={`fixed bottom-4 left-4 right-4 z-50 max-w-sm rounded-lg border p-4 shadow-xl sm:bottom-6 sm:left-auto sm:right-6 ${isDark ? "border-teal-400/30 bg-[#10231f] text-slate-100" : "border-teal-200 bg-teal-50 text-stone-900"}`}>
            <p className="text-sm">{statusMessage}</p>
            <div className="mt-3 flex items-center justify-between gap-5">
              {taskCreated ? <Link href={`/${bookId}#author-project-tasks` as Route} prefetch={false} className="text-sm font-semibold underline underline-offset-4">View tasks</Link> : <span />}
              <button type="button" onClick={() => setStatusMessage(null)} aria-label="Dismiss notice" className="text-sm font-semibold">Dismiss</button>
            </div>
          </div>
        ) : null}
        {activeStep === "feedback" && assignmentRemoved ? <p className="mt-3 text-sm" role="status">The selected assignment is no longer available. Showing the first available assignment.</p> : null}

        {lastDismissedId ? <button type="button" className="app-button-secondary mt-2" disabled={busy} onClick={() => void handleIssueStatus(lastDismissedId, "pending")}>Undo dismissal</button> : null}
        <div className="mt-4 space-y-3">
          {requests.filter(({ query }) => query.isError).map(({ label, query }) => <div key={label} role="alert"><p>Could not load or refresh {label}. Previously loaded content is retained.</p><button type="button" className="app-button-secondary mt-2" disabled={busy || query.isFetching} onClick={() => void query.refetch()}>Retry {label}</button></div>)}
          <button type="button" className="app-button-secondary" disabled={busy || requests.some(({ query }) => query.isFetching)} onClick={() => void Promise.allSettled(requests.map(({ query }) => query.refetch()))}>Refresh this step</button>
        </div>
        <main className="mt-5">
          {waiting ? <p role="status">Loading {activeStepMeta.label.toLowerCase()}…</p> : null}
          {unavailable && !waiting ? <p>Some step data is unavailable. Use the retry controls above to continue.</p> : null}
          <fieldset disabled={busy} className="min-w-0 border-0 p-0" hidden={waiting || unavailable}>
          <div hidden={activeStep !== "upload"}><UploadStep book={book} bookId={bookId} isDark={isDark} showUploadWorkspace={showUploadWorkspace} setShowUploadWorkspace={setShowUploadWorkspace} onDraftChange={setUploadDirty} /></div>
          {activeStep === "bible" ? <CharacterStep bookId={bookId} characters={characters} stats={characterStats} isDark={isDark} /> : null}
          {activeStep === "continuity" ? <ContinuityStep bookId={bookId} storyHealth={storyHealth} isDark={isDark} /> : null}
          {activeStep === "issues" ? <IssuesStep bookId={bookId} issueCards={issueCards} savingIssueId={savingDecision ? savingIssueId ?? "loading" : null} onStatus={handleIssueStatus} isDark={isDark} /> : null}
          {activeStep === "invite" ? (
            <section className={surfaceClass(isDark)} onChange={() => setInviteDirty(true)}>
              <div className="max-w-2xl"><h2 className="text-lg font-semibold">Invite a beta reader</h2><p className={`mt-1 text-sm leading-6 ${mutedClass(isDark)}`}>Readers receive only the selected chapters and cannot edit the manuscript. Invitations expire at the deadline.</p></div>
              <div className="mt-6 grid max-w-2xl gap-4">
                <InviteField label="Reader email" isDark={isDark}><input type="email" autoComplete="email" maxLength={320} value={readerEmail} onChange={(event) => setReaderEmail(event.target.value)} aria-label="Reader email" className={inputClass(isDark)} /></InviteField>
                <div className="grid gap-4 sm:grid-cols-2"><InviteField label="Scope" isDark={isDark}><select value={scopeKind} onChange={(event) => setScopeKind(event.target.value)} aria-label="Scope" className={inputClass(isDark)}><option value="full_book">Full book</option><option value="chapter_range">Chapter range</option></select></InviteField><InviteField label="Deadline" detail="Choose 3–7 days from today. Access expires that many days after sending." isDark={isDark}><input type="date" min={deadlineFromWindow(3)} max={deadlineFromWindow(7)} value={deadline} onChange={(event) => setDeadline(event.target.value)} aria-label="Deadline" className={inputClass(isDark)} /></InviteField></div>
                {scopeKind !== "full_book" ? <div className="grid gap-4 sm:grid-cols-2"><InviteField label="From chapter" isDark={isDark}><input type="number" min="1" value={chapterStart} onChange={(event) => setChapterStart(event.target.value)} aria-label="From chapter" className={inputClass(isDark)} /></InviteField><InviteField label="Through chapter" isDark={isDark}><input type="number" min="1" value={chapterEnd} onChange={(event) => setChapterEnd(event.target.value)} aria-label="Through chapter" className={inputClass(isDark)} /></InviteField></div> : null}
                <InviteField label="Questions for the reader" detail="Up to 12 questions, 300 characters each; one per line." isDark={isDark}><textarea value={authorQuestions} onChange={(event) => setAuthorQuestions(event.target.value)} rows={5} aria-label="Author prompts" className={`${inputClass(isDark)} h-auto py-3`} /></InviteField>
                <div><button type="button" onClick={() => void handleCreateAssignment()} disabled={creatingAssignment} className="app-button-primary">{creatingAssignment ? "Sending invite…" : "Send beta invite"}</button></div>
              </div>
              {assignments.length ? <p className={`mt-5 text-sm ${mutedClass(isDark)}`}>{assignments.length} existing assignment{assignments.length === 1 ? "" : "s"}. <button type="button" onClick={() => selectStep("feedback")} className={`font-semibold underline underline-offset-4 ${isDark ? "text-teal-300" : "text-teal-800"}`}>Review feedback</button></p> : null}
            </section>
          ) : null}
          {activeStep === "feedback" ? <FeedbackStep bookId={bookId} assignments={assignments} activeAssignmentId={activeAssignmentId} selectedAssignment={selectedAssignment} savingFeedbackId={savingDecision ? savingFeedbackId ?? "loading" : null} isDark={isDark} onSelect={setSelectedAssignmentId} onCopy={handleCopyGuestLink} onStatus={handleFeedbackStatus} onInvite={() => selectStep("invite")} /> : null}
          {activeStep === "feedback" && guestLink?.assignmentId === activeAssignmentId ? <label className="mt-4 block text-sm">Private review link<input className={`${inputClass(isDark)} mt-2`} value={guestLink.url} readOnly onFocus={(event) => event.target.select()} /></label> : null}
          {copyingLink ? <p role="status">Preparing private review link…</p> : null}
          </fieldset>
          {activeStep === "issues" && !waiting && !unavailable ? <RevisionMilestonesPanel bookId={bookId} label={snapshotLabel} onLabelChange={setSnapshotLabel} busy={snapshotBusy || busy} onBusyChange={setSnapshotBusy} comparison={snapshotComparison} onComparisonChange={setSnapshotComparison} /> : null}
        </main>

        <div className={`mt-6 flex items-center justify-between border-t pt-4 ${isDark ? "border-white/10" : "border-stone-200"}`}><button type="button" disabled={activeIndex === 0} onClick={() => selectStep(STEPS[activeIndex - 1].id)} className="app-button-secondary disabled:invisible">Previous</button>{activeIndex < STEPS.length - 1 ? <button type="button" onClick={() => selectStep(STEPS[activeIndex + 1].id)} className="app-button-primary">Next: {STEPS[activeIndex + 1].label}</button> : <Link href={`/${bookId}` as Route} prefetch={false} className="app-button-primary">Return to overview</Link>}</div>
      </div>
    </div>
  )
}

function UploadStep({ book, bookId, isDark, showUploadWorkspace, setShowUploadWorkspace, onDraftChange }: { book: Book | null; bookId: string; isDark: boolean; showUploadWorkspace: boolean; setShowUploadWorkspace: (value: boolean) => void; onDraftChange: (value: boolean) => void }) {
  const [opened, setOpened] = useState(false)
  useEffect(() => { if (showUploadWorkspace) setOpened(true) }, [showUploadWorkspace])
  return <section className={surfaceClass(isDark)}><div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"><div className="max-w-2xl"><h2 className="text-lg font-semibold">Current manuscript</h2><p className={`mt-2 text-sm leading-6 ${mutedClass(isDark)}`}>DOCX, PDF, EPUB, TXT, and Markdown are supported. Replacing the manuscript starts a new processing pass. Review existing sharing settings before replacing content.</p></div><button type="button" onClick={() => setShowUploadWorkspace(!showUploadWorkspace)} className="app-button-primary">{showUploadWorkspace ? "Hide upload tools" : "Open upload tools"}</button></div><dl className={`mt-6 divide-y border-y ${isDark ? "divide-white/10 border-white/10" : "divide-stone-200 border-stone-200"}`}><StatusRow label="Draft" value={book?.title ?? "Loading manuscript…"} isDark={isDark} /><StatusRow label="Processing" value={book?.status === "ready" ? "Ready for review" : `${book?.processing?.stage ?? book?.status ?? "Waiting"}${typeof book?.processing?.progress_pct === "number" ? ` · ${Math.round(book.processing.progress_pct)}%` : ""}`} isDark={isDark} /><StatusRow label="Access" value="Check Visibility for public access; reader invitations are managed separately" isDark={isDark} /></dl>{opened ? <div data-revision-upload className="mt-6" hidden={!showUploadWorkspace}><UploadModal onDraftChange={onDraftChange} onClose={() => setShowUploadWorkspace(false)} initialMode="author" initialExistingBookId={bookId} presentation="inline" /></div> : null}</section>
}

function CharacterStep({ bookId, characters, stats, isDark }: { bookId: string; characters: Character[]; stats: ReturnType<typeof buildCharacterReviewStats>; isDark: boolean }) {
  const [showAll, setShowAll] = useState(false)
  return <section className={surfaceClass(isDark)}><div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div><h2 className="text-lg font-semibold">Character review</h2><p className={`mt-1 text-sm ${mutedClass(isDark)}`}>Correct only the profiles that affect names, aliases, or continuity.</p></div><Link href={`/${bookId}/characters` as Route} prefetch={false} className={`text-sm font-semibold underline underline-offset-4 ${isDark ? "text-teal-300" : "text-teal-800"}`}>Open full character bible</Link></div><div className={`mt-5 flex flex-wrap border-y ${isDark ? "border-white/10" : "border-stone-200"}`}><Metric label="Profiles" value={stats.totalCharacters} isDark={isDark} /><Metric label="Possible duplicates" value={stats.duplicateCount} isDark={isDark} divided /><Metric label="Needs review" value={stats.needsReviewCount} isDark={isDark} divided /></div><div className={`mt-5 divide-y border-y ${isDark ? "divide-white/10 border-white/10" : "divide-stone-200 border-stone-200"}`}>{characters.slice(0, showAll ? characters.length : 6).map((character) => <div key={character.id} className="grid gap-1 py-4 sm:grid-cols-[12rem_minmax(0,1fr)_auto] sm:items-baseline sm:gap-4"><p className="text-sm font-semibold">{character.name}</p><p className={`text-sm leading-6 ${mutedClass(isDark)}`}>{character.description || "No profile summary yet."}</p><span className={`text-xs ${mutedClass(isDark)}`}>{character.aliases.length ? `${character.aliases.length} alias${character.aliases.length === 1 ? "" : "es"}` : "Check aliases"}</span></div>)}{!characters.length ? <p className={`py-5 text-sm ${mutedClass(isDark)}`}>No character profiles are available yet.</p> : null}</div>{characters.length > 6 ? <button type="button" className="app-button-secondary mt-3" onClick={() => setShowAll(!showAll)}>{showAll ? "Show fewer characters" : `Show all ${characters.length} characters`}</button> : null}</section>
}

function ContinuityStep({ bookId, storyHealth, isDark }: { bookId: string; storyHealth: StoryHealth | null; isDark: boolean }) {
  return <section className={surfaceClass(isDark)}><h2 className="text-lg font-semibold">Continuity health</h2><p className={`mt-2 max-w-3xl text-sm leading-7 ${mutedClass(isDark)}`}>{storyHealth?.summary || "Continuity evidence is still being prepared. You can return when manuscript processing is complete."}</p><div className={`mt-6 flex items-baseline gap-3 border-y py-4 ${isDark ? "border-white/10" : "border-stone-200"}`}><span className={`text-sm ${mutedClass(isDark)}`}>Story health</span><strong className="text-2xl tabular-nums">{storyHealth && storyHealth.available !== false ? storyHealth.score : "—"}</strong><span className={`text-xs ${mutedClass(isDark)}`}>Evidence summary, not a quality grade</span></div><div className="mt-5 flex flex-wrap gap-3"><Link href={`/${bookId}/analysis` as Route} prefetch={false} className="app-button-primary">Review findings</Link><Link href={`/${bookId}/analysis?view=chapters` as Route} prefetch={false} className="app-button-secondary">Open chapter reports</Link></div></section>
}

function IssuesStep({ bookId, issueCards, savingIssueId, onStatus, isDark }: { bookId: string; issueCards: ReturnType<typeof buildAuthorLoopIssueCards>; savingIssueId: string | null; onStatus: (id: string, status: "ignored" | "task_created") => Promise<void>; isDark: boolean }) {
  const [showAll, setShowAll] = useState(false)
  return <div id="revision-control" className="space-y-5"><section className={surfaceClass(isDark)}><div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div><h2 className="text-lg font-semibold">Revision queue</h2><p className={`mt-1 text-sm ${mutedClass(isDark)}`}>Review available findings and the latest 12 chapter reports, then create work only for findings you accept.</p></div><span className={`text-sm ${mutedClass(isDark)}`}>{issueCards.length} active finding{issueCards.length === 1 ? "" : "s"}</span></div><div className={`mt-5 divide-y border-y ${isDark ? "divide-white/10 border-white/10" : "divide-stone-200 border-stone-200"}`}>{issueCards.slice(0, showAll ? issueCards.length : 8).map((issue) => <article key={issue.id} className="grid gap-4 py-5 lg:grid-cols-[8rem_minmax(0,1fr)_12rem]"><div className={`text-xs leading-5 ${mutedClass(isDark)}`}><p className="font-semibold capitalize">{issue.severity}</p><p>{issue.citation}</p></div><div><h3 className="text-sm font-semibold">{issue.title}</h3><p className={`mt-1 text-sm leading-6 ${mutedClass(isDark)}`}>{issue.explanation}</p><p className={`mt-2 text-sm ${isDark ? "text-teal-300" : "text-teal-800"}`}>{issue.suggestedFix}</p></div><div className="flex gap-2 lg:flex-col"><button type="button" disabled={!!savingIssueId || issue.status === "task_created"} aria-label={`Create task: ${issue.title}`} onClick={() => void onStatus(issue.id, "task_created")} className="app-button-primary flex-1">{issue.status === "task_created" ? "Task created" : "Convert to task"}</button><button type="button" disabled={!!savingIssueId} aria-label={`Dismiss: ${issue.title}`} onClick={() => void onStatus(issue.id, "ignored")} className="app-button-secondary flex-1">Dismiss</button></div></article>)}{!issueCards.length ? <p className={`py-5 text-sm ${mutedClass(isDark)}`}>No active findings are ready for triage.</p> : null}</div>{issueCards.length > 8 ? <button type="button" className="app-button-secondary mt-3" onClick={() => setShowAll(!showAll)}>{showAll ? "Show fewer findings" : `Show all ${issueCards.length} findings`}</button> : null}<Link href={`/${bookId}/analysis?view=chapters` as Route} className="mt-4 block text-sm underline">Review chapter evidence in Findings</Link></section></div>
}

function FeedbackStep({ bookId, assignments, activeAssignmentId, selectedAssignment, savingFeedbackId, isDark, onSelect, onCopy, onStatus, onInvite }: { bookId: string; assignments: BetaReadAssignment[]; activeAssignmentId: string | null; selectedAssignment: BetaReadAssignmentDetail | null; savingFeedbackId: string | null; isDark: boolean; onSelect: (id: string) => void; onCopy: () => Promise<void>; onStatus: (item: BetaReadFeedbackItem, status: "resolved" | "archived" | "task_created" | "open") => Promise<void>; onInvite: () => void }) {
  return <section id="beta-consensus" className={surfaceClass(isDark)}><div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div><h2 className="text-lg font-semibold">Reader feedback</h2><p className={`mt-1 text-sm ${mutedClass(isDark)}`}>Resolve, archive, or convert only actionable notes into revision tasks.</p></div><Link href={`/${bookId}/beta-feedback` as Route} className={`text-sm font-semibold underline underline-offset-4 ${isDark ? "text-teal-300" : "text-teal-800"}`}>Open full feedback workspace</Link></div>{assignments.length ? <><label className={`mt-6 block max-w-md text-xs font-medium ${mutedClass(isDark)}`}>Reader assignment<select aria-label="Reader assignment" value={activeAssignmentId ?? ""} onChange={(event) => onSelect(event.target.value)} className={`mt-2 ${inputClass(isDark)}`}>{assignments.map((assignment) => <option key={assignment.id} value={assignment.id}>{assignment.reader_email} · {assignment.status_label}</option>)}</select></label>{selectedAssignment ? <><div className={`mt-5 flex flex-wrap border-y ${isDark ? "border-white/10" : "border-stone-200"}`}><Metric label="Notes" value={selectedAssignment.feedback_summary.feedback_item_count} isDark={isDark} /><Metric label="Confusing" value={selectedAssignment.feedback_summary.confusing_count} isDark={isDark} divided /><Metric label="Answers" value={selectedAssignment.feedback_summary.answer_count} isDark={isDark} divided /></div><button type="button" onClick={() => void onCopy()} className={`mt-5 text-sm font-semibold underline underline-offset-4 ${isDark ? "text-teal-300" : "text-teal-800"}`}>Copy private review link</button><div className={`mt-5 divide-y border-y ${isDark ? "divide-white/10 border-white/10" : "divide-stone-200 border-stone-200"}`}>{selectedAssignment.feedback_items.map((item) => <article key={item.id} className="grid gap-4 py-5 lg:grid-cols-[8rem_minmax(0,1fr)_auto]"><div className={`text-xs leading-5 ${mutedClass(isDark)}`}><p className="capitalize">{(item.author_status || "open").replaceAll("_", " ")}</p><p>{item.chapter_number ? `Chapter ${item.chapter_number}` : "Book-wide"}</p></div><div><h3 className="text-sm font-semibold">{item.question_prompt || item.anchor_text || "Reader note"}</h3>{item.body ? <p className={`mt-1 text-sm leading-6 ${mutedClass(isDark)}`}>{item.body}</p> : null}</div><div className="flex flex-wrap gap-2"><button type="button" disabled={!!savingFeedbackId} aria-label={`${item.author_status === "resolved" || item.author_status === "archived" ? "Reopen" : "Resolve"} feedback: ${item.body || item.anchor_text || item.id}`} onClick={() => void onStatus(item, item.author_status === "resolved" || item.author_status === "archived" ? "open" : "resolved")} className="app-button-secondary">{item.author_status === "resolved" || item.author_status === "archived" ? "Reopen" : "Resolve"}</button><button type="button" disabled={!!savingFeedbackId} onClick={() => void onStatus(item, "archived")} className="app-button-secondary">Archive</button><button type="button" disabled={!!savingFeedbackId || item.author_status === "task_created"} onClick={() => void onStatus(item, "task_created")} className="app-button-primary">{item.author_status === "task_created" ? "Task created" : "Convert to task"}</button></div></article>)}{!selectedAssignment.feedback_items.length ? <p className={`py-5 text-sm ${mutedClass(isDark)}`}>This reader has not returned feedback yet.</p> : null}</div></> : null}</> : <div className={`mt-6 border-y py-5 text-sm ${isDark ? "border-white/10 text-slate-400" : "border-stone-200 text-stone-500"}`}>No beta-reader assignments yet. <button type="button" onClick={onInvite} className="font-semibold underline underline-offset-4">Invite a reader</button>.</div>}</section>
}

function StatusRow({ label, value, isDark }: { label: string; value: string; isDark: boolean }) {
  return <div className="grid gap-1 py-3 sm:grid-cols-[9rem_minmax(0,1fr)] sm:gap-4"><dt className={`text-xs font-medium ${mutedClass(isDark)}`}>{label}</dt><dd className="text-sm">{value}</dd></div>
}

function Metric({ label, value, isDark, divided = false }: { label: string; value: number; isDark: boolean; divided?: boolean }) {
  return <div className={`min-w-36 px-4 py-3 first:pl-0 ${divided ? (isDark ? "border-l border-white/10" : "border-l border-stone-200") : ""}`}><p className={`text-xs ${mutedClass(isDark)}`}>{label}</p><p className="mt-1 text-lg font-semibold tabular-nums">{value}</p></div>
}

function inputClass(isDark: boolean) {
  return `h-11 w-full rounded-sm border px-3 text-sm outline-none transition ${isDark ? "border-white/10 bg-[#101720] text-slate-100 focus:border-teal-300" : "border-stone-300 bg-white text-stone-900 focus:border-teal-700"}`
}

function InviteField({ label, detail, isDark, children }: { label: string; detail?: string; isDark: boolean; children: ReactNode }) {
  return <label className="grid gap-2"><span className={`text-xs font-medium ${mutedClass(isDark)}`}>{label}</span>{children}{detail ? <span className={`text-xs ${mutedClass(isDark)}`}>{detail}</span> : null}</label>
}
