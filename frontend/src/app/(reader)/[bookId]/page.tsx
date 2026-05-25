"use client"

import { startTransition, useEffect, useMemo, useRef, useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import dynamic from "next/dynamic"
import type { Route } from "next"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"

import { capture } from "@/lib/analytics/posthog"
import { booksApi } from "@/lib/api/books"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { asQueryKey, bookCacheKey, booksQuotesCacheKey, readerCacheKey } from "@/lib/query/cacheKeys"
import { useAuthStore } from "@/lib/stores/authStore"
import { useBookModeStore } from "@/lib/stores/bookModeStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { resolveAssetUrl } from "@/lib/utils/assetUrls"
import { buildIssueDisplay } from "@/lib/utils/storyFeedback"
import type { Book, BookNote, BookOverviewPayload, ChapterConsistencyReport, GoalCalendarItem, PreWritingCheck, RevisionIntelligence, SavedQuote, StoryHealth, WriterWorkspace } from "@/types/book"
import type { Character } from "@/types/character"
import type { ChapterListResponse, ReadingProgress, SummaryCollectionResponse } from "@/types/reader"

const AuthorWorkspaceDashboard = dynamic(
  () => import("@/components/reader/AuthorWorkspaceDashboard").then((module) => module.AuthorWorkspaceDashboard),
  {
    loading: () => <WorkspacePanelLoadingState />,
  }
)

const AuthorToolsNav = dynamic(
  () => import("@/components/layout/AuthorToolsNav").then((module) => module.AuthorToolsNav),
  {
    ssr: false,
    loading: () => <NavPanelLoadingState />,
  }
)

const ReaderOverview = dynamic(
  () => import("@/components/reader/ReaderOverview").then((module) => module.ReaderOverview),
  {
    loading: () => <WorkspacePanelLoadingState />,
  }
)

type IconName =
  | "analysis"
  | "bell"
  | "book"
  | "calendar"
  | "chat"
  | "chevron"
  | "edit"
  | "file"
  | "flame"
  | "gap"
  | "gear"
  | "graph"
  | "moon"
  | "pen"
  | "plus"
  | "search"
  | "spark"
  | "sun"
  | "timeline"
  | "users"
  | "voice"

type WorkspaceSaveState = "idle" | "saving" | "saved" | "error"

type ReaderBookmarkSnapshot = {
  chapter: number
  chapterTitle: string | null
  scrollPct: number
  savedAt: string
}

function storyUnitName(workType?: Book["work_type"], plural = false) {
  if (workType === "screenplay") return plural ? "scenes" : "scene"
  return plural ? "chapters" : "chapter"
}

function storyUnitTitle(workType?: Book["work_type"]) {
  return workType === "screenplay" ? "Scene" : "Chapter"
}

function storyUnitPrefix(workType?: Book["work_type"]) {
  return workType === "screenplay" ? "Sc." : "Ch."
}

function formatEtaLabel(seconds?: number | null) {
  if (typeof seconds !== "number" || Number.isNaN(seconds)) return null
  if (seconds <= 0) return "almost done"

  const minutes = Math.max(1, Math.round(seconds / 60))
  if (minutes < 60) return `${minutes} min left`

  const hours = Math.max(1, Math.round(minutes / 60))
  return `${hours} hr left`
}

function getProcessingSummary(book: Book | null) {
  const processing = book?.processing
  if (!processing) return null

  const stage = (processing.stage ?? processing.status ?? "").toString().trim()
  const completed = typeof processing.chapters_completed === "number" ? processing.chapters_completed : null
  const total = typeof processing.chapters_total === "number" ? processing.chapters_total : book?.total_chapters
  const progress = typeof processing.progress_pct === "number" ? processing.progress_pct : book?.progress_pct
  const eta = formatEtaLabel(processing.eta_seconds)
  const chapterLabel =
    processing.last_chapter_number
      ? `${storyUnitPrefix(book?.work_type)} ${processing.last_chapter_number}${processing.last_chapter_title ? ` - ${processing.last_chapter_title}` : ""}`
      : null

  const parts = [
    stage ? stage.replace(/_/g, " ") : null,
    completed !== null && total ? `${completed}/${total} ${storyUnitName(book?.work_type, true)}` : null,
    typeof progress === "number" ? `${Math.round(progress)}%` : null,
    eta,
    chapterLabel,
  ].filter(Boolean)

  return parts.length > 0 ? parts.join(" / ") : null
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value))
}

function estimateWordCount(book: Book | null, progress: ReadingProgress | null, targetWords: number) {
  if (typeof book?.total_tokens === "number" && book.total_tokens > 0) {
    return Math.round(book.total_tokens * 0.75)
  }

  const percent = progress?.percent_complete ?? book?.progress_pct
  if (typeof percent === "number" && percent > 0) {
    return Math.round(targetWords * (percent / 100))
  }

  return null
}

function formatNumber(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return "Syncing"
  return value.toLocaleString()
}

function formatDate(value: string | null | undefined) {
  if (!value) return "Today"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "Today"
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
}

function formatDateKey(date: Date) {
  const year = date.getFullYear()
  const month = `${date.getMonth() + 1}`.padStart(2, "0")
  const day = `${date.getDate()}`.padStart(2, "0")
  return `${year}-${month}-${day}`
}

function getCurrentWeekActivity(activityDates: string[]) {
  const activeDays = new Set(activityDates.filter(Boolean))
  const today = new Date()
  const start = new Date(today)
  const day = start.getDay()
  const offset = day === 0 ? -6 : 1 - day
  start.setDate(start.getDate() + offset)
  start.setHours(0, 0, 0, 0)

  return Array.from({ length: 7 }, (_, index) => {
    const current = new Date(start)
    current.setDate(start.getDate() + index)
    return activeDays.has(formatDateKey(current))
  })
}

function formatDateInputValue(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

function todayDateValue() {
  return formatDateInputValue(new Date())
}

function monthValueFromDate(dateValue: string) {
  return /^\d{4}-\d{2}-\d{2}$/.test(dateValue) ? dateValue.slice(0, 7) : todayDateValue().slice(0, 7)
}

function monthStartFromValue(monthValue: string) {
  const match = monthValue.match(/^(\d{4})-(\d{2})$/)
  const year = match ? Number(match[1]) : new Date().getFullYear()
  const monthIndex = match ? Math.max(0, Number(match[2]) - 1) : new Date().getMonth()
  return new Date(year, monthIndex, 1)
}

function shiftMonthValue(monthValue: string, delta: number) {
  const next = monthStartFromValue(monthValue)
  next.setMonth(next.getMonth() + delta)
  return formatDateInputValue(next).slice(0, 7)
}

function formatPlannerDate(dateValue: string) {
  const match = dateValue.match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!match) return "Select a day"
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
  return date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })
}

function formatPlannerMonth(monthValue: string) {
  return monthStartFromValue(monthValue).toLocaleDateString(undefined, { month: "long", year: "numeric" })
}

function buildCalendarDays(monthValue: string) {
  const monthStart = monthStartFromValue(monthValue)
  const gridStart = new Date(monthStart)
  gridStart.setDate(1 - monthStart.getDay())

  return Array.from({ length: 42 }, (_, index) => {
    const day = new Date(gridStart)
    day.setDate(gridStart.getDate() + index)
    return {
      value: formatDateInputValue(day),
      label: String(day.getDate()),
      inMonth: day.getMonth() === monthStart.getMonth(),
    }
  })
}

function createCalendarItemId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID()
  return `goal-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function formatQuotaLabel(value: number | null | undefined, unit: string | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value) || value <= 0) return null
  const cleanUnit = (unit || "items").trim() || "items"
  return `${value.toLocaleString()} ${cleanUnit}`
}

export default function BookOverviewPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const [bookmark, setBookmark] = useState<ReaderBookmarkSnapshot | null>(null)
  const [secondaryDataEnabled, setSecondaryDataEnabled] = useState(false)
  const [workspaceSaveState, setWorkspaceSaveState] = useState<WorkspaceSaveState>("idle")
  const [workspaceSaveMessage, setWorkspaceSaveMessage] = useState<string | null>(null)
  const [modeSaving, setModeSaving] = useState(false)
  const router = useRouter()
  const queryClient = useQueryClient()
  const { theme, toggleTheme } = usePreferencesStore()
  const bookMode = useBookModeStore((state) => state.getMode(bookId))
  const setBookMode = useBookModeStore((state) => state.setMode)
  const user = useAuthStore((state) => state.user)
  const authHydrated = useAuthStore((state) => state.hydrated)
  const userTier = useAuthStore((state) => state.user?.tier)
  const isDark = theme === "dark"
  const overviewScrollKey = `reader-overview-scroll:${bookId}`
  const overviewQueryKey = asQueryKey(bookCacheKey(bookId, "overview"))
  const bookQueryKey = asQueryKey(bookCacheKey(bookId, "detail"))
  const writerWorkspaceQueryKey = asQueryKey(bookCacheKey(bookId, "writer-workspace"))
  const overviewLoadStartedAt = useRef<number | null>(typeof performance !== "undefined" ? performance.now() : null)
  const overviewReadyCaptured = useRef(false)

  const overviewQuery = useQuery({
    queryKey: overviewQueryKey,
    queryFn: async () => {
      const payload = await booksApi.getOverview(bookId)
      queryClient.setQueryData(bookQueryKey, payload.book)
      queryClient.setQueryData(asQueryKey(readerCacheKey(bookId, "progress")), payload.progress)
      queryClient.setQueryData(asQueryKey(readerCacheKey(bookId, "chapters")), payload.chapter_list)
      queryClient.setQueryData(asQueryKey(readerCacheKey(bookId, "summary-collection")), payload.summary_collection)
      return payload
    },
    staleTime: 20_000,
    refetchInterval: (query) => {
      const currentBook = (query.state.data as BookOverviewPayload | undefined)?.book
      return currentBook && currentBook.status !== "ready" ? 3_000 : false
    },
    refetchIntervalInBackground: false,
  })
  const resolvedBookMode = overviewQuery.data?.book.mode ?? bookMode
  const resolvedCollaborationRole = overviewQuery.data?.book.collaboration_role ?? null
  const resolvedCollaborationPermissions = overviewQuery.data?.book.collaboration_permissions ?? null
  const canUsePaidAuthorTools = canUseAuthorFeatures(userTier) || Boolean(resolvedCollaborationPermissions?.can_edit_manuscript)
  const bookNotesQuery = useQuery({
    queryKey: asQueryKey(bookCacheKey(bookId, "notes")),
    queryFn: () => booksApi.getBookNotes(bookId),
    staleTime: 20_000,
    enabled: secondaryDataEnabled && resolvedBookMode === "reader",
  })
  const savedQuotesQuery = useQuery({
    queryKey: asQueryKey(booksQuotesCacheKey()),
    queryFn: () => booksApi.listQuotes(),
    staleTime: 45_000,
    enabled: secondaryDataEnabled && resolvedBookMode === "reader",
  })
  const charactersQuery = useQuery({
    queryKey: asQueryKey(bookCacheKey(bookId, "characters")),
    queryFn: () => booksApi.getCharacters(bookId),
    staleTime: 45_000,
    enabled: secondaryDataEnabled && resolvedBookMode === "author" && canUsePaidAuthorTools,
  })
  const chapterReportsQuery = useQuery({
    queryKey: asQueryKey(bookCacheKey(bookId, "chapter-reports:6")),
    queryFn: () => booksApi.getChapterReports(bookId, 6),
    staleTime: 30_000,
    enabled: secondaryDataEnabled && resolvedBookMode === "author" && canUsePaidAuthorTools,
  })
  const preWritingCheckQuery = useQuery({
    queryKey: asQueryKey(bookCacheKey(bookId, "pre-writing:auto")),
    queryFn: () => booksApi.getPreWritingCheck(bookId),
    staleTime: 30_000,
    enabled: secondaryDataEnabled && resolvedBookMode === "author" && canUsePaidAuthorTools,
  })
  const storyHealthQuery = useQuery({
    queryKey: asQueryKey(bookCacheKey(bookId, "story-health")),
    queryFn: () => booksApi.getStoryHealth(bookId),
    staleTime: 30_000,
    enabled: secondaryDataEnabled && resolvedBookMode === "author" && canUsePaidAuthorTools,
  })
  const writerWorkspaceQuery = useQuery({
    queryKey: writerWorkspaceQueryKey,
    queryFn: () => booksApi.getWriterWorkspace(bookId),
    staleTime: 10_000,
    enabled: secondaryDataEnabled && resolvedBookMode === "author" && canUsePaidAuthorTools,
  })
  const revisionIntelligenceQuery = useQuery({
    queryKey: asQueryKey(bookCacheKey(bookId, "revision-intelligence")),
    queryFn: () => booksApi.getRevisionIntelligence(bookId),
    staleTime: 20_000,
    enabled: secondaryDataEnabled && resolvedBookMode === "author" && canUsePaidAuthorTools,
  })

  const book = overviewQuery.data?.book ?? null
  const progress = overviewQuery.data?.progress ?? null
  const chapterList = overviewQuery.data?.chapter_list ?? null
  const summaryCollection = overviewQuery.data?.summary_collection ?? null
  const bookNotes = bookNotesQuery.data ?? []
  const savedQuotes = (savedQuotesQuery.data ?? []).filter((quote) => quote.book_id === bookId)
  const characters = charactersQuery.data ?? []
  const chapterReports = chapterReportsQuery.data ?? []
  const preWritingCheck = preWritingCheckQuery.data ?? null
  const storyHealth = storyHealthQuery.data ?? null
  const writerWorkspace = writerWorkspaceQuery.data ?? null
  const revisionIntelligence = revisionIntelligenceQuery.data ?? null

  useEffect(() => {
    if (secondaryDataEnabled) return

    const scheduleSecondaryData =
      typeof window.requestIdleCallback === "function"
        ? window.requestIdleCallback.bind(window)
        : ((callback: IdleRequestCallback) =>
            window.setTimeout(() => callback({ didTimeout: false, timeRemaining: () => 0 } as IdleDeadline), 120))
    const cancelSecondaryData =
      typeof window.cancelIdleCallback === "function"
        ? window.cancelIdleCallback.bind(window)
        : window.clearTimeout.bind(window)

    const handle = scheduleSecondaryData(() => {
      startTransition(() => setSecondaryDataEnabled(true))
    })

    return () => cancelSecondaryData(handle)
  }, [secondaryDataEnabled])

  useEffect(() => {
    if (typeof window === "undefined") return

    const bookmarkKey = `reader-bookmark:${bookId}`
    const raw = window.localStorage.getItem(bookmarkKey)
    if (!raw) {
      setBookmark(null)
      return
    }

    try {
      const parsed = JSON.parse(raw) as ReaderBookmarkSnapshot
      if (typeof parsed.chapter === "number" && typeof parsed.scrollPct === "number" && typeof parsed.savedAt === "string") {
        setBookmark(parsed)
        return
      }
    } catch {
      // ignore malformed bookmark payloads
    }

    setBookmark(null)
  }, [bookId])

  useEffect(() => {
    if (book?.mode === "reader" || book?.mode === "author") {
      setBookMode(bookId, book.mode)
    }
  }, [book?.mode, bookId, setBookMode])

  useEffect(() => {
    if (!overviewQuery.isSuccess || !overviewQuery.data || overviewReadyCaptured.current) return
    overviewReadyCaptured.current = true
    capture("reader_overview_critical_ready", {
      book_id: bookId,
      active_mode: overviewQuery.data.book.mode,
      critical_request_count: 1,
      duration_ms:
        typeof performance !== "undefined" && overviewLoadStartedAt.current !== null
          ? Math.round(performance.now() - overviewLoadStartedAt.current)
          : null,
    })
  }, [bookId, overviewQuery.data, overviewQuery.isSuccess])

  useEffect(() => {
    if (workspaceSaveState !== "saved") return
    const timeout = window.setTimeout(() => {
      setWorkspaceSaveState("idle")
      setWorkspaceSaveMessage(null)
    }, 2400)
    return () => window.clearTimeout(timeout)
  }, [workspaceSaveState])

  useEffect(() => {
    if (typeof window === "undefined") return

    const saved = window.sessionStorage.getItem(overviewScrollKey)
    if (saved) {
      const nextY = Number(saved)
      if (!Number.isNaN(nextY)) {
        window.setTimeout(() => window.scrollTo({ top: nextY, behavior: "auto" }), 40)
      }
    }

    const saveScroll = () => {
      window.sessionStorage.setItem(overviewScrollKey, String(window.scrollY))
    }

    saveScroll()
    window.addEventListener("scroll", saveScroll, { passive: true })
    return () => window.removeEventListener("scroll", saveScroll)
  }, [overviewScrollKey])

  const continueChapter = progress?.current_chapter ?? 1
  const percentComplete = Math.round(progress?.percent_complete ?? book?.progress_pct ?? 0)
  const chaptersLeft = progress?.chapters_left ?? book?.chapters_left ?? 0
  const activeBookMode = book?.mode ?? bookMode
  const collaborationRole = book?.collaboration_role ?? null
  const collaborationPermissions = book?.collaboration_permissions ?? null
  const isCollaboratorSession = Boolean(collaborationRole)
  const hasCollaboratorAuthorAccess = Boolean(collaborationPermissions?.can_edit_manuscript)
  const canUseAuthorWorkspace = !isCollaboratorSession || hasCollaboratorAuthorAccess
  const canEditSharedManuscript = !isCollaboratorSession || hasCollaboratorAuthorAccess
  const processingSummary = getProcessingSummary(book)
  const unitTitle = storyUnitTitle(book?.work_type)
  const unitPrefix = storyUnitPrefix(book?.work_type)
  const chapters = chapterList?.chapters ?? []
  const chapterCount = chapters.length || book?.total_chapters || null
  const targetWords = Math.max(1, writerWorkspace?.word_count_goals.book_target ?? 100000)
  const currentWords = typeof book?.total_words === "number" && book.total_words > 0 ? book.total_words : estimateWordCount(book, progress, targetWords)
  const dailyTarget = Math.max(1, user?.daily_word_goal ?? 1000)
  const dailyWords = Math.max(0, user?.today_word_count ?? 0)
  const loginStreakDays = Math.max(0, user?.login_streak_days ?? 0)
  const weeklyLoginActivity = getCurrentWeekActivity(user?.login_activity_dates ?? [])
  const continuityIssueCount = chapterReports.reduce((sum, report) => sum + report.continuity_flags.length, 0)
  const worldGapCount = preWritingCheck?.alerts.length ?? 0
  const timelineIssueCount = Math.max(0, chaptersLeft > 0 ? Math.min(3, Math.ceil(chaptersLeft / 8)) : 0)
  const greetingName = authHydrated ? user?.username?.trim() || "there" : "there"

  const navigateWithMemory = (href: string) => {
    if (typeof window !== "undefined") {
      window.sessionStorage.setItem(overviewScrollKey, String(window.scrollY))
    }
    router.push(href as Route)
  }

  const saveWorkspacePatch = async (
    patch: Partial<WriterWorkspace>,
    messages: { saving: string; success: string; error: string }
  ) => {
    if (!writerWorkspace) return false

    const previous = writerWorkspace
    queryClient.setQueryData(writerWorkspaceQueryKey, { ...writerWorkspace, ...patch })
    setWorkspaceSaveState("saving")
    setWorkspaceSaveMessage(messages.saving)

    try {
      const updated = await booksApi.updateWriterWorkspace(bookId, patch)
      queryClient.setQueryData(writerWorkspaceQueryKey, updated)
      setWorkspaceSaveState("saved")
      setWorkspaceSaveMessage(messages.success)
      return true
    } catch {
      queryClient.setQueryData(writerWorkspaceQueryKey, previous)
      setWorkspaceSaveState("error")
      setWorkspaceSaveMessage(messages.error)
      return false
    }
  }

  const saveGoalCalendar = async (goalCalendar: GoalCalendarItem[]) =>
    saveWorkspacePatch(
      { goal_calendar: goalCalendar },
      {
        saving: "Saving planner...",
        success: "Planner saved.",
        error: "Could not save planner changes.",
      }
    )

  const continueReading = () => {
    navigateWithMemory(`/${bookId}/chapter/${continueChapter}`)
  }

  const openAddSceneFlow = () => {
    navigateWithMemory(`/${bookId}/manuscript?newScene=1`)
  }

  const openRelationships = () => {
    navigateWithMemory(`/${bookId}/graph`)
  }

  const updateMode = async (nextMode: "reader" | "author") => {
    if (modeSaving) return
    if (nextMode === activeBookMode) return
    if (nextMode === "author" && !canUseAuthorWorkspace) return
    const previousBook = book
    startTransition(() => setBookMode(bookId, nextMode))
    setModeSaving(true)
    if (previousBook) {
      queryClient.setQueryData(bookQueryKey, { ...previousBook, mode: nextMode })
      queryClient.setQueryData(overviewQueryKey, (current: BookOverviewPayload | undefined) => (
        current ? { ...current, book: { ...current.book, mode: nextMode } } : current
      ))
    }
    try {
      const updated = await booksApi.setMode(bookId, nextMode)
      queryClient.setQueryData(bookQueryKey, updated)
      queryClient.setQueryData(overviewQueryKey, (current: BookOverviewPayload | undefined) => (
        current ? { ...current, book: updated } : current
      ))
    } catch {
      startTransition(() => setBookMode(bookId, previousBook?.mode ?? "reader"))
      if (previousBook) {
        queryClient.setQueryData(bookQueryKey, previousBook)
        queryClient.setQueryData(overviewQueryKey, (current: BookOverviewPayload | undefined) => (
          current ? { ...current, book: previousBook } : current
        ))
      }
    } finally {
      setModeSaving(false)
    }
  }

  if (!book) {
    return (
      <div className={`min-h-screen ${isDark ? "bg-[#171b1d] text-slate-400" : "bg-[#f8f4ee] text-slate-500"}`}>
        <div className="flex min-h-screen items-center justify-center text-sm font-medium">Loading...</div>
      </div>
    )
  }

  return (
    <div className={`min-h-screen ${isDark ? "bg-[#171b1d] text-slate-100" : "bg-[#f8f4ee] text-slate-950"}`}>
      <div className="mx-auto grid max-w-[100rem] gap-5 px-4 pb-28 pt-5 sm:px-6 lg:grid-cols-[15.5rem_minmax(0,1fr)] lg:px-8 xl:gap-6">
        <div className="lg:hidden">
          <AuthorToolsNav
            bookId={bookId}
            active="overview"
            isDark={isDark}
            bookData={book}
            title={activeBookMode === "author" ? "Author workspace" : "Reader workspace"}
            description={activeBookMode === "author" ? "Drafting and intelligence stay nearby without crowding the book." : "Reading, chapters, and quiet tools stay one hover away."}
            currentChapter={continueChapter}
            mode={activeBookMode}
          />
        </div>

        <div className="hidden lg:block lg:sticky lg:top-5 lg:self-start">
          <AuthorToolsNav
            bookId={bookId}
            active="overview"
            isDark={isDark}
            bookData={book}
            title={activeBookMode === "author" ? "Author workspace" : "Reader workspace"}
            description={activeBookMode === "author" ? "Drafting and intelligence stay nearby without crowding the book." : "Reading, chapters, and quiet tools stay one hover away."}
            currentChapter={continueChapter}
            mode={activeBookMode}
            variant="rail"
            railSize="compact"
          />
        </div>

        <main className="min-w-0 space-y-5">
          {activeBookMode === "reader" ? (
            <ReaderOverview
              bookId={bookId}
              book={book}
              activeBookMode={activeBookMode}
              progress={progress}
              chapterList={chapterList}
              summaryCollection={summaryCollection}
              bookNotes={bookNotes}
              savedQuotes={savedQuotes}
              bookmark={bookmark}
              isDark={isDark}
              modeSaving={modeSaving}
              canUseAuthorMode={canUseAuthorWorkspace}
              onModeChange={updateMode}
              onToggleTheme={toggleTheme}
              onNavigate={navigateWithMemory}
              onContinueReading={continueReading}
            />
          ) : (
            <AuthorWorkspaceDashboard
              bookId={bookId}
              book={book}
              isDark={isDark}
              activeBookMode={activeBookMode}
              canUseAuthorMode={canUseAuthorWorkspace}
              modeSaving={modeSaving}
              greetingName={greetingName}
              canOpenManuscript={canEditSharedManuscript}
              currentWords={currentWords}
              targetWords={targetWords}
              percentComplete={percentComplete}
              chapters={chapters}
              unitTitle={unitTitle}
              unitPrefix={unitPrefix}
              storyHealth={storyHealth}
              preWritingCheck={preWritingCheck}
              revisionIntelligence={revisionIntelligence}
              writerWorkspace={writerWorkspace}
              continuityIssueCount={continuityIssueCount}
              worldGapCount={worldGapCount}
              timelineIssueCount={timelineIssueCount}
              processingSummary={processingSummary}
              chapterCount={chapterCount}
              characterCount={characters.length}
              worldArticleCount={(writerWorkspace?.templates.length ?? 0) + (writerWorkspace?.corkboard_cards.length ?? 0)}
              loginStreakDays={loginStreakDays}
              weeklyLoginActivity={weeklyLoginActivity}
              dailyWords={dailyWords}
              dailyTarget={dailyTarget}
              saveState={workspaceSaveState}
              saveMessage={workspaceSaveMessage}
              onModeChange={updateMode}
              onToggleTheme={toggleTheme}
              onNavigate={navigateWithMemory}
              onOpenManuscript={() => navigateWithMemory(`/${bookId}/manuscript`)}
              onOpenRelationships={openRelationships}
              onSaveGoalCalendar={saveGoalCalendar}
              onRevisionChange={(nextRevision) => {
                queryClient.setQueryData(asQueryKey(bookCacheKey(bookId, "revision-intelligence")), nextRevision)
              }}
              onWriterWorkspaceChange={(nextWorkspace) => {
                queryClient.setQueryData(writerWorkspaceQueryKey, nextWorkspace)
              }}
            />
          )}
        </main>
      </div>

      {activeBookMode === "author" && canEditSharedManuscript ? (
        <CreateFab bookId={bookId} isDark={isDark} onAddScene={openAddSceneFlow} onNavigate={navigateWithMemory} />
      ) : null}

      <nav className={`fixed inset-x-0 bottom-0 z-30 border-t px-4 py-3 backdrop-blur lg:hidden ${isDark ? "border-white/10 bg-[#171b1d]/95" : "border-slate-200 bg-white/95"}`}>
        <div className={`mx-auto grid max-w-xl grid-cols-6 gap-2 text-center text-[11px] font-medium ${isDark ? "text-slate-400" : "text-slate-500"}`}>
          <Link href={`/${bookId}`} className="rounded-xl px-2 py-2 text-teal-800">Overview</Link>
          <button onClick={continueReading} className="rounded-xl px-2 py-2">Read</button>
          <Link href={`/${bookId}/chapters`} className="rounded-xl px-2 py-2">Chapters</Link>
          <Link href={`/${bookId}/summaries`} className="rounded-xl px-2 py-2">Summary</Link>
          <button onClick={openRelationships} className="rounded-xl px-2 py-2">Graph</button>
          <Link href="/library" className="rounded-xl px-2 py-2">Library</Link>
        </div>
      </nav>
    </div>
  )
}

function OverviewHeader({
  isDark,
  activeBookMode,
  canUseAuthorMode,
  modeSaving,
  greetingName,
  onModeChange,
  onToggleTheme,
}: {
  isDark: boolean
  activeBookMode: "reader" | "author"
  canUseAuthorMode: boolean
  modeSaving: boolean
  greetingName: string
  onModeChange: (nextMode: "reader" | "author") => void
  onToggleTheme: () => void
}) {
  return (
    <header className="flex flex-col gap-4 py-2 md:flex-row md:items-center md:justify-between">
      <div>
        <h1 className={`text-2xl font-semibold tracking-tight ${isDark ? "text-white" : "text-slate-950"}`}>{`Welcome back, ${greetingName}.`}</h1>
        <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>Every great story is a world carefully remembered.</p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className={`inline-flex h-10 overflow-hidden rounded-md border ${isDark ? "border-white/10 bg-white/[0.04]" : "border-slate-200 bg-white"}`}>
            {(["reader", "author"] as const).map((mode) => {
              const locked = mode === "author" && !canUseAuthorMode
              return (
              <button
                key={mode}
                onClick={() => onModeChange(mode)}
              disabled={modeSaving || locked}
              className={`px-3 text-xs font-semibold capitalize transition ${
                activeBookMode === mode
                  ? isDark ? "bg-teal-800 text-white" : "bg-teal-800 text-white"
                  : locked
                    ? isDark ? "text-slate-600" : "text-slate-400"
                    : isDark ? "text-slate-400 hover:bg-white/[0.06]" : "text-slate-500 hover:bg-slate-50"
              }`}
              >
                {locked ? "author locked" : mode}
              </button>
              )
            })}
        </div>
        <Link href="/library" className={`inline-flex h-10 items-center gap-2 rounded-md px-4 text-sm font-semibold shadow-[0_14px_28px_-18px_rgba(124,58,237,0.85)] ${isDark ? "bg-teal-800/90 text-white hover:bg-teal-800" : "bg-teal-800 text-white hover:bg-teal-800"}`}>
          <Icon name="plus" />
          New Project
        </Link>
        <IconLink href="/library" label="Search library" icon="search" isDark={isDark} />
        <IconLink href="/notifications" label="Notifications" icon="bell" isDark={isDark} />
        <button
          onClick={onToggleTheme}
          aria-label={`Switch to ${isDark ? "light" : "dark"} mode`}
          className={`flex h-10 w-10 items-center justify-center rounded-md border transition ${isDark ? "border-white/10 bg-white/[0.04] text-slate-300 hover:bg-white/[0.08]" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}`}
        >
          <Icon name={isDark ? "sun" : "moon"} />
        </button>
        <IconLink href="/settings" label="Settings" icon="gear" isDark={isDark} />
      </div>
    </header>
  )
}

function CurrentProjectCard({
  book,
  isDark,
  canOpenManuscript,
  currentWords,
  targetWords,
  percentComplete,
  chapters,
  unitTitle,
  unitPrefix,
  onOpenManuscript,
}: {
  book: Book
  isDark: boolean
  canOpenManuscript: boolean
  currentWords: number | null
  targetWords: number
  percentComplete: number
  chapters: ChapterListResponse["chapters"]
  unitTitle: string
  unitPrefix: string
  onOpenManuscript: () => void
}) {
  const recentChapters = chapters.slice(-4).reverse()

  return (
    <section className={panelClass(isDark, "p-4 sm:p-5")}>
      <PanelTitle isDark={isDark}>Current Project</PanelTitle>
      <div className="mt-4 grid gap-5 md:grid-cols-[9rem_minmax(0,1fr)_minmax(13rem,0.78fr)]">
        <BookCover book={book} isDark={isDark} />

        <div className="min-w-0">
          <div className="flex items-start gap-2">
            <h2 className={`truncate text-2xl font-semibold tracking-tight ${isDark ? "text-white" : "text-slate-950"}`}>{book.title}</h2>
            <Icon name="edit" className={isDark ? "mt-1 h-4 w-4 text-slate-500" : "mt-1 h-4 w-4 text-slate-400"} />
          </div>
          <p className="mt-2 text-sm font-semibold text-teal-800">{book.genre || (book.work_type === "screenplay" ? "Screenplay" : "Manuscript")}</p>

          <div className="mt-7">
            <div className={`flex items-end justify-between text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
              <span>Manuscript Progress</span>
              <span>{formatNumber(currentWords)} / {targetWords.toLocaleString()} words</span>
            </div>
            <div className={`mt-2 h-2 overflow-hidden rounded-full ${isDark ? "bg-white/10" : "bg-slate-100"}`}>
              <div
                className="h-full rounded-full bg-[linear-gradient(90deg,#7c3aed,#a855f7)]"
                style={{ width: `${clamp(percentComplete || (currentWords ? (currentWords / targetWords) * 100 : 0), 0, 100)}%` }}
              />
            </div>
            <div className={`mt-1 text-right text-xs font-semibold ${isDark ? "text-slate-500" : "text-slate-400"}`}>{clamp(percentComplete, 0, 100)}%</div>
          </div>

          <div className={`mt-6 grid gap-3 border-t pt-4 text-sm ${isDark ? "border-white/10" : "border-slate-100"}`}>
            <InfoRow label="Status" value={book.status === "ready" ? "Drafting" : book.status.replace(/_/g, " ")} isDark={isDark} dot />
            <InfoRow label="Last Edited" value={formatDate(book.created_at)} isDark={isDark} />
          </div>
        </div>

        <div className="flex flex-col">
          <p className={`text-xs font-semibold ${isDark ? "text-slate-500" : "text-slate-400"}`}>Recent {unitTitle}s</p>
          <div className="mt-4 space-y-3">
            {recentChapters.length > 0 ? recentChapters.map((chapter) => (
              <div key={chapter.number} className="flex items-center justify-between gap-3 text-xs">
                <span className={`truncate ${isDark ? "text-slate-300" : "text-slate-600"}`}>
                  {unitPrefix} {chapter.number}. {chapter.title || `${unitTitle} ${chapter.number}`}
                </span>
                <span className={isDark ? "text-slate-600" : "text-slate-400"}>{chapter.read ? "Read" : "Open"}</span>
              </div>
            )) : (
              <p className={`text-sm leading-6 ${isDark ? "text-slate-500" : "text-slate-500"}`}>{unitTitle} indexing is still syncing.</p>
            )}
          </div>

          {canOpenManuscript ? (
            <button
              type="button"
              onClick={onOpenManuscript}
              className={`mt-auto inline-flex h-10 items-center justify-center gap-2 rounded-md px-4 text-xs font-semibold transition ${isDark ? "bg-teal-800/10 text-teal-200 hover:bg-teal-800/18" : "bg-teal-50 text-teal-800 hover:bg-teal-100"}`}
            >
              Open Manuscript Editor
              <Icon name="chevron" className="h-3.5 w-3.5" />
            </button>
          ) : null}
        </div>
      </div>
    </section>
  )
}

function StoryHealthCard({
  bookId,
  isDark,
  storyHealth,
}: {
  bookId: string
  isDark: boolean
  storyHealth: StoryHealth | null
}) {
  const score = storyHealth?.score ?? 0
  const status = storyHealth?.status ?? "Loading"
  const summary = storyHealth?.summary ?? "Syncing story metrics from your book data."
  const healthColor = score >= 85 ? "#45d483" : score >= 70 ? "#8b5cf6" : score >= 55 ? "#f5bf3d" : "#fb7185"
  const metricColors: Record<string, { text: string; bar: string }> = {
    Continuity: { text: "text-emerald-400", bar: "bg-emerald-400" },
    "Character consistency": { text: "text-sky-400", bar: "bg-sky-400" },
    "Timeline clarity": { text: "text-teal-700", bar: "bg-teal-600" },
    "Plot thread closure": { text: "text-amber-400", bar: "bg-amber-400" },
    "Worldbuilding consistency": { text: "text-cyan-400", bar: "bg-cyan-400" },
    Pacing: { text: "text-rose-400", bar: "bg-rose-400" },
    "Dialogue/voice consistency": { text: "text-fuchsia-400", bar: "bg-fuchsia-400" },
  }
  const metrics = storyHealth?.metrics ?? []

  return (
    <section className={panelClass(isDark, "p-4 sm:p-5")}>
      <div className="flex items-center gap-2">
        <PanelTitle isDark={isDark}>Story Health</PanelTitle>
        <span className={`flex h-4 w-4 items-center justify-center rounded-full border text-[10px] ${isDark ? "border-white/15 text-slate-500" : "border-slate-200 text-slate-400"}`}>i</span>
      </div>

      <div className="mt-5 grid gap-5 sm:grid-cols-[8.5rem_minmax(0,1fr)] xl:grid-cols-1 2xl:grid-cols-[8.5rem_minmax(0,1fr)]">
        <div className="flex justify-center">
          <div
            className="relative flex h-32 w-32 items-center justify-center rounded-full"
            style={{ background: `conic-gradient(${healthColor} 0 ${score}%, ${isDark ? "#1b2430" : "#edf0f5"} ${score}% 100%)` }}
          >
            <div className={`flex h-22 w-22 flex-col items-center justify-center rounded-full ${isDark ? "bg-[#0d141c]" : "bg-white"}`}>
              <span className={`text-3xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{score}</span>
              <span className={`text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>{status}</span>
            </div>
          </div>
        </div>

        <div className="space-y-3">
          {metrics.map((metric) => {
            const colors = metricColors[metric.label] ?? { text: "text-teal-700", bar: "bg-teal-600" }
            return (
              <div key={metric.label} className={`rounded-md border p-3 ${isDark ? "border-white/[0.06] bg-white/[0.025]" : "border-slate-200/70 bg-slate-50/70"}`}>
                <div className="flex items-center justify-between gap-3 text-xs">
                  <span className={isDark ? "text-slate-300" : "text-slate-700"}>{metric.label}</span>
                  <span className={`font-bold ${colors.text}`}>{metric.score}%</span>
                </div>
                <div className={`mt-2 h-1.5 overflow-hidden rounded-full ${isDark ? "bg-white/[0.08]" : "bg-slate-200"}`}>
                  <div
                    className={`h-full rounded-full ${colors.bar}`}
                    style={{ width: `${metric.score}%` }}
                  />
                </div>
                <p className={`mt-2 text-[11px] leading-5 ${isDark ? "text-slate-500" : "text-slate-500"}`}>{metric.detail}</p>
              </div>
            )
          })}
        </div>
      </div>

      <p className={`mt-5 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{summary}</p>
      <Link href={`/${bookId}/analysis`} className={`mt-4 inline-flex h-10 w-full items-center justify-center gap-2 rounded-md text-xs font-semibold transition ${isDark ? "bg-teal-800/10 text-teal-200 hover:bg-teal-800/18" : "bg-teal-50 text-teal-800 hover:bg-teal-100"}`}>
        <Icon name="analysis" className="h-4 w-4" />
        View Full Analysis
      </Link>
    </section>
  )
}

function ActiveIssuesCard({
  isDark,
  continuityIssueCount,
  worldGapCount,
  timelineIssueCount,
  onNavigate,
  bookId,
}: {
  isDark: boolean
  continuityIssueCount: number
  worldGapCount: number
  timelineIssueCount: number
  onNavigate: (href: string) => void
  bookId: string
}) {
  const issues = [
    { title: "Character Inconsistencies", rawCount: continuityIssueCount, severity: "High", icon: "users" as IconName, color: "text-rose-400", href: `/${bookId}/reports` },
    { title: "World Gaps", rawCount: worldGapCount, severity: "Medium", icon: "gap" as IconName, color: "text-amber-400", href: `/${bookId}/world-gap` },
    { title: "Timeline Conflicts", rawCount: timelineIssueCount, severity: "Low", icon: "timeline" as IconName, color: "text-teal-700", href: `/${bookId}/timeline` },
  ].map((issue) => ({
    ...issue,
    ...buildIssueDisplay(issue.rawCount),
  }))
  const totalDisplayedIssues = issues.reduce((sum, issue) => sum + issue.displayCount, 0)

  return (
    <section className={panelClass(isDark, "p-4 sm:p-5")}>
      <div className="flex items-center gap-2">
        <PanelTitle isDark={isDark}>Active Issues</PanelTitle>
        <span className="rounded-full bg-rose-500 px-1.5 py-0.5 text-[10px] font-bold leading-none text-white">{totalDisplayedIssues}</span>
      </div>

      <div className="mt-4 space-y-3">
        {issues.map((issue) => (
          <button
            key={issue.title}
            onClick={() => onNavigate(issue.href)}
            className={`flex w-full items-center gap-3 rounded-md border p-3 text-left transition ${isDark ? "border-white/[0.06] bg-white/[0.025] hover:bg-white/[0.05]" : "border-slate-100 bg-white hover:bg-slate-50"}`}
          >
            <Icon name={issue.icon} className={`h-6 w-6 ${issue.color}`} />
            <div className="min-w-0 flex-1">
              <p className={`truncate text-sm font-semibold ${isDark ? "text-slate-200" : "text-slate-700"}`}>{issue.title}</p>
              <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>{issue.label}</p>
            </div>
            <span className={`rounded px-2 py-1 text-[10px] font-semibold ${severityClass(issue.severity, isDark)}`}>{issue.severity}</span>
            <Icon name="chevron" className={isDark ? "h-3.5 w-3.5 text-slate-600" : "h-3.5 w-3.5 text-slate-400"} />
          </button>
        ))}
      </div>

      <button onClick={() => onNavigate(`/${bookId}/analysis`)} className="mt-5 inline-flex w-full items-center justify-end gap-2 text-xs font-semibold text-teal-800">
        Go to Insights
        <Icon name="chevron" className="h-3.5 w-3.5" />
      </button>
    </section>
  )
}

function QuickToolsCard({ isDark, bookId, onNavigate }: { isDark: boolean; bookId: string; onNavigate: (href: string) => void }) {
  const tools = [
    { title: "Story Advisor", body: "Get AI feedback on your story", href: `/${bookId}/advisor`, icon: "graph" as IconName, color: "text-teal-700" },
    { title: "Ask LoreVia", body: "Ask anything about your story", href: `/${bookId}/ask`, icon: "chat" as IconName, color: "text-blue-400" },
    { title: "World Gap Detection", body: "Find missing or inconsistent details", href: `/${bookId}/world-gap`, icon: "gap" as IconName, color: "text-amber-400" },
    { title: "Character Bible", body: "Manage your characters", href: `/${bookId}/characters`, icon: "file" as IconName, color: "text-emerald-400" },
    { title: "Voice Inconsistency", body: "Detect character voice drift", href: `/${bookId}/voice`, icon: "voice" as IconName, color: "text-rose-400" },
    { title: "Manuscript Editor", body: "Write and edit your manuscript", href: `/${bookId}/manuscript`, icon: "book" as IconName, color: "text-teal-700" },
  ]

  return (
    <section className={panelClass(isDark, "p-4 sm:p-5")}>
      <PanelTitle isDark={isDark}>Quick Tools</PanelTitle>
      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-2 2xl:grid-cols-3">
        {tools.map((tool) => (
          <button
            key={tool.title}
            onClick={() => onNavigate(tool.href)}
            className={`min-h-32 rounded-md border p-3 text-left transition ${isDark ? "border-white/[0.06] bg-white/[0.025] hover:bg-white/[0.055]" : "border-slate-100 bg-white hover:bg-slate-50"}`}
          >
            <Icon name={tool.icon} className={`h-6 w-6 ${tool.color}`} />
            <p className={`mt-4 text-sm font-semibold ${isDark ? "text-slate-200" : "text-slate-700"}`}>{tool.title}</p>
            <p className={`mt-2 text-xs leading-5 ${isDark ? "text-slate-500" : "text-slate-400"}`}>{tool.body}</p>
          </button>
        ))}
      </div>
    </section>
  )
}

function RecentActivityCard({
  isDark,
  book,
  unitTitle,
  continueChapter,
  processingSummary,
}: {
  isDark: boolean
  book: Book
  unitTitle: string
  continueChapter: number
  processingSummary: string | null
}) {
  const activity = [
    { icon: "pen" as IconName, title: `You edited ${unitTitle} ${Math.max(1, continueChapter - 1)}`, time: "Today", color: "text-slate-400" },
    { icon: "spark" as IconName, title: processingSummary || "LoreVia checked story intelligence", time: "Today", color: "text-rose-400" },
    { icon: "users" as IconName, title: `You updated ${book.title}`, time: formatDate(book.created_at), color: "text-blue-400" },
    { icon: "calendar" as IconName, title: "World setting updated", time: "Recently", color: "text-slate-400" },
    { icon: "voice" as IconName, title: "Voice consistency check completed", time: "Recently", color: "text-teal-700" },
  ]

  return (
    <section className={panelClass(isDark, "p-4 sm:p-5")}>
      <PanelTitle isDark={isDark}>Recent Activity</PanelTitle>
      <div className="mt-4 space-y-4">
        {activity.map((item) => (
          <div key={item.title} className="flex gap-3">
            <Icon name={item.icon} className={`mt-0.5 h-4 w-4 shrink-0 ${item.color}`} />
            <div className="min-w-0">
              <p className={`line-clamp-2 text-sm font-medium leading-5 ${isDark ? "text-slate-300" : "text-slate-700"}`}>{item.title}</p>
              <p className={`mt-1 text-xs ${isDark ? "text-slate-600" : "text-slate-400"}`}>{item.time}</p>
            </div>
          </div>
        ))}
      </div>
      <Link href="/notifications" className="mt-5 inline-flex w-full items-center justify-end gap-2 text-xs font-semibold text-teal-800">
        View All Activity
        <Icon name="chevron" className="h-3.5 w-3.5" />
      </Link>
    </section>
  )
}

function ProjectOverviewCard({
  isDark,
  currentWords,
  chapterCount,
  characterCount,
  worldArticleCount,
}: {
  isDark: boolean
  currentWords: number | null
  chapterCount: number | null
  characterCount: number
  worldArticleCount: number
}) {
  const stats = [
    { label: "Total Words", value: formatNumber(currentWords), icon: "spark" as IconName, color: "text-teal-700", path: "M2 17c2-5 4-2 6-5s4 1 6-3 4 0 6-4" },
    { label: "Chapters", value: formatNumber(chapterCount), icon: "book" as IconName, color: "text-blue-400", path: "M2 15c2-1 3-6 5-4s2 6 5 3 4-6 8-4" },
    { label: "Characters", value: formatNumber(characterCount), icon: "users" as IconName, color: "text-emerald-400", path: "M2 16c3-3 4 1 7-2s5-7 11-5" },
    { label: "World Articles", value: formatNumber(worldArticleCount), icon: "file" as IconName, color: "text-amber-400", path: "M2 17c4-1 4-8 7-5s3 6 6 2 4-4 5-3" },
  ]

  return (
    <section className={panelClass(isDark, "p-4 sm:p-5")}>
      <PanelTitle isDark={isDark}>Project Overview</PanelTitle>
      <div className="mt-6 grid gap-4 sm:grid-cols-4">
        {stats.map((stat) => (
          <div key={stat.label} className="min-w-0">
            <p className={`text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>{stat.label}</p>
            <p className={`mt-2 text-2xl font-semibold tracking-tight ${isDark ? "text-white" : "text-slate-950"}`}>{stat.value}</p>
            <div className="mt-5 flex items-end gap-2">
              <Icon name={stat.icon} className={`h-5 w-5 ${stat.color}`} />
              <svg className={`h-8 min-w-0 flex-1 ${stat.color}`} viewBox="0 0 22 20" fill="none" aria-hidden="true">
                <path d={stat.path} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

function WritingStreakCard({ isDark, streakDays, weekActivity }: { isDark: boolean; streakDays: number; weekActivity: boolean[] }) {
  return (
    <section className={panelClass(isDark, "p-4 sm:p-5")}>
      <PanelTitle isDark={isDark}>Writing Streak</PanelTitle>
      <div className="mt-6 flex items-center gap-3">
        <Icon name="flame" className="h-8 w-8 text-orange-400" />
        <div>
          <p className={`text-2xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{streakDays} days</p>
          <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>Tracked from daily sign-ins.</p>
        </div>
      </div>
      <div className="mt-7 grid grid-cols-7 gap-2">
        {["M", "T", "W", "T", "F", "S", "S"].map((day, index) => (
          <div key={`${day}-${index}`} className="text-center">
            <div className={`mx-auto h-9 w-4 rounded-full ${weekActivity[index] ? "bg-teal-800" : isDark ? "bg-white/10" : "bg-slate-200"}`} />
            <p className={`mt-2 text-[10px] font-semibold ${isDark ? "text-slate-500" : "text-slate-400"}`}>{day}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

function DailyGoalCard({ isDark, dailyWords, dailyTarget }: { isDark: boolean; dailyWords: number; dailyTarget: number }) {
  const goalPercent = clamp((dailyWords / dailyTarget) * 100, 0, 100)
  const progressLabel =
    dailyWords >= dailyTarget
      ? "Goal reached today."
      : dailyWords > 0
        ? "Progress updates when you save manuscript edits."
        : "No writing logged yet today."

  return (
    <section className={panelClass(isDark, "p-4 sm:p-5")}>
      <PanelTitle isDark={isDark}>Daily Goal</PanelTitle>
      <div className="mt-6 flex items-center justify-center">
        <div
          className="relative flex h-32 w-32 items-center justify-center rounded-full"
          style={{ background: `conic-gradient(#8b5cf6 0 ${goalPercent}%, ${isDark ? "#1b2430" : "#edf0f5"} ${goalPercent}% 100%)` }}
        >
          <div className={`flex h-24 w-24 flex-col items-center justify-center rounded-full ${isDark ? "bg-[#0d141c]" : "bg-white"}`}>
            <span className={`text-2xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{dailyWords.toLocaleString()}</span>
            <span className={`text-[10px] ${isDark ? "text-slate-500" : "text-slate-400"}`}>/ {dailyTarget.toLocaleString()} words</span>
          </div>
        </div>
      </div>
      <div className="mt-5 flex items-center justify-between gap-3">
        <p className={`text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>{progressLabel}</p>
        <Link href="/settings" className={`rounded-md px-3 py-2 text-xs font-semibold ${isDark ? "bg-teal-800/10 text-teal-200" : "bg-teal-50 text-teal-800"}`}>Update Goal</Link>
      </div>
    </section>
  )
}

function GoalCalendarCard({
  isDark,
  writerWorkspace,
  saveState,
  saveMessage,
  onSaveGoalCalendar,
  onOpenManuscript,
}: {
  isDark: boolean
  writerWorkspace: WriterWorkspace | null
  saveState: WorkspaceSaveState
  saveMessage: string | null
  onSaveGoalCalendar: (goalCalendar: GoalCalendarItem[]) => Promise<boolean>
  onOpenManuscript: () => void
}) {
  const editable = Boolean(writerWorkspace)
  const [selectedDate, setSelectedDate] = useState(() => todayDateValue())
  const [visibleMonth, setVisibleMonth] = useState(() => todayDateValue().slice(0, 7))
  const [draftTitle, setDraftTitle] = useState("")
  const [draftQuotaValue, setDraftQuotaValue] = useState("")
  const [draftQuotaUnit, setDraftQuotaUnit] = useState("words")
  const today = todayDateValue()
  const goalCalendar = writerWorkspace?.goal_calendar ?? []
  const calendarDays = useMemo(() => buildCalendarDays(visibleMonth), [visibleMonth])
  const itemsByDate = useMemo(() => {
    const map = new Map<string, GoalCalendarItem[]>()
    for (const item of goalCalendar) {
      const current = map.get(item.due_date) ?? []
      current.push(item)
      map.set(item.due_date, current)
    }

    for (const items of map.values()) {
      items.sort((left, right) => {
        if (left.completed !== right.completed) return left.completed ? 1 : -1
        return left.title.localeCompare(right.title)
      })
    }

    return map
  }, [goalCalendar])
  const selectedItems = itemsByDate.get(selectedDate) ?? []
  const selectedQuotaTotal = selectedItems.reduce((sum, item) => sum + (item.quota_value ?? 0), 0)
  const monthItemCount = goalCalendar.filter((item) => item.due_date.startsWith(visibleMonth)).length
  const monthCompletedCount = goalCalendar.filter((item) => item.due_date.startsWith(visibleMonth) && item.completed).length
  const goalChips = [
    { label: "Book goal", value: writerWorkspace?.word_count_goals.book_target, unit: "words" },
    { label: "Chapter goal", value: writerWorkspace?.word_count_goals.chapter_target, unit: "words" },
    { label: "Session quota", value: writerWorkspace?.word_count_goals.session_target, unit: "words" },
  ]

  useEffect(() => {
    if (selectedDate.startsWith(visibleMonth)) return
    setVisibleMonth(monthValueFromDate(selectedDate))
  }, [selectedDate, visibleMonth])

  const addCalendarItem = async () => {
    const title = draftTitle.trim()
    if (!title || !writerWorkspace || !editable) return

    const parsedQuota = Number(draftQuotaValue)
    const nextItems = [
      ...goalCalendar,
      {
        id: createCalendarItemId(),
        title,
        due_date: selectedDate,
        quota_value: Number.isFinite(parsedQuota) && parsedQuota > 0 ? Math.round(parsedQuota) : null,
        quota_unit: Number.isFinite(parsedQuota) && parsedQuota > 0 ? draftQuotaUnit : null,
        completed: false,
      },
    ]

    const saved = await onSaveGoalCalendar(nextItems)
    if (!saved) return
    setDraftTitle("")
    setDraftQuotaValue("")
  }

  const toggleCalendarItem = async (itemId: string) => {
    if (!editable) return
    const nextItems = goalCalendar.map((item) => (item.id === itemId ? { ...item, completed: !item.completed } : item))
    await onSaveGoalCalendar(nextItems)
  }

  const removeCalendarItem = async (itemId: string) => {
    if (!editable) return
    await onSaveGoalCalendar(goalCalendar.filter((item) => item.id !== itemId))
  }

  return (
    <section className={panelClass(isDark, "p-4 sm:p-5")}>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <PanelTitle isDark={isDark}>Goal Calendar</PanelTitle>
            <span className={`inline-flex items-center rounded-full px-2 py-1 text-[10px] font-semibold ${isDark ? "bg-white/[0.05] text-slate-400" : "bg-slate-100 text-slate-500"}`}>
              {monthCompletedCount}/{monthItemCount || 0} done this month
            </span>
          </div>
          <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>
            Plan writing goals, track quotas, and keep each milestone attached to a day on the board.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {goalChips.map((goal) => (
            <div key={goal.label} className={`rounded-md border px-3 py-2 text-xs ${isDark ? "border-white/[0.08] bg-white/[0.03]" : "border-slate-200 bg-slate-50"}`}>
              <p className={isDark ? "text-slate-500" : "text-slate-400"}>{goal.label}</p>
              <p className={`mt-1 font-semibold ${isDark ? "text-slate-200" : "text-slate-700"}`}>
                {typeof goal.value === "number" && goal.value > 0 ? `${goal.value.toLocaleString()} ${goal.unit}` : "Not set"}
              </p>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-6 grid gap-5 xl:grid-cols-[minmax(0,1.45fr)_minmax(20rem,0.95fr)]">
        <div className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-white/[0.025]" : "border-slate-200/70 bg-slate-50/60"}`}>
          <div className="flex items-center justify-between gap-3">
            <button
              onClick={() => setVisibleMonth((current) => shiftMonthValue(current, -1))}
              aria-label="Show previous month"
              className={`flex h-9 w-9 items-center justify-center rounded-md border transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-300 hover:bg-[#17212d]" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}`}
            >
              <Icon name="chevron" className="h-4 w-4 rotate-180" />
            </button>
            <div className="text-center">
              <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{formatPlannerMonth(visibleMonth)}</p>
              <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>Select a day to review the plan.</p>
            </div>
            <button
              onClick={() => setVisibleMonth((current) => shiftMonthValue(current, 1))}
              aria-label="Show next month"
              className={`flex h-9 w-9 items-center justify-center rounded-md border transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-300 hover:bg-[#17212d]" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}`}
            >
              <Icon name="chevron" className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-4 grid grid-cols-7 gap-2">
            {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((label) => (
              <div key={label} className={`px-1 text-center text-[11px] font-semibold ${isDark ? "text-slate-500" : "text-slate-400"}`}>
                {label}
              </div>
            ))}
            {calendarDays.map((day) => {
              const dayItems = itemsByDate.get(day.value) ?? []
              const completedCount = dayItems.filter((item) => item.completed).length
              const quotaTotal = dayItems.reduce((sum, item) => sum + (item.quota_value ?? 0), 0)
              const selected = day.value === selectedDate
              const isToday = day.value === today

              return (
                <button
                  key={day.value}
                  onClick={() => setSelectedDate(day.value)}
                  className={`min-h-[5.7rem] rounded-md border p-2 text-left transition ${
                    selected
                      ? isDark
                        ? "border-teal-800/25 bg-teal-800/10"
                        : "border-teal-300 bg-teal-50"
                      : isDark
                        ? "border-white/[0.05] bg-[#101720] hover:bg-[#16202b]"
                        : "border-slate-200 bg-white hover:bg-slate-50"
                  } ${!day.inMonth ? (isDark ? "text-slate-600" : "text-slate-300") : ""}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className={`text-sm font-semibold ${selected ? "text-teal-800" : day.inMonth ? (isDark ? "text-slate-200" : "text-slate-700") : ""}`}>{day.label}</span>
                    {isToday ? <span className="rounded-full bg-teal-800 px-1.5 py-0.5 text-[10px] font-semibold text-white">Today</span> : null}
                  </div>
                  <div className="mt-3 space-y-1">
                    {dayItems.length > 0 ? (
                      <>
                        <p className={`text-[11px] font-medium ${isDark ? "text-slate-300" : "text-slate-600"}`}>{dayItems.length} item{dayItems.length === 1 ? "" : "s"}</p>
                        <p className={`text-[10px] ${isDark ? "text-slate-500" : "text-slate-400"}`}>{completedCount}/{dayItems.length} complete</p>
                        {quotaTotal > 0 ? <p className="text-[10px] font-semibold text-teal-800">{quotaTotal.toLocaleString()} quota</p> : null}
                      </>
                    ) : (
                      <p className={`text-[10px] ${isDark ? "text-slate-600" : "text-slate-300"}`}>Open</p>
                    )}
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        <div className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-white/[0.025]" : "border-slate-200/70 bg-slate-50/60"}`}>
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{formatPlannerDate(selectedDate)}</p>
              <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>
                {selectedItems.length > 0 ? `${selectedItems.length} scheduled item${selectedItems.length === 1 ? "" : "s"}` : "No goals scheduled yet."}
              </p>
            </div>
            <div className="text-right">
              <p className={`text-[11px] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Selected quota</p>
              <p className={`mt-1 text-sm font-semibold ${isDark ? "text-slate-200" : "text-slate-700"}`}>{selectedQuotaTotal > 0 ? selectedQuotaTotal.toLocaleString() : "-"}</p>
            </div>
          </div>

          <div className="mt-4 space-y-3">
            {selectedItems.length > 0 ? selectedItems.map((item) => {
              const quotaLabel = formatQuotaLabel(item.quota_value, item.quota_unit)
              const overdue = item.due_date < today && !item.completed
              return (
                <div key={item.id} className={`rounded-md border p-3 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-white"}`}>
                  <div className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      checked={item.completed}
                      disabled={!editable || saveState === "saving"}
                      onChange={() => void toggleCalendarItem(item.id)}
                      className="mt-1 h-4 w-4 rounded border-slate-300 text-teal-800 focus:ring-teal-700"
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className={`text-sm font-semibold ${item.completed ? (isDark ? "text-slate-500 line-through" : "text-slate-400 line-through") : isDark ? "text-slate-200" : "text-slate-700"}`}>
                          {item.title}
                        </p>
                        {quotaLabel ? <span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${isDark ? "bg-teal-800/10 text-teal-200" : "bg-teal-50 text-teal-800"}`}>{quotaLabel}</span> : null}
                        {overdue ? <span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${isDark ? "bg-amber-500/12 text-amber-300" : "bg-amber-50 text-amber-700"}`}>Overdue</span> : null}
                      </div>
                      <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>{item.completed ? "Completed" : "Planned"} for {formatPlannerDate(item.due_date)}</p>
                    </div>
                    <button
                      onClick={() => void removeCalendarItem(item.id)}
                      disabled={!editable || saveState === "saving"}
                      className={`text-xs font-semibold ${isDark ? "text-slate-500 hover:text-rose-300 disabled:text-slate-700" : "text-slate-400 hover:text-rose-600 disabled:text-slate-300"}`}
                    >
                      Remove
                    </button>
                  </div>
                </div>
              )
            }) : (
              <div className={`rounded-md border border-dashed p-4 text-sm ${isDark ? "border-white/[0.08] text-slate-500" : "border-slate-200 text-slate-400"}`}>
                Nothing is scheduled for this day yet.
              </div>
            )}
          </div>

          <div className={`mt-5 rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-[#0d141c]" : "border-slate-200 bg-white"}`}>
            <div className="flex items-center justify-between gap-3">
              <p className={`text-sm font-semibold ${isDark ? "text-slate-200" : "text-slate-700"}`}>Add planning item</p>
              <button
                onClick={() => {
                  setSelectedDate(today)
                  setVisibleMonth(monthValueFromDate(today))
                }}
                className={`text-xs font-semibold ${isDark ? "text-teal-200" : "text-teal-800"}`}
              >
                Jump to today
              </button>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1.2fr)_9rem]">
              <input
                value={draftTitle}
                onChange={(event) => setDraftTitle(event.target.value)}
                disabled={!editable || saveState === "saving"}
                placeholder={editable ? "Draft chapter, revise outline, finish scene..." : "Loading planner..."}
                className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 placeholder:text-slate-600 focus:border-teal-700" : "border-slate-200 bg-white text-slate-900 placeholder:text-slate-400 focus:border-teal-700"}`}
              />
              <input
                type="date"
                value={selectedDate}
                onChange={(event) => setSelectedDate(event.target.value)}
                disabled={!editable || saveState === "saving"}
                className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-teal-700" : "border-slate-200 bg-white text-slate-900 focus:border-teal-700"}`}
              />
            </div>

            <div className="mt-3 grid gap-3 sm:grid-cols-[minmax(0,0.65fr)_minmax(0,0.65fr)_auto]">
              <input
                type="number"
                min="0"
                step="1"
                value={draftQuotaValue}
                onChange={(event) => setDraftQuotaValue(event.target.value)}
                disabled={!editable || saveState === "saving"}
                placeholder="Quota"
                className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 placeholder:text-slate-600 focus:border-teal-700" : "border-slate-200 bg-white text-slate-900 placeholder:text-slate-400 focus:border-teal-700"}`}
              />
              <select
                value={draftQuotaUnit}
                onChange={(event) => setDraftQuotaUnit(event.target.value)}
                disabled={!editable || saveState === "saving"}
                className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-teal-700" : "border-slate-200 bg-white text-slate-900 focus:border-teal-700"}`}
              >
                {["words", "chapters", "scenes", "pages", "tasks"].map((unit) => (
                  <option key={unit} value={unit}>{unit}</option>
                ))}
              </select>
              <button
                onClick={() => void addCalendarItem()}
                disabled={!editable || saveState === "saving" || !draftTitle.trim()}
                className={`inline-flex h-11 items-center justify-center rounded-md px-4 text-sm font-semibold transition ${isDark ? "bg-teal-800 text-white hover:bg-teal-700 disabled:bg-teal-800/35" : "bg-teal-800 text-white hover:bg-teal-800 disabled:bg-teal-300"}`}
              >
                Add item
              </button>
            </div>

            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className={`inline-flex h-2 w-2 rounded-full ${
                  saveState === "error"
                    ? "bg-rose-400"
                    : saveState === "saved"
                      ? "bg-emerald-400"
                      : saveState === "saving"
                        ? "bg-amber-400"
                        : isDark
                          ? "bg-slate-600"
                          : "bg-slate-300"
                }`} />
                <p className={`text-xs ${saveState === "error" ? "text-rose-400" : isDark ? "text-slate-500" : "text-slate-400"}`}>
                  {saveMessage || (editable ? "Changes save back into this book workspace." : "Loading planner...")}
                </p>
              </div>
              <button type="button" onClick={onOpenManuscript} className="text-xs font-semibold text-teal-800">
                Adjust word goals
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

function BookCover({ book, isDark }: { book: Book; isDark: boolean }) {
  const [failed, setFailed] = useState(false)
  const src = !failed ? resolveAssetUrl(book.cover_url) : null

  if (!src) {
    return (
      <div className={`flex aspect-[0.72] min-h-48 items-center justify-center overflow-hidden rounded-md ${isDark ? "bg-[#18202b]" : "bg-slate-100"}`}>
        <span className={`font-serif text-5xl font-bold ${isDark ? "text-white/20" : "text-slate-300"}`}>{titleInitials(book.title)}</span>
      </div>
    )
  }

  return (
    <div className="aspect-[0.72] min-h-48 overflow-hidden rounded-md">
      <img
        src={src}
        alt={`${book.title} cover`}
        loading="lazy"
        decoding="async"
        onError={() => setFailed(true)}
        className="h-full w-full object-cover object-center"
      />
    </div>
  )
}

function CreateFab({
  bookId,
  isDark,
  onAddScene,
  onNavigate,
}: {
  bookId: string
  isDark: boolean
  onAddScene: () => void
  onNavigate: (href: string) => void
}) {
  const itemClass = `rounded-full border px-4 py-2 text-sm font-semibold shadow-[0_18px_44px_-28px_rgba(0,0,0,0.8)] transition ${
    isDark ? "border-white/10 bg-[#17191d] text-slate-100 hover:bg-[#202329]" : "border-slate-200 bg-white text-slate-800 hover:bg-slate-50"
  }`

  return (
    <div className="group/create fixed bottom-24 right-5 z-40 flex flex-col items-end gap-3 lg:bottom-8 lg:right-8">
      <div className="pointer-events-none flex translate-y-2 flex-col items-end gap-2 opacity-0 transition group-hover/create:pointer-events-auto group-hover/create:translate-y-0 group-hover/create:opacity-100 group-focus-within/create:pointer-events-auto group-focus-within/create:translate-y-0 group-focus-within/create:opacity-100">
        <button onClick={onAddScene} className={itemClass}>Add Scene</button>
        <button onClick={() => onNavigate(`/${bookId}/notes`)} className={itemClass}>Add Note</button>
        <button onClick={() => onNavigate(`/${bookId}/characters`)} className={itemClass}>Add Character</button>
      </div>
      <button className={`rounded-full px-5 py-3 text-sm font-semibold shadow-[0_18px_55px_-28px_rgba(0,0,0,0.9)] transition ${isDark ? "bg-teal-800 text-white hover:bg-teal-700" : "bg-teal-800 text-white hover:bg-teal-800"}`}>
        + Create
      </button>
    </div>
  )
}

function PanelTitle({ isDark, children }: { isDark: boolean; children: React.ReactNode }) {
  return <h2 className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{children}</h2>
}

function InfoRow({ label, value, isDark, dot = false }: { label: string; value: string; isDark: boolean; dot?: boolean }) {
  return (
    <div className="grid grid-cols-[7rem_minmax(0,1fr)] items-center gap-3 text-sm">
      <span className={isDark ? "text-slate-500" : "text-slate-400"}>{label}</span>
      <span className={`flex min-w-0 items-center gap-2 font-medium capitalize ${isDark ? "text-slate-300" : "text-slate-700"}`}>
        {dot ? <span className="h-2 w-2 rounded-full bg-emerald-400" /> : null}
        {value}
      </span>
    </div>
  )
}

function IconLink({ href, label, icon, isDark }: { href: Route | string; label: string; icon: IconName; isDark: boolean }) {
  return (
    <Link
      href={href as Route}
      aria-label={label}
      className={`flex h-10 w-10 items-center justify-center rounded-md border transition ${isDark ? "border-white/10 bg-white/[0.04] text-slate-300 hover:bg-white/[0.08]" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}`}
    >
      <Icon name={icon} />
    </Link>
  )
}

function panelClass(isDark: boolean, extra = "") {
  return `rounded-md border shadow-[0_18px_42px_-32px_rgba(15,23,42,0.38)] ${
    isDark ? "border-white/[0.065] bg-[#0d141c]" : "border-slate-200/70 bg-white"
  } ${extra}`
}

function severityClass(severity: string, isDark: boolean) {
  if (severity === "High") return isDark ? "bg-rose-500/10 text-rose-300" : "bg-rose-50 text-rose-600"
  if (severity === "Medium") return isDark ? "bg-amber-500/10 text-amber-300" : "bg-amber-50 text-amber-600"
  return isDark ? "bg-emerald-500/10 text-emerald-300" : "bg-emerald-50 text-emerald-600"
}

function titleInitials(title: string) {
  return title
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("")
}

function Icon({ name, className = "h-4 w-4" }: { name: IconName; className?: string }) {
  const common = { className, fill: "none", viewBox: "0 0 24 24", stroke: "currentColor", strokeWidth: 1.8 }

  switch (name) {
    case "analysis":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M5 19V9M10 19V5M15 19v-7M20 19V8M4 19h17" /></svg>
    case "bell":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M14.9 17H9.1m5.8 0H18l-1.3-1.3a2 2 0 01-.7-1.4V11a4 4 0 10-8 0v3.3a2 2 0 01-.7 1.4L6 17h3.1m5.8 0a3 3 0 11-5.8 0" /></svg>
    case "book":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M6 4h9a3 3 0 013 3v13H8a2 2 0 01-2-2V4zM8 18h10M9 8h5" /></svg>
    case "calendar":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M7 4v3M17 4v3M5 9h14M6 6h12a1 1 0 011 1v12H5V7a1 1 0 011-1z" /></svg>
    case "chat":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M5 6.5A3.5 3.5 0 018.5 3h7A3.5 3.5 0 0119 6.5v4A3.5 3.5 0 0115.5 14H11l-5 5v-5.5A3.5 3.5 0 015 10V6.5zM9 8h6M9 11h4" /></svg>
    case "chevron":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" /></svg>
    case "edit":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M4 20h4l11-11a2.6 2.6 0 10-4-4L4 16v4z" /></svg>
    case "file":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M7 4h8l3 3v13H7V4zM15 4v4h4M9 13h6M9 16h4" /></svg>
    case "flame":
      return <svg className={className} fill="currentColor" viewBox="0 0 24 24"><path d="M12.6 2.2c.5 2.8-.3 4.7-2.2 6.6-1.7 1.7-2.5 3.4-1.8 5.4.4 1.1 1.2 2 2.4 2.6-.3-1.4.2-2.8 1.4-4.1.9 1 1.8 2.2 1.8 4a3.6 3.6 0 01-3.8 3.6c-3.2 0-5.8-2.5-5.8-6.2 0-2.9 1.4-5.2 3.7-7.4 1.7-1.7 2.8-3.1 2.6-4.5h1.7zM14.8 4.8c2.9 2.5 4.6 5.3 4.6 8.7 0 4.7-3.2 8.3-8.1 8.3 3-.9 5.1-3.4 5.1-6.5 0-2.3-1.1-4.1-2.5-5.8.9-1.5 1.3-3 .9-4.7z" /></svg>
    case "gap":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M4 7h7M13 7h7M4 17h7M13 17h7M11 7l2 10" /></svg>
    case "gear":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M12 15.5a3.5 3.5 0 100-7 3.5 3.5 0 000 7z" /><path strokeLinecap="round" strokeLinejoin="round" d="M19 12a7 7 0 00-.1-1l2-1.5-2-3.4-2.4 1a7 7 0 00-1.7-1L14.5 3h-5l-.3 3.1a7 7 0 00-1.7 1l-2.4-1-2 3.4 2 1.5A7 7 0 005 12a7 7 0 00.1 1l-2 1.5 2 3.4 2.4-1a7 7 0 001.7 1l.3 3.1h5l.3-3.1a7 7 0 001.7-1l2.4 1 2-3.4-2-1.5c.1-.3.1-.7.1-1z" /></svg>
    case "graph":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M5 19V9M10 19V5M15 19v-7M20 19V8M4 19h17" /></svg>
    case "moon":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M20 15.5A8 8 0 018.5 4 8.5 8.5 0 1020 15.5z" /></svg>
    case "pen":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M4 20h4l11-11a2.6 2.6 0 10-4-4L4 16v4z" /></svg>
    case "plus":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14M5 12h14" /></svg>
    case "search":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M11 18a7 7 0 100-14 7 7 0 000 14zM16 16l4 4" /></svg>
    case "spark":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3zM18 16l.8 2.2L21 19l-2.2.8L18 22l-.8-2.2L15 19l2.2-.8L18 16z" /></svg>
    case "sun":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M12 4V2M12 22v-2M4 12H2M22 12h-2M5 5l-1.4-1.4M20.4 20.4L19 19M19 5l1.4-1.4M3.6 20.4L5 19M12 16a4 4 0 100-8 4 4 0 000 8z" /></svg>
    case "timeline":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M7 4v16M17 4v16M7 8h10M7 16h10M10 12h4" /></svg>
    case "users":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M9 11a3 3 0 100-6 3 3 0 000 6zM4 19a5 5 0 0110 0M17 11a2.5 2.5 0 100-5M15.5 15.5A4.5 4.5 0 0120 20" /></svg>
    case "voice":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M4 13v-2M8 16V8M12 19V5M16 16V8M20 13v-2" /></svg>
    default:
      return null
  }
}

function WorkspacePanelLoadingState() {
  return (
    <div className="rounded-md border border-border bg-card/60 p-6 text-sm text-muted-foreground">
      Loading workspace tools...
    </div>
  )
}

function NavPanelLoadingState() {
  return <div className="rounded-2xl border border-border bg-card/60 p-4" />
}
