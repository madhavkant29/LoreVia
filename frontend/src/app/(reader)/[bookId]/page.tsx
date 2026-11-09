"use client"

import { startTransition, useEffect, useMemo, useRef, useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import dynamic from "next/dynamic"
import type { Route } from "next"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"

import { ContextualUpgradePrompt } from "@/components/billing/ContextualUpgradePrompt"
import { CreateFab } from "@/components/overview/CreateFab"
import { ActivationExperience } from "@/components/reader/ActivationExperience"
import { ReviewReadyDialog } from "@/components/reader/ReviewReadyDialog"
import { ProfileEnrichmentNotice } from "@/components/reader/ProfileEnrichmentNotice"
import { WorkspaceModeSwitcher } from "@/components/reader/WorkspaceModeSwitcher"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"
import { ErrorCard } from "@/components/ui/ErrorCard"
import { RecentActivityList } from "@/components/ui/RecentActivityList"
import { ProcessingStatusPanel } from "@/components/ui/ResponsivenessStatus"
import { DashboardSkeleton, SidebarSkeleton } from "@/components/ui/Skeleton"
import { VisibilityBadge } from "@/components/ui/VisibilityBadge"
import { captureTiming } from "@/lib/analytics/posthog"
import { booksApi } from "@/lib/api/books"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { asQueryKey, bookCacheKey, booksQuotesCacheKey, booksStatsCacheKey, readerCacheKey } from "@/lib/query/cacheKeys"
import { useAuthStore } from "@/lib/stores/authStore"
import { useBookModeStore } from "@/lib/stores/bookModeStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { getBookRouteSegment, normalizeBookRouteId } from "@/lib/utils/bookRoutes"
import {
  getProcessingSummary,
  normalizeProcessingStatus,
  storyUnitName,
  storyUnitPrefix,
  storyUnitTitle,
} from "@/lib/utils/processingStatus"
import { buildGoalCalendarSavePatch, findRevisionTaskSource, patchRevisionIntelligenceItem } from "@/lib/utils/revisionIntelligence"
import type { BookOverviewPayload, GoalCalendarItem, ReaderBootstrapPayload, RevisionIntelligence, UserStats, WriterWorkspace } from "@/types/book"
import type { RecentActivityItem } from "@/types/ux"

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

const FREE_FEATURE_GATE_FLASH_PREFIX = "lorevia:free-feature-gate:"

type WorkspaceSaveState = "idle" | "saving" | "saved" | "error"

type ReaderBookmarkSnapshot = {
  chapter: number
  chapterTitle: string | null
  scrollPct: number
  savedAt: string
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

export default function BookOverviewPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const normalizedBookId = normalizeBookRouteId(bookId)
  const [bookmark, setBookmark] = useState<ReaderBookmarkSnapshot | null>(null)
  const [secondaryDataEnabled, setSecondaryDataEnabled] = useState(false)
  const [workspaceSaveState, setWorkspaceSaveState] = useState<WorkspaceSaveState>("idle")
  const [workspaceSaveMessage, setWorkspaceSaveMessage] = useState<string | null>(null)
  const [featureGateMessage, setFeatureGateMessage] = useState<string | null>(null)
  const [modeSaving, setModeSaving] = useState(false)
  const [processingRetrying, setProcessingRetrying] = useState(false)
  const [processingError, setProcessingError] = useState<string | null>(null)
  const [modeError, setModeError] = useState<string | null>(null)
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
      const startedAt = typeof performance !== "undefined" ? performance.now() : 0
      const bootstrap: ReaderBootstrapPayload = await booksApi.getReaderBootstrap(bookId, { profile: "critical" })
      captureTiming("reader_bootstrap_ms", startedAt, { book_id: bookId })
      const payload = bootstrap.overview
      const fullBootstrap = bootstrap.profile !== "critical"
      if (typeof window !== "undefined") {
        window.sessionStorage.setItem(`book-route-segment:${normalizeBookRouteId(bookId)}`, getBookRouteSegment(payload.book))
      }
      queryClient.setQueryData(bookQueryKey, payload.book)
      queryClient.setQueryData(asQueryKey(readerCacheKey(bookId, "progress")), payload.progress)
      queryClient.setQueryData(asQueryKey(readerCacheKey(bookId, "chapters")), payload.chapter_list)
      queryClient.setQueryData(asQueryKey(readerCacheKey(bookId, "summary-collection")), payload.summary_collection)
      if (fullBootstrap) {
        queryClient.setQueryData(asQueryKey(bookCacheKey(bookId, "notes")), bootstrap.notes)
        queryClient.setQueryData(asQueryKey(booksQuotesCacheKey()), bootstrap.saved_quotes)
        if (bootstrap.stats) queryClient.setQueryData(asQueryKey(booksStatsCacheKey()), bootstrap.stats)
        queryClient.setQueryData(asQueryKey(bookCacheKey(bookId, "characters")), bootstrap.characters)
        queryClient.setQueryData(asQueryKey(bookCacheKey(bookId, "chapter-reports:6")), bootstrap.chapter_reports)
        if (bootstrap.prewriting_check) queryClient.setQueryData(asQueryKey(bookCacheKey(bookId, "pre-writing:auto")), bootstrap.prewriting_check)
        if (bootstrap.story_health) queryClient.setQueryData(asQueryKey(bookCacheKey(bookId, "story-health")), bootstrap.story_health)
        if (bootstrap.writer_workspace) queryClient.setQueryData(writerWorkspaceQueryKey, bootstrap.writer_workspace)
        if (bootstrap.revision_intelligence) queryClient.setQueryData(asQueryKey(bookCacheKey(bookId, "revision-intelligence")), bootstrap.revision_intelligence)
      }
      return payload
    },
    staleTime: 20_000,
    refetchInterval: (query) => {
      const currentBook = (query.state.data as BookOverviewPayload | undefined)?.book
      return currentBook && currentBook.status !== "ready" ? 3_000 : false
    },
    refetchIntervalInBackground: false,
  })

  const resolvedBookMode = overviewQuery.data?.book.workspace_shell ?? overviewQuery.data?.book.mode ?? bookMode
  const resolvedCollaborationPermissions = overviewQuery.data?.book.collaboration_permissions ?? null
  const resolvedCanSwitchWorkspaceMode = overviewQuery.data?.book.can_switch_workspace_mode ?? true
  const hasOwnAuthorAccess = canUseAuthorFeatures(userTier)
  const canUsePaidAuthorTools = hasOwnAuthorAccess || Boolean(resolvedCollaborationPermissions?.can_edit_manuscript)
  const bookNotesQuery = useQuery({
    queryKey: asQueryKey(bookCacheKey(bookId, "notes")),
    queryFn: () => booksApi.getBookNotes(bookId),
    staleTime: 20_000,
    enabled: secondaryDataEnabled && (resolvedBookMode === "reader" || !canUsePaidAuthorTools),
  })
  const savedQuotesQuery = useQuery({
    queryKey: asQueryKey(booksQuotesCacheKey()),
    queryFn: () => booksApi.listQuotes(),
    staleTime: 45_000,
    enabled: secondaryDataEnabled && (resolvedBookMode === "reader" || !canUsePaidAuthorTools),
  })
  const userStatsQuery = useQuery<UserStats>({
    queryKey: asQueryKey(booksStatsCacheKey()),
    queryFn: booksApi.getStats,
    staleTime: 45_000,
    enabled: secondaryDataEnabled && resolvedBookMode === "author" && canUsePaidAuthorTools,
  })
  const charactersQuery = useQuery({
    queryKey: asQueryKey(bookCacheKey(bookId, "characters:count")),
    queryFn: () => booksApi.getCharacters(bookId, { fields: ["id"] }),
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
  const savedQuotes = (savedQuotesQuery.data ?? []).filter((quote) => quote.book_id === normalizedBookId)
  const userStats = userStatsQuery.data ?? null
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
    const nextShell = book?.workspace_shell ?? book?.mode
    if (nextShell === "reader" || nextShell === "author") {
      setBookMode(bookId, nextShell)
    }
  }, [book?.mode, book?.workspace_shell, bookId, setBookMode])

  useEffect(() => {
    if (!overviewQuery.isSuccess || !overviewQuery.data || overviewReadyCaptured.current) return
    overviewReadyCaptured.current = true
    captureTiming("reader_first_paint_ms", overviewLoadStartedAt.current ?? 0, {
      book_id: bookId,
      active_mode: overviewQuery.data.book.workspace_shell ?? overviewQuery.data.book.mode,
      critical_request_count: 1,
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
    const currentWindow = window
    let scrollRestoreTimeout: number | null = null

    const gateMessageKey = `${FREE_FEATURE_GATE_FLASH_PREFIX}${normalizedBookId}`
    const gateMessage = currentWindow.sessionStorage.getItem(gateMessageKey)
    if (gateMessage) {
      setFeatureGateMessage(gateMessage)
      currentWindow.sessionStorage.removeItem(gateMessageKey)
    }

    const saved = currentWindow.sessionStorage.getItem(overviewScrollKey)
    if (saved) {
      const nextY = Number(saved)
      if (!Number.isNaN(nextY)) {
        scrollRestoreTimeout = currentWindow.setTimeout(
          () => currentWindow.scrollTo({ top: nextY, behavior: "auto" }),
          40,
        )
      }
    }

    const saveScroll = () => {
      currentWindow.sessionStorage.setItem(overviewScrollKey, String(currentWindow.scrollY))
    }

    saveScroll()
    currentWindow.addEventListener("scroll", saveScroll, { passive: true })
    return () => {
      if (scrollRestoreTimeout !== null) currentWindow.clearTimeout(scrollRestoreTimeout)
      currentWindow.removeEventListener("scroll", saveScroll)
    }
  }, [normalizedBookId, overviewScrollKey])

  const continueChapter = progress?.current_chapter ?? 1
  const percentComplete = Math.round(progress?.percent_complete ?? book?.progress_pct ?? 0)
  const chaptersLeft = progress?.chapters_left ?? book?.chapters_left ?? 0
  const activeBookMode = book?.workspace_shell ?? book?.mode ?? bookMode
  const collaborationRole = book?.collaboration_role ?? null
  const collaborationPermissions = book?.collaboration_permissions ?? null
  const canSwitchWorkspaceMode = book?.can_switch_workspace_mode ?? resolvedCanSwitchWorkspaceMode
  const isCollaboratorSession = Boolean(collaborationRole)
  const hasCollaboratorAuthorAccess = Boolean(collaborationPermissions?.can_edit_manuscript)
  const canUseAuthorWorkspace = isCollaboratorSession ? hasCollaboratorAuthorAccess : hasOwnAuthorAccess
  const canEditSharedManuscript = canUsePaidAuthorTools
  const isLimitedAuthorOwner = book?.mode === "author" && book.access_class === "owner" && !hasOwnAuthorAccess
  const shouldShowAuthorWorkspace = activeBookMode === "author" && canUsePaidAuthorTools
  const processingSummary = getProcessingSummary(book)
  const normalizedProcessingStatus = normalizeProcessingStatus(book?.processing, book)
  const showActivationExperience = Boolean(
    shouldShowAuthorWorkspace
      && revisionIntelligence?.activation
      && !revisionIntelligence.activation.completed
      && (!normalizedProcessingStatus || normalizedProcessingStatus.ready),
  )
  const unitTitle = storyUnitTitle(book?.work_type)
  const unitPrefix = storyUnitPrefix(book?.work_type)
  const chapters = chapterList?.chapters ?? []
  const chapterCount = chapters.length || book?.total_chapters || null
  const configuredTargetWords = writerWorkspace?.word_count_goals.book_target
  const currentWords = typeof book?.total_words === "number" && book.total_words >= 0 ? book.total_words : null
  const targetWords = typeof configuredTargetWords === "number" && configuredTargetWords > 0 ? configuredTargetWords : null
  const dailyTarget = Math.max(1, user?.daily_word_goal ?? 1000)
  const dailyWords = Math.max(0, user?.today_word_count ?? 0)
  const loginStreakDays = Math.max(0, user?.login_streak_days ?? 0)
  const weeklyLoginActivity = getCurrentWeekActivity(user?.login_activity_dates ?? [])
  const continuityIssueCount = chapterReports.reduce((sum, report) => sum + report.continuity_flags.length, 0)
  const worldGapCount = preWritingCheck?.alerts.length ?? 0
  const worldItemCount = Math.max(0, overviewQuery.data?.world_stats?.total_items ?? 0)
  const timelineIssueCount = (revisionIntelligence?.priority_findings ?? []).filter((finding) => {
    if (finding.is_stale || ["fixed", "ignored"].includes(finding.status)) return false
    return /timeline|temporal|chronolog|sequence|date|time/.test(finding.category.toLowerCase())
  }).length
  const greetingName = authHydrated ? user?.username?.trim() || "there" : "there"
  const overviewActivityItems = useMemo<RecentActivityItem[]>(() => {
    const items: RecentActivityItem[] = []
    if (processingSummary && book?.status !== "ready") {
      items.push({
        id: "processing",
        label: "Processing status updated",
        detail: processingSummary,
        tone: book?.status === "failed" ? "danger" : book?.status === "processing" ? "warning" : "default",
      })
    }
    items.push({
      id: "progress",
      label: `${percentComplete}% read`,
      detail: `${chaptersLeft} ${storyUnitName(book?.work_type, chaptersLeft !== 1)} left from the current reading progress.`,
      href: `/${bookId}/chapter/${continueChapter}` as Route,
    })
    if (revisionIntelligence?.summary?.recent_edit_label) {
      items.push({
        id: "revision",
        label: "Revision digest",
        detail: revisionIntelligence.summary.recent_edit_label,
        href: "/notifications" as Route,
        tone: "warning",
      })
    }
    if (continuityIssueCount > 0) {
      items.push({
        id: "continuity",
        label: `${continuityIssueCount} continuity flags`,
        detail: "Open Story Advisor to triage the current draft.",
        href: `/${bookId}/advisor` as Route,
        tone: "warning",
      })
    }
    return items
  }, [book?.status, book?.work_type, bookId, chaptersLeft, continuityIssueCount, continueChapter, percentComplete, processingSummary, revisionIntelligence])

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

  const saveGoalCalendar = async (goalCalendar: GoalCalendarItem[]) => {
    if (!writerWorkspace) return false
    const { patch, removedTaskIds } = buildGoalCalendarSavePatch(writerWorkspace, goalCalendar)
    const saved = await saveWorkspacePatch(
      patch,
      {
        saving: "Saving planner...",
        success: "Planner saved.",
        error: "Could not save planner changes.",
      }
    )
    if (saved && removedTaskIds.length > 0) {
      const revisionKey = asQueryKey(bookCacheKey(bookId, "revision-intelligence"))
      queryClient.setQueryData<RevisionIntelligence | undefined>(revisionKey, (current) => {
        if (!current) return current
        return removedTaskIds.reduce((updated, taskId) => {
          const source = findRevisionTaskSource(updated, taskId)
          return source
            ? patchRevisionIntelligenceItem(updated, source.id, {
                task_id: null,
                status: source.status === "task_created" ? "pending" : source.status,
              })
            : updated
        }, current)
      })
    }
    return saved
  }

  const continueReading = () => {
    navigateWithMemory(`/${bookId}/chapter/${continueChapter}`)
  }

  const openAddSceneFlow = () => {
    navigateWithMemory(`/${bookId}/manuscript?newScene=1`)
  }

  const openRelationships = () => {
    navigateWithMemory(`/${bookId}/graph`)
  }

  const retryProcessing = async () => {
    if (!book) return
    setProcessingRetrying(true)
    setProcessingError(null)
    try {
      const processing = normalizedProcessingStatus?.resumeAvailable
        ? await booksApi.continueProcessing(book.id)
        : await booksApi.retryProcessing(book.id)
      queryClient.setQueryData(overviewQueryKey, (current: BookOverviewPayload | undefined) => (
        current ? { ...current, book: { ...current.book, status: "processing", processing } } : current
      ))
      await overviewQuery.refetch()
    } catch {
      setProcessingError("Processing could not be restarted. Check your connection and try again.")
    } finally {
      setProcessingRetrying(false)
    }
  }

  const updateMode = async (nextMode: "reader" | "author") => {
    if (modeSaving) return
    if (nextMode === activeBookMode) return
    if (!canSwitchWorkspaceMode) return
    if (nextMode === "author" && !canUseAuthorWorkspace) return
    const previousBook = book
    startTransition(() => setBookMode(bookId, nextMode))
    setModeSaving(true)
    setModeError(null)
    if (previousBook) {
      queryClient.setQueryData(bookQueryKey, { ...previousBook, workspace_shell: nextMode, mode: nextMode })
      queryClient.setQueryData(overviewQueryKey, (current: BookOverviewPayload | undefined) => (
        current ? { ...current, book: { ...current.book, workspace_shell: nextMode, mode: nextMode } } : current
      ))
    }
    try {
      const updated = await booksApi.setMode(bookId, nextMode)
      queryClient.setQueryData(bookQueryKey, updated)
      queryClient.setQueryData(overviewQueryKey, (current: BookOverviewPayload | undefined) => (
        current ? { ...current, book: updated } : current
      ))
    } catch {
      setModeError("The workspace could not be changed. Your previous workspace has been restored. Try switching again.")
      startTransition(() => setBookMode(bookId, previousBook?.workspace_shell ?? previousBook?.mode ?? bookMode))
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

  if (overviewQuery.isError && !book) {
    return (
      <div className="min-h-screen bg-background text-foreground">
        <div className="mx-auto max-w-[100rem] px-4 pt-10 sm:px-6 lg:px-8">
          <ErrorCard
            title="Failed to load book overview"
            message="Something went wrong while loading this book. Check your connection and try again."
            onRetry={() => overviewQuery.refetch()}
            isDark={isDark}
            variant="full"
          />
        </div>
      </div>
    )
  }

  if (!book) {
    return (
      <div className="min-h-screen bg-background text-foreground">
        <div className="mx-auto grid max-w-[100rem] gap-5 px-4 pb-28 pt-5 sm:px-6 lg:grid-cols-[15.5rem_minmax(0,1fr)] lg:px-8 xl:gap-6">
          <div className="hidden lg:block lg:sticky lg:top-5 lg:self-start">
            <NavPanelLoadingState />
          </div>
          <main className="min-w-0" role="status" aria-label="Loading book overview" aria-busy="true">
            <DashboardSkeleton />
          </main>
        </div>
      </div>
    )
  }

  return (
    <div data-book-overview className="min-h-screen bg-background text-foreground">
      <ReviewReadyDialog book={book} bookId={bookId} enabled={shouldShowAuthorWorkspace} hasReviewMaterial={chapterReports.length > 0} />
      <div className="mx-auto max-w-[100rem] space-y-5 px-4 pb-28 pt-5 sm:px-6 lg:px-8 xl:space-y-6">
        <AuthorToolsNav
          bookId={bookId}
          active="overview"
          isDark={isDark}
          bookData={book}
          title={activeBookMode === "author" ? "Author workspace" : "Reader workspace"}
          currentChapter={continueChapter}
          mode={activeBookMode}
          variant="bar"
        />

        <main className="min-w-0 space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <VisibilityBadge
              state={book?.is_public || book?.public_status === "published" ? "public_sample" : isCollaboratorSession ? "shared" : "private"}
            />
            <div className="flex items-center gap-2">
              {showActivationExperience ? (
                <WorkspaceModeSwitcher
                  isDark={isDark}
                  activeMode={activeBookMode}
                  modeSaving={modeSaving}
                  writingAvailable={canUseAuthorWorkspace && canSwitchWorkspaceMode}
                  onModeChange={updateMode}
                />
              ) : null}
              <button type="button" onClick={() => window.dispatchEvent(new CustomEvent(SUPPORT_HELP_EVENT))} className="min-h-10 rounded-sm border border-border px-3 text-sm font-medium">Help</button>
              {shouldShowAuthorWorkspace && canEditSharedManuscript ? <CreateFab inline bookId={bookId} isDark={isDark} onAddScene={openAddSceneFlow} onNavigate={navigateWithMemory} /> : null}
            </div>
          </div>
          {modeError ? <p role="alert" className="border-l-2 border-amber-500 px-3 py-2 text-sm text-amber-900 dark:text-amber-200">{modeError}</p> : null}
          {processingError ? <p role="alert" className="border-l-2 border-amber-500 px-3 py-2 text-sm text-amber-900 dark:text-amber-200">{processingError}</p> : null}
          {overviewQuery.isError ? <ErrorCard variant="compact" isDark={isDark} message="The overview could not be refreshed. Showing the last loaded information." onRetry={() => overviewQuery.refetch()} /> : null}
          <ProfileEnrichmentNotice processing={book?.processing} bookId={bookId} isDark={isDark} onReview={() => navigateWithMemory(`/${bookId}/characters`)} />
          <ProcessingStatusPanel
            status={normalizedProcessingStatus}
            retrying={processingRetrying}
            onRetry={normalizedProcessingStatus?.retryAvailable || normalizedProcessingStatus?.resumeAvailable ? () => void retryProcessing() : undefined}
          />

          {featureGateMessage ? (
            <ContextualUpgradePrompt
              featureName="Manuscript Editor"
              body={featureGateMessage}
              onBack={() => setFeatureGateMessage(null)}
            />
          ) : null}

          {!featureGateMessage && isLimitedAuthorOwner ? (
            <ContextualUpgradePrompt
              featureName="Manuscript Editor"
              body="Author drafting tools are locked on the Free plan. You can still read the project, review existing notes, and compare plans when you are ready to continue editing."
            />
          ) : null}

          {!shouldShowAuthorWorkspace ? (
            <ReaderOverview
              bookId={bookId}
              book={book}
              activeBookMode="reader"
              progress={progress}
              chapterList={chapterList}
              summaryCollection={summaryCollection}
              bookNotes={bookNotes}
              savedQuotes={savedQuotes}
              savedItemsLoading={bookNotesQuery.isPending || savedQuotesQuery.isPending}
              savedItemsError={bookNotesQuery.isError || savedQuotesQuery.isError}
              onRetrySavedItems={() => { void bookNotesQuery.refetch(); void savedQuotesQuery.refetch() }}
              bookmark={bookmark}
              isDark={isDark}
              modeSaving={modeSaving}
              canUseAuthorMode={canUseAuthorWorkspace && canSwitchWorkspaceMode}
              greetingName={greetingName}
              onModeChange={updateMode}
              onToggleTheme={toggleTheme}
              onNavigate={navigateWithMemory}
              onContinueReading={continueReading}
            />
          ) : showActivationExperience && revisionIntelligence ? (
            <ActivationExperience
              bookId={bookId}
              bookCreatedAt={book?.created_at}
              bookTitle={book?.title ?? "your manuscript"}
              bookWorkType={book?.work_type}
              chapterCount={chapterCount ?? 0}
              isDark={isDark}
              revision={revisionIntelligence}
              enableFirstImpression={book?.access_class === "owner" && ["novel", "screenplay"].includes(book?.work_type ?? "novel")}
              onNavigate={navigateWithMemory}
              onRevisionChange={(nextRevision) => {
                queryClient.setQueryData(asQueryKey(bookCacheKey(bookId, "revision-intelligence")), nextRevision)
              }}
            />
          ) : (
            <AuthorWorkspaceDashboard
              bookId={bookId}
              book={book}
              isDark={isDark}
              activeBookMode={activeBookMode}
              canUseAuthorMode={canUseAuthorWorkspace && canSwitchWorkspaceMode}
              modeSaving={modeSaving}
              greetingName={greetingName}
              canOpenManuscript={canEditSharedManuscript}
              currentWords={currentWords}
              targetWords={targetWords}
              percentComplete={percentComplete}
              chapters={chapters}
              summaryCollection={summaryCollection}
              unitTitle={unitTitle}
              unitPrefix={unitPrefix}
              storyHealth={storyHealth}
              preWritingCheck={preWritingCheck}
              revisionIntelligence={revisionIntelligence}
              writerWorkspace={writerWorkspace}
              continuityIssueCount={chapterReportsQuery.data ? continuityIssueCount : null}
              worldGapCount={preWritingCheck ? worldGapCount : null}
              timelineIssueCount={revisionIntelligence ? timelineIssueCount : null}
              processingSummary={book.status === "ready" ? null : processingSummary}
              chapterCount={chapterCount}
              characterCount={characters.length}
              worldArticleCount={worldItemCount}
              loginStreakDays={loginStreakDays}
              weeklyLoginActivity={weeklyLoginActivity}
              dailyWords={dailyWords}
              dailyTarget={dailyTarget}
              userStats={userStats}
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
              storyHealthError={storyHealthQuery.isError}
              onRetryStoryHealth={() => storyHealthQuery.refetch()}
              preWritingCheckError={preWritingCheckQuery.isError}
              onRetryPreWritingCheck={() => preWritingCheckQuery.refetch()}
              revisionIntelligenceError={revisionIntelligenceQuery.isError}
              onRetryRevisionIntelligence={() => revisionIntelligenceQuery.refetch()}
              writerWorkspaceError={writerWorkspaceQuery.isError}
              onRetryWriterWorkspace={() => writerWorkspaceQuery.refetch()}
            />
          )}
          <details className="border-y border-border py-3">
            <summary className="cursor-pointer text-sm font-semibold">Project signals</summary>
            <RecentActivityList title="Latest updates" items={overviewActivityItems} emptyLabel="No project signals yet. Start writing or reading to see your activity here." variant="compact" />
          </details>
        </main>
      </div>


      <nav aria-label="Book shortcuts" data-lorevia-bottom-floating className="fixed inset-x-0 bottom-0 z-30 border-t border-slate-200 bg-card px-4 py-3 dark:border-white/10 dark:bg-background lg:hidden">
        <div className="mx-auto grid max-w-xl grid-cols-3 gap-1 text-center text-xs sm:grid-cols-6 font-medium text-muted-foreground">
          <Link href={`/${bookId}`} aria-current="page" className="min-h-10 rounded-sm bg-teal-50 px-2 py-2 text-teal-800 dark:bg-teal-950 dark:text-teal-200">Overview</Link>
          <button onClick={continueReading} className="min-h-10 rounded-sm px-2 py-2">Read</button>
          <Link href={`/${bookId}/chapters`} className="min-h-10 rounded-sm px-2 py-2">Chapters</Link>
          <Link href={`/${bookId}/notes`} className="min-h-10 rounded-sm px-2 py-2">Notes</Link>
          {activeBookMode === "author" ? (
            <button onClick={openRelationships} className="min-h-10 rounded-sm px-2 py-2">Graph</button>
          ) : (
            <Link href={`/${bookId}/timeline`} className="min-h-10 rounded-sm px-2 py-2">Timeline</Link>
          )}
          <Link href="/library" className="min-h-10 rounded-sm px-2 py-2">Library</Link>
        </div>
      </nav>
    </div>
  )
}

function WorkspacePanelLoadingState() {
  return <DashboardSkeleton />
}

function NavPanelLoadingState() {
  return <SidebarSkeleton />
}
