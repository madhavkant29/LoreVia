"use client"

import React, { Suspense, useDeferredValue, useEffect, useMemo, useState } from "react"
import type { Route } from "next"
import Link from "next/link"

import { RevisionIntelligencePanel } from "@/components/revision/RevisionIntelligencePanel"
import { CoverEditOverlay } from "@/components/ui/CoverEditOverlay"
import { ErrorCard } from "@/components/ui/ErrorCard"
import { Skeleton } from "@/components/ui/Skeleton"
import { buildIssueDisplay } from "@/lib/utils/storyFeedback"
import { SmartBookCover } from "@/components/ui/SmartBookCover"
import type { Book, GoalCalendarItem, PreWritingCheck, RevisionActionItem, RevisionIntelligence, StoryHealth, WriterWorkspace } from "@/types/book"
import type { ChapterListResponse } from "@/types/reader"

type IconName =
  | "analysis"
  | "book"
  | "calendar"
  | "chat"
  | "chevron"
  | "edit"
  | "file"
  | "flame"
  | "gap"
  | "graph"
  | "moon"
  | "pen"
  | "search"
  | "spark"
  | "sun"
  | "timeline"
  | "users"
  | "voice"

type WorkspaceSaveState = "idle" | "saving" | "saved" | "error"
type AuthorDashboardTab = "overview" | "revision" | "planning" | "story-map" | "stats"
type RevisionInsightSelection = { key: string; title: string; subtitle: string; items: RevisionActionItem[] }
type RevisionSeverityFilter = "all" | "high" | "medium" | "low"

type Props = {
  bookId: string
  book: Book
  isDark: boolean
  activeBookMode: "reader" | "author"
  canUseAuthorMode: boolean
  modeSaving: boolean
  greetingName: string
  canOpenManuscript: boolean
  currentWords: number | null
  targetWords: number
  percentComplete: number
  chapters: ChapterListResponse["chapters"]
  unitTitle: string
  unitPrefix: string
  storyHealth: StoryHealth | null
  preWritingCheck: PreWritingCheck | null
  revisionIntelligence: RevisionIntelligence | null
  writerWorkspace: WriterWorkspace | null
  continuityIssueCount: number
  worldGapCount: number
  timelineIssueCount: number
  processingSummary: string | null
  chapterCount: number | null
  characterCount: number
  worldArticleCount: number
  loginStreakDays: number
  weeklyLoginActivity: boolean[]
  dailyWords: number
  dailyTarget: number
  saveState: WorkspaceSaveState
  saveMessage: string | null
  storyHealthError?: boolean
  onRetryStoryHealth?: () => void
  preWritingCheckError?: boolean
  onRetryPreWritingCheck?: () => void
  revisionIntelligenceError?: boolean
  onRetryRevisionIntelligence?: () => void
  writerWorkspaceError?: boolean
  onRetryWriterWorkspace?: () => void
  onModeChange: (nextMode: "reader" | "author") => void
  onToggleTheme: () => void
  onNavigate: (href: string) => void
  onOpenManuscript: () => void
  onOpenRelationships: () => void
  onSaveGoalCalendar: (goalCalendar: GoalCalendarItem[]) => Promise<boolean>
  onRevisionChange: (revision: RevisionIntelligence) => void
  onWriterWorkspaceChange: (workspace: WriterWorkspace) => void
}

export function AuthorWorkspaceDashboard({
  bookId,
  book,
  isDark,
  activeBookMode,
  canUseAuthorMode,
  modeSaving,
  greetingName,
  canOpenManuscript,
  currentWords,
  targetWords,
  percentComplete,
  chapters,
  unitTitle,
  unitPrefix,
  storyHealth,
  preWritingCheck,
  revisionIntelligence,
  writerWorkspace,
  continuityIssueCount,
  worldGapCount,
  timelineIssueCount,
  processingSummary,
  chapterCount,
  characterCount,
  worldArticleCount,
  loginStreakDays,
  weeklyLoginActivity,
  dailyWords,
  dailyTarget,
  saveState,
  saveMessage,
  storyHealthError,
  onRetryStoryHealth,
  preWritingCheckError,
  onRetryPreWritingCheck,
  revisionIntelligenceError,
  onRetryRevisionIntelligence,
  writerWorkspaceError,
  onRetryWriterWorkspace,
  onModeChange,
  onToggleTheme,
  onNavigate,
  onOpenManuscript,
  onOpenRelationships,
  onSaveGoalCalendar,
  onRevisionChange,
  onWriterWorkspaceChange,
}: Props) {
  const [activeTab, setActiveTab] = useState<AuthorDashboardTab>("overview")
  const [coverUrlOverride, setCoverUrlOverride] = useState<string | null>(null)
  const deferedBookCoverUrl = coverUrlOverride !== null ? coverUrlOverride : book.cover_url
  const deferredStoryHealth = useDeferredValue(storyHealth)
  const deferredPreWritingCheck = useDeferredValue(preWritingCheck)
  const deferredRevisionIntelligence = useDeferredValue(revisionIntelligence)
  const deferredWriterWorkspace = useDeferredValue(writerWorkspace)
  const recentAlerts = preWritingCheck?.alerts ?? []
  const quickLinks = [
    { title: "Story Advisor", body: "Ask for revision guidance and continuity checks.", href: `/${bookId}/advisor`, icon: "graph" as IconName },
    { title: "Ask LoreVia", body: "Search the manuscript memory without leaving the workspace.", href: `/${bookId}/ask`, icon: "chat" as IconName },
    { title: "Character Graph", body: "Open the relationship map for cast-level context.", href: `/${bookId}/graph`, icon: "users" as IconName },
    { title: "Timeline", body: "Review event order and pressure points.", href: `/${bookId}/timeline`, icon: "timeline" as IconName },
  ]
  const totalRevisionItems = deferredRevisionIntelligence?.summary.active_item_count ?? continuityIssueCount + worldGapCount + timelineIssueCount
  const highSeverityItems = deferredRevisionIntelligence?.summary.high_severity_count ?? continuityIssueCount

  return (
    <div className="space-y-4">
      <OverviewHeader
        isDark={isDark}
        activeBookMode={activeBookMode}
        canUseAuthorMode={canUseAuthorMode}
        modeSaving={modeSaving}
        greetingName={greetingName}
        onModeChange={onModeChange}
        onToggleTheme={onToggleTheme}
      />

      <section className="grid gap-5 xl:auto-rows-fr xl:grid-cols-[minmax(0,1.32fr)_minmax(18rem,0.86fr)_minmax(17.5rem,0.82fr)]">
        <CurrentProjectCard
          book={book}
          isDark={isDark}
          canOpenManuscript={canOpenManuscript}
          currentWords={currentWords}
          targetWords={targetWords}
          percentComplete={percentComplete}
          dailyWords={dailyWords}
          dailyTarget={dailyTarget}
          loginStreakDays={loginStreakDays}
          onOpenManuscript={onOpenManuscript}
          onOpenRelationships={onOpenRelationships}
          onNavigate={onNavigate}
          bookId={bookId}
          resolvedCoverUrl={deferedBookCoverUrl}
          onCoverUpdated={(updated) => setCoverUrlOverride(updated.cover_url ?? null)}
        />
        <RecentChaptersCard
          book={book}
          isDark={isDark}
          chapters={chapters}
          unitTitle={unitTitle}
          unitPrefix={unitPrefix}
          onNavigate={onNavigate}
          bookId={bookId}
        />
        <StoryPulseCard
          bookId={bookId}
          isDark={isDark}
          storyHealth={deferredStoryHealth}
          storyHealthError={storyHealthError}
          onRetryStoryHealth={onRetryStoryHealth}
        />
      </section>

      <Suspense fallback={<Skeleton variant="card" className="min-h-72" />}>
        <section className="grid gap-5 xl:auto-rows-fr xl:grid-cols-[minmax(18rem,0.92fr)_minmax(0,1.12fr)_minmax(17rem,0.8fr)]">
        <ActiveIssuesCard
          isDark={isDark}
          continuityIssueCount={continuityIssueCount}
          worldGapCount={worldGapCount}
          timelineIssueCount={timelineIssueCount}
          onNavigate={onNavigate}
          bookId={bookId}
          processingSummary={processingSummary}
        />
        {deferredRevisionIntelligence ? (
          <RevisionIntelligencePanel
            bookId={bookId}
            revision={deferredRevisionIntelligence}
            writerWorkspace={deferredWriterWorkspace}
            isDark={isDark}
            onRevisionChange={onRevisionChange}
            onWriterWorkspaceChange={onWriterWorkspaceChange}
            variant="preview"
          />
        ) : (
          <RevisionPreviewPlaceholder isDark={isDark} />
        )}
        <div className="grid auto-rows-fr gap-5">
          <CompactQuickLinksCard isDark={isDark} links={quickLinks} onNavigate={onNavigate} />
          <RecentSignalsCard
            isDark={isDark}
            unitTitle={unitTitle}
            recentAlerts={recentAlerts}
            chapters={chapters}
            onNavigate={onNavigate}
            bookId={bookId}
            preWritingCheckError={preWritingCheckError}
            onRetryPreWritingCheck={onRetryPreWritingCheck}
          />
        </div>
      </section>
      </Suspense>

      <section className={panelClass(isDark, "overflow-hidden p-4 sm:p-5")} data-testid="author-workspace-tabs">
        <div className="grid gap-4 border-b border-white/[0.06] pb-4 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1fr)] lg:items-end">
          <div>
            <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Secondary workspace</p>
            <h2 className={`mt-2 font-serif text-3xl leading-none ${isDark ? "text-white" : "text-slate-900"}`}>
              {activeTab === "planning" ? "Plan with intent. Write with momentum." : "Your author command center."}
            </h2>
            <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-slate-500"}`}>
              {activeTab === "planning"
                ? "Align goals, schedule sessions, and protect the manuscript from drift."
                : "Deep tools for planning, structure, and story intelligence."}
            </p>
          </div>
          <div role="tablist" aria-label="Author workspace tabs" className={`grid gap-1 rounded-md border p-1 sm:grid-cols-3 xl:grid-cols-5 ${isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-slate-50"}`}>
            {([
              ["overview", "Overview"],
              ["revision", "Revision Hub"],
              ["planning", "Planning"],
              ["story-map", "Story Map"],
              ["stats", "Workspace Stats"],
            ] as const).map(([tab, label]) => (
              <button
                key={tab}
                type="button"
                role="tab"
                aria-selected={activeTab === tab}
                onClick={() => setActiveTab(tab)}
                className={`rounded-xl px-3 py-2.5 text-xs font-semibold transition focus:outline-none focus:ring-2 focus:ring-teal-500/60 ${
                  activeTab === tab
                    ? "bg-teal-800 text-white"
                    : isDark ? "text-slate-300 hover:bg-white/[0.06]" : "text-slate-600 hover:bg-white"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-5">
          {activeTab === "overview" ? (
            <AuthorOverviewTab
              isDark={isDark}
              currentWords={currentWords}
              targetWords={targetWords}
              chapterCount={chapterCount}
              characterCount={characterCount}
              worldArticleCount={worldArticleCount}
              percentComplete={percentComplete}
              dailyWords={dailyWords}
              dailyTarget={dailyTarget}
              loginStreakDays={loginStreakDays}
              weeklyLoginActivity={weeklyLoginActivity}
              totalRevisionItems={totalRevisionItems}
              highSeverityItems={highSeverityItems}
              chapters={chapters}
              unitTitle={unitTitle}
              onNavigate={onNavigate}
              onOpenManuscript={onOpenManuscript}
              bookId={bookId}
            />
          ) : null}

          {activeTab === "revision" ? (
            <RevisionHubTab
              bookId={bookId}
              isDark={isDark}
              revisionIntelligence={deferredRevisionIntelligence}
              writerWorkspace={deferredWriterWorkspace}
              chapters={chapters}
              storyHealth={deferredStoryHealth}
              onRevisionChange={onRevisionChange}
              onWriterWorkspaceChange={onWriterWorkspaceChange}
              revisionIntelligenceError={revisionIntelligenceError}
              onRetryRevisionIntelligence={onRetryRevisionIntelligence}
              writerWorkspaceError={writerWorkspaceError}
              onRetryWriterWorkspace={onRetryWriterWorkspace}
              storyHealthError={storyHealthError}
              onRetryStoryHealth={onRetryStoryHealth}
            />
          ) : null}

          {activeTab === "planning" ? (
            <PlanningTab
              isDark={isDark}
              writerWorkspace={deferredWriterWorkspace}
              currentWords={currentWords}
              targetWords={targetWords}
              chapterCount={chapterCount}
              dailyWords={dailyWords}
              dailyTarget={dailyTarget}
              loginStreakDays={loginStreakDays}
              saveState={saveState}
              saveMessage={saveMessage}
              onSaveGoalCalendar={onSaveGoalCalendar}
              onOpenManuscript={onOpenManuscript}
              writerWorkspaceError={writerWorkspaceError}
              onRetryWriterWorkspace={onRetryWriterWorkspace}
            />
          ) : null}

          {activeTab === "story-map" ? (
            <StoryMapTab
              isDark={isDark}
              bookId={bookId}
              preWritingCheck={deferredPreWritingCheck}
              revisionIntelligence={deferredRevisionIntelligence}
              onOpenRelationships={onOpenRelationships}
              onNavigate={onNavigate}
              preWritingCheckError={preWritingCheckError}
              onRetryPreWritingCheck={onRetryPreWritingCheck}
              revisionIntelligenceError={revisionIntelligenceError}
              onRetryRevisionIntelligence={onRetryRevisionIntelligence}
            />
          ) : null}

          {activeTab === "stats" ? (
            <WorkspaceStatsTab
              isDark={isDark}
              currentWords={currentWords}
              targetWords={targetWords}
              chapterCount={chapterCount}
              characterCount={characterCount}
              worldArticleCount={worldArticleCount}
              percentComplete={percentComplete}
              chapters={chapters}
              dailyWords={dailyWords}
              dailyTarget={dailyTarget}
              loginStreakDays={loginStreakDays}
              weeklyLoginActivity={weeklyLoginActivity}
              onOpenManuscript={onOpenManuscript}
            />
          ) : null}
        </div>
      </section>
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
    <section className={panelClass(isDark, "overflow-hidden p-4 sm:p-5")}>
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div className="min-w-0">
          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-teal-200/80" : "text-teal-800"}`}>Author workspace</p>
          <h1 className={`mt-2 font-serif text-3xl leading-none sm:text-4xl ${isDark ? "text-white" : "text-slate-900"}`}>
            Welcome back, {greetingName}.
          </h1>
          <p className={`mt-3 max-w-3xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
            Drafting, revision pressure, and story memory now live in one calmer workspace.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {canUseAuthorMode ? (
            <ModeToggle
              isDark={isDark}
              activeMode={activeBookMode}
              modeSaving={modeSaving}
              onModeChange={onModeChange}
            />
          ) : null}

          <button
            type="button"
            onClick={onToggleTheme}
            className={`flex h-11 w-11 items-center justify-center rounded-full border transition ${isDark ? "border-white/10 bg-white/[0.04] text-slate-200 hover:bg-white/[0.08]" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"}`}
            aria-label={`Switch to ${isDark ? "light" : "dark"} mode`}
          >
            <Icon name={isDark ? "sun" : "moon"} />
          </button>
        </div>
      </div>
    </section>
  )
}

function CurrentProjectCard({
  book,
  isDark,
  canOpenManuscript,
  currentWords,
  targetWords,
  percentComplete,
  dailyWords,
  dailyTarget,
  loginStreakDays,
  onOpenManuscript,
  onOpenRelationships,
  onNavigate,
  bookId,
  resolvedCoverUrl,
  onCoverUpdated,
}: {
  book: Book
  isDark: boolean
  canOpenManuscript: boolean
  currentWords: number | null
  targetWords: number
  percentComplete: number
  dailyWords: number
  dailyTarget: number
  loginStreakDays: number
  onOpenManuscript: () => void
  onOpenRelationships: () => void
  onNavigate: (href: string) => void
  bookId: string
  resolvedCoverUrl: string | null | undefined
  onCoverUpdated: (book: Book) => void
}) {
  const goalProgress = clamp((dailyWords / Math.max(1, dailyTarget)) * 100, 0, 100)
  const manuscriptProgress = clamp(percentComplete || (currentWords ? (currentWords / targetWords) * 100 : 0), 0, 100)
  const etaDays = currentWords && dailyTarget > 0 ? Math.max(1, Math.ceil(Math.max(0, targetWords - currentWords) / dailyTarget)) : null
  const etaDate = etaDays ? new Date(Date.now() + etaDays * 24 * 60 * 60 * 1000).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "Syncing"

  return (
    <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Current project</p>
      <div className="mt-4 grid gap-5 md:grid-cols-[9rem_minmax(0,1fr)] xl:grid-cols-[10rem_minmax(0,1fr)]">
        <SmartBookCover
          src={resolvedCoverUrl}
          title={book.title}
          isDark={isDark}
          className="aspect-[0.72] min-h-48 overflow-hidden rounded-lg"
          overlay={
            <CoverEditOverlay
              bookId={bookId}
              isDark={isDark}
              hasCover={Boolean(resolvedCoverUrl)}
              onCoverUpdated={onCoverUpdated}
            />
          }
        />
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className={`break-words text-2xl font-semibold tracking-tight sm:text-3xl ${isDark ? "text-white" : "text-slate-950"}`}>{book.title}</h2>
            <span className="text-xs font-semibold text-teal-600">{book.work_type === "screenplay" ? "Screenplay" : "Manuscript"}</span>
          </div>
          <p className={`mt-3 max-w-xl break-words text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
            {book.public_description?.trim() || `The draft is ${Math.round(manuscriptProgress)}% complete, with the next pass centered on pacing, continuity, and scene-by-scene momentum.`}
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            {canOpenManuscript ? (
              <button
                type="button"
                onClick={onOpenManuscript}
                className={`inline-flex min-h-11 items-center gap-2 rounded-md px-5 py-2.5 text-sm font-semibold transition ${isDark ? "bg-teal-800 text-white hover:bg-teal-700" : "bg-teal-800 text-white hover:bg-teal-700"}`}
              >
                <Icon name="book" />
                Open Manuscript Editor
                <Icon name="chevron" />
              </button>
            ) : null}
            <button type="button" onClick={onOpenRelationships} className={secondaryButtonClass(isDark)}>
              <Icon name="users" />
              Open relationship map
            </button>
            <button type="button" onClick={() => onNavigate(`/${bookId}/summaries`)} className={secondaryButtonClass(isDark)}>
              <Icon name="search" />
              Open summaries
            </button>
          </div>
        </div>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <HeroMetric isDark={isDark} label="Draft progress" value={`${formatNumber(currentWords)} / ${targetWords.toLocaleString()}`} note={`${Math.round(manuscriptProgress)}% of target`} progress={manuscriptProgress} />
        <HeroMetric isDark={isDark} label="Daily target" value={`${dailyWords.toLocaleString()} / ${dailyTarget.toLocaleString()}`} note="Today's quota" progress={goalProgress} />
        <HeroMetric isDark={isDark} label="Writing rhythm" value={`${loginStreakDays} day${loginStreakDays === 1 ? "" : "s"}`} note="Current streak" progress={Math.min(100, loginStreakDays * 12)} />
        <HeroMetric isDark={isDark} label="Est. completion" value={etaDate} note={etaDays ? `In ${etaDays} day${etaDays === 1 ? "" : "s"}` : "Add a daily goal"} progress={etaDays ? clamp(100 - etaDays, 6, 100) : 0} />
      </div>
    </section>
  )
}

function RecentChaptersCard({
  book,
  isDark,
  chapters,
  unitTitle,
  unitPrefix,
  onNavigate,
  bookId,
}: {
  book: Book
  isDark: boolean
  chapters: ChapterListResponse["chapters"]
  unitTitle: string
  unitPrefix: string
  onNavigate: (href: string) => void
  bookId: string
}) {
  const recentChapters = chapters.slice(-3).reverse()

  return (
    <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Recent chapters</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <StatusPill isDark={isDark} label={book.status === "ready" ? "Drafting" : book.status.replace(/_/g, " ")} tone="violet" />
            <StatusPill isDark={isDark} label={`${chapters.length} indexed ${unitTitle.toLowerCase()}${chapters.length === 1 ? "" : "s"}`} tone="slate" />
          </div>
        </div>
        <button type="button" onClick={() => onNavigate(`/${bookId}/manuscript`)} className="text-xs font-semibold text-teal-600">
          Open draft
        </button>
      </div>
      <div className="mt-5 space-y-3">
        {recentChapters.length > 0 ? recentChapters.map((chapter) => (
          <button
            key={chapter.number}
            type="button"
            onClick={() => onNavigate(`/${bookId}/chapter/${chapter.number}`)}
            className={`flex w-full items-start justify-between gap-3 rounded-md border px-4 py-3 text-left transition ${isDark ? "border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06]" : "border-slate-200 bg-white hover:bg-slate-50"}`}
          >
            <div className="min-w-0">
              <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>{unitPrefix} {chapter.number}</p>
              <p className={`mt-1 break-words text-sm font-medium leading-6 ${isDark ? "text-slate-100" : "text-slate-800"}`}>{chapter.title || `${unitTitle} ${chapter.number}`}</p>
              <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>{chapter.read ? "Opened recently" : "Ready to draft"}</p>
            </div>
            <span className="text-xs font-semibold text-teal-600">{chapter.read ? "Read" : "Open"}</span>
          </button>
        )) : (
          <p className={`rounded-md border border-dashed px-4 py-6 text-sm ${isDark ? "border-white/[0.08] text-slate-500" : "border-slate-200 text-slate-400"}`}>
            {unitTitle} indexing is still syncing.
          </p>
        )}
      </div>
      <button type="button" onClick={() => onNavigate(`/${bookId}/chapters`)} className={footerLinkClass(isDark)}>
        View all chapters <Icon name="chevron" />
      </button>
    </section>
  )
}

function CurrentProjectHero({
  book,
  isDark,
  canOpenManuscript,
  currentWords,
  targetWords,
  percentComplete,
  chapters,
  unitTitle,
  unitPrefix,
  dailyWords,
  dailyTarget,
  loginStreakDays,
  onOpenManuscript,
  onOpenRelationships,
  onNavigate,
  bookId,
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
  dailyWords: number
  dailyTarget: number
  loginStreakDays: number
  onOpenManuscript: () => void
  onOpenRelationships: () => void
  onNavigate: (href: string) => void
  bookId: string
}) {
  const recentChapters = chapters.slice(-3).reverse()
  const goalProgress = clamp((dailyWords / Math.max(1, dailyTarget)) * 100, 0, 100)
  const manuscriptProgress = clamp(percentComplete || (currentWords ? (currentWords / targetWords) * 100 : 0), 0, 100)

  return (
    <section className={panelClass(isDark, "overflow-hidden px-5 py-5 sm:px-6 sm:py-6")}>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_22rem]">
        <div className="grid gap-6 lg:grid-cols-[11rem_minmax(0,1fr)]">
          <div className="space-y-4">
            <SmartBookCover
              src={book.cover_url}
              title={book.title}
              isDark={isDark}
              className="aspect-[0.72] min-h-48 overflow-hidden rounded-lg"
            />
            <button
              type="button"
              onClick={onOpenRelationships}
              className={`inline-flex w-full items-center justify-center gap-2 rounded-md border px-4 py-3 text-sm font-semibold transition ${isDark ? "border-white/10 bg-white/[0.04] text-slate-100 hover:bg-white/[0.08]" : "border-slate-200 bg-white text-slate-800 hover:bg-slate-50"}`}
            >
              <Icon name="users" />
              Open relationship map
            </button>
          </div>

          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`rounded-full px-3 py-1 text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "bg-teal-800/10 text-teal-100" : "bg-teal-50 text-teal-800"}`}>
                Current project
              </span>
              <span className={isDark ? "text-xs text-slate-500" : "text-xs text-slate-400"}>
                {book.genre || (book.work_type === "screenplay" ? "Screenplay" : "Manuscript")}
              </span>
            </div>
            <div className="mt-4 flex items-start gap-2">
              <div className="min-w-0">
                <h2 className={`text-3xl font-semibold tracking-tight sm:text-4xl ${isDark ? "text-white" : "text-slate-950"}`}>{book.title}</h2>
                <p className={`mt-2 text-base ${isDark ? "text-slate-300" : "text-slate-600"}`}>
                  The draft is {manuscriptProgress}% complete, with the next pass centered on pacing, continuity, and scene-by-scene momentum.
                </p>
              </div>
              <Icon name="edit" className={isDark ? "mt-1 h-5 w-5 text-slate-500" : "mt-1 h-5 w-5 text-slate-400"} />
            </div>

            <div className="mt-6 flex flex-wrap gap-3">
              {canOpenManuscript ? (
                <button
                  type="button"
                  onClick={onOpenManuscript}
                  className={`inline-flex min-h-12 items-center gap-2 rounded-md px-5 py-3 text-sm font-semibold transition ${isDark ? "bg-teal-800 text-white hover:bg-teal-700" : "bg-teal-800 text-white hover:bg-teal-800"}`}
                >
                  <Icon name="book" />
                  Open manuscript editor
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => onNavigate(`/${bookId}/chapters`)}
                className={`inline-flex min-h-12 items-center gap-2 rounded-md border px-5 py-3 text-sm font-semibold transition ${isDark ? "border-white/10 bg-white/[0.04] text-slate-100 hover:bg-white/[0.08]" : "border-slate-200 bg-white text-slate-800 hover:bg-slate-50"}`}
              >
                <Icon name="file" />
                Review chapters
              </button>
              <button
                type="button"
                onClick={() => onNavigate(`/${bookId}/summaries`)}
                className={`inline-flex min-h-12 items-center gap-2 rounded-md border px-5 py-3 text-sm font-semibold transition ${isDark ? "border-white/10 bg-white/[0.04] text-slate-100 hover:bg-white/[0.08]" : "border-slate-200 bg-white text-slate-800 hover:bg-slate-50"}`}
              >
                <Icon name="search" />
                Open summaries
              </button>
            </div>

            <div className="mt-7 grid gap-4 sm:grid-cols-3">
              <HeroMetric
                isDark={isDark}
                label="Draft progress"
                value={`${formatNumber(currentWords)} / ${targetWords.toLocaleString()}`}
                note={`${manuscriptProgress}% of target`}
                progress={manuscriptProgress}
              />
              <HeroMetric
                isDark={isDark}
                label="Daily target"
                value={`${dailyWords.toLocaleString()} / ${dailyTarget.toLocaleString()}`}
                note={dailyWords >= dailyTarget ? "Goal reached today" : `${Math.round(goalProgress)}% of today's quota`}
                progress={goalProgress}
              />
              <HeroMetric
                isDark={isDark}
                label="Writing rhythm"
                value={`${loginStreakDays} day${loginStreakDays === 1 ? "" : "s"}`}
                note="Current streak"
                progress={Math.min(100, loginStreakDays * 10)}
              />
            </div>
          </div>
        </div>

        <div className={`rounded-lg border p-4 ${isDark ? "border-white/[0.06] bg-black/20" : "border-slate-200 bg-slate-50/80"}`}>
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className={`text-3xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Recent chapters</p>
              <p className={`mt-1 text-sm ${isDark ? "text-slate-300" : "text-slate-600"}`}>Keep the current run of scenes in view.</p>
            </div>
            <button type="button" onClick={() => onNavigate(`/${bookId}/manuscript`)} className="text-xs font-semibold text-teal-700">
              Open draft
            </button>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <StatusPill isDark={isDark} label={book.status === "ready" ? "Drafting" : book.status.replace(/_/g, " ")} tone="violet" />
            <StatusPill isDark={isDark} label={`${chapters.length} indexed ${unitTitle.toLowerCase()}${chapters.length === 1 ? "" : "s"}`} tone="slate" />
          </div>

          <div className="mt-4 space-y-3">
            {recentChapters.length > 0 ? recentChapters.map((chapter) => (
              <button
                key={chapter.number}
                type="button"
                onClick={() => onNavigate(`/${bookId}/chapter/${chapter.number}`)}
                className={`flex w-full items-start justify-between gap-3 rounded-md border px-4 py-3 text-left transition ${isDark ? "border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06]" : "border-slate-200 bg-white hover:bg-slate-50"}`}
              >
                <div className="min-w-0">
                  <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>{unitPrefix} {chapter.number}</p>
                  <p className={`mt-1 break-words text-sm font-medium leading-6 ${isDark ? "text-slate-100" : "text-slate-800"}`}>{chapter.title || `${unitTitle} ${chapter.number}`}</p>
                </div>
                <span className={`rounded-full px-2 py-1 text-3xs font-semibold ${chapter.read ? (isDark ? "bg-emerald-500/12 text-emerald-200" : "bg-emerald-50 text-emerald-700") : (isDark ? "bg-white/10 text-slate-300" : "bg-slate-100 text-slate-600")}`}>
                  {chapter.read ? "Read" : "Open"}
                </span>
              </button>
            )) : (
              <p className={`rounded-md border border-dashed px-4 py-6 text-sm ${isDark ? "border-white/[0.08] text-slate-500" : "border-slate-200 text-slate-400"}`}>
                {unitTitle} indexing is still syncing.
              </p>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}

function StoryPulseCard({
  bookId,
  isDark,
  storyHealth,
  storyHealthError,
  onRetryStoryHealth,
}: {
  bookId: string
  isDark: boolean
  storyHealth: StoryHealth | null
  storyHealthError?: boolean
  onRetryStoryHealth?: () => void
}) {
  const [selectedMetricLabel, setSelectedMetricLabel] = useState<string | null>(null)
  if (storyHealthError && !storyHealth && onRetryStoryHealth) {
    return (
      <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
        <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Story pulse</p>
        <div className="mt-4">
          <ErrorCard
            message="Failed to load story health"
            onRetry={onRetryStoryHealth}
            variant="compact"
            isDark={isDark}
          />
        </div>
      </section>
    )
  }

  const score = storyHealth?.score ?? 0
  const status = storyHealth?.status ?? "Syncing"
  const summary = storyHealth?.summary ?? "LoreVia is still building the latest story pulse."
  const healthColor = score >= 85 ? "#45d483" : score >= 70 ? "#8b5cf6" : score >= 55 ? "#f5bf3d" : "#fb7185"
  const topMetrics = (storyHealth?.metrics ?? []).slice(0, 3)
  const selectedMetric = topMetrics.find((metric) => metric.label === selectedMetricLabel) ?? null

  return (
    <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Story pulse</p>
          <h2 className={`mt-2 text-lg font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Key metrics only.</h2>
        </div>
        <span className={`rounded-full px-3 py-1 text-3xs font-semibold ${isDark ? "bg-white/[0.05] text-slate-300" : "bg-slate-100 text-slate-600"}`}>{status}</span>
      </div>

      <div className="mt-5 flex items-center gap-4">
        <div
          className="relative flex h-24 w-24 items-center justify-center rounded-full"
          style={{ background: `conic-gradient(${healthColor} 0 ${score}%, ${isDark ? "#1b2430" : "#edf0f5"} ${score}% 100%)` }}
        >
          <div className={`flex h-[4.6rem] w-[4.6rem] flex-col items-center justify-center rounded-full ${isDark ? "bg-[#0d141c]" : "bg-white"}`}>
            <span className={`text-2xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{score}</span>
            <span className={`text-3xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>health</span>
          </div>
        </div>
        <p className={`min-w-0 break-words text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{summary}</p>
      </div>

      <div className="mt-5 space-y-3">
        {topMetrics.map((metric) => (
          <button
            key={metric.label}
            type="button"
            onClick={() => setSelectedMetricLabel((current) => current === metric.label ? null : metric.label)}
            className={`w-full rounded-md border px-4 py-3 text-left transition ${isDark ? "border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06]" : "border-slate-200 bg-white hover:bg-slate-50"} ${selectedMetricLabel === metric.label ? (isDark ? "ring-1 ring-sky-400/60" : "ring-1 ring-sky-500/50") : ""}`}
          >
            <div className="flex items-center justify-between gap-3">
              <span className={isDark ? "min-w-0 break-words text-sm text-slate-200" : "min-w-0 break-words text-sm text-slate-700"}>{metric.label}</span>
              <span className="text-sm font-semibold text-teal-700">{metric.score}%</span>
            </div>
          </button>
        ))}
      </div>

      {selectedMetric ? (
        <div className={`mt-4 rounded-md border px-4 py-3 ${isDark ? "border-sky-400/30 bg-sky-500/10" : "border-sky-200 bg-sky-50"}`}>
          <p className={`text-sm font-semibold ${isDark ? "text-sky-100" : "text-sky-800"}`}>{selectedMetric.label}: {selectedMetric.score}%</p>
          <p className={`mt-2 text-xs leading-5 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{selectedMetric.detail}</p>
        </div>
      ) : null}

      <Link
        href={`/${bookId}/analysis` as Route}
        className={`mt-5 inline-flex w-full items-center justify-center rounded-md border px-4 py-3 text-sm font-semibold transition ${
          isDark ? "border-white/10 bg-white/[0.04] text-teal-200 hover:bg-white/[0.08]" : "border-slate-200 bg-white text-teal-800 hover:bg-slate-50"
        }`}
      >
        View full report
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
  processingSummary,
}: {
  isDark: boolean
  continuityIssueCount: number
  worldGapCount: number
  timelineIssueCount: number
  onNavigate: (href: string) => void
  bookId: string
  processingSummary: string | null
}) {
  const issues = [
    { title: "Character Inconsistencies", rawCount: continuityIssueCount, severity: "High", icon: "users" as IconName, href: `/${bookId}/reports` },
    { title: "World Gaps", rawCount: worldGapCount, severity: "Medium", icon: "gap" as IconName, href: `/${bookId}/world-gap` },
    { title: "Timeline Conflicts", rawCount: timelineIssueCount, severity: "Low", icon: "timeline" as IconName, href: `/${bookId}/timeline` },
  ].map((issue) => ({
    ...issue,
    ...buildIssueDisplay(issue.rawCount),
  }))

  return (
      <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Next actions</p>
            <h2 className={`mt-2 text-xl font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Keep the risky parts visible.</h2>
          </div>
          <Icon name="spark" className="h-5 w-5 text-teal-700" />
        </div>

        <p className={`mt-4 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
          Keep revision fallout visible before it reaches readers.
        </p>

        {processingSummary ? (
          <p className={`mt-4 rounded-md border px-4 py-3 text-sm leading-6 ${isDark ? "border-white/[0.06] bg-white/[0.03] text-slate-300" : "border-slate-200 bg-slate-50 text-slate-600"}`}>
            {processingSummary}
          </p>
        ) : null}

        <button
          type="button"
          onClick={() => onNavigate(`/${bookId}/reports`)}
          className={`mt-4 inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-semibold transition ${isDark ? "bg-teal-800 text-white hover:bg-teal-700" : "bg-teal-800 text-white hover:bg-teal-700"}`}
        >
          Create revision checklist
        </button>

        <div className="mt-4 space-y-3">
        {issues.map((issue) => (
          <button
            key={issue.title}
            type="button"
            onClick={() => onNavigate(issue.href)}
            className={`flex w-full items-center gap-3 rounded-md border px-4 py-3 text-left transition ${isDark ? "border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06]" : "border-slate-200 bg-white hover:bg-slate-50"}`}
          >
            <Icon name={issue.icon} className="h-5 w-5 text-teal-700" />
            <div className="min-w-0 flex-1">
              <p className={`break-words text-sm font-semibold leading-6 ${isDark ? "text-slate-100" : "text-slate-800"}`}>{issue.title}</p>
              <p className={`mt-1 break-words text-xs leading-5 ${isDark ? "text-slate-500" : "text-slate-400"}`}>{issue.label}</p>
            </div>
            <span className={`rounded-full px-2 py-1 text-3xs font-semibold ${severityClass(issue.severity, isDark)}`}>{issue.severity}</span>
          </button>
        ))}
      </div>
    </section>
  )
}

function CompactQuickLinksCard({
  isDark,
  links,
  onNavigate,
}: {
  isDark: boolean
  links: Array<{ title: string; body: string; href: string; icon: IconName }>
  onNavigate: (href: string) => void
}) {
  return (
    <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Workspace links</p>
      <div className="mt-4 space-y-3">
        {links.map((link) => (
          <button
            key={link.title}
            type="button"
            onClick={() => onNavigate(link.href)}
            className={`flex w-full items-start gap-3 rounded-md border px-4 py-3 text-left transition ${isDark ? "border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06]" : "border-slate-200 bg-white hover:bg-slate-50"}`}
          >
            <Icon name={link.icon} className="mt-0.5 h-5 w-5 text-teal-700" />
            <div className="min-w-0">
              <p className={`break-words text-sm font-semibold ${isDark ? "text-slate-100" : "text-slate-800"}`}>{link.title}</p>
              <p className={`mt-1 break-words text-xs leading-5 ${isDark ? "text-slate-500" : "text-slate-400"}`}>{link.body}</p>
            </div>
          </button>
        ))}
      </div>
    </section>
  )
}

function RecentSignalsCard({
  isDark,
  unitTitle,
  recentAlerts,
  chapters,
  onNavigate,
  bookId,
  preWritingCheckError,
  onRetryPreWritingCheck,
}: {
  isDark: boolean
  unitTitle: string
  recentAlerts: PreWritingCheck["alerts"]
  chapters: ChapterListResponse["chapters"]
  onNavigate: (href: string) => void
  bookId: string
  preWritingCheckError?: boolean
  onRetryPreWritingCheck?: () => void
}) {
  const recentEntries = useMemo(() => {
    const chapterSignals = chapters.slice(-2).reverse().map((chapter) => ({
      title: `${unitTitle} ${chapter.number}: ${chapter.title || `${unitTitle} ${chapter.number}`}`,
      note: chapter.read ? "Recently opened" : "Ready to review",
      href: `/${bookId}/chapter/${chapter.number}`,
    }))

    return [
      ...recentAlerts.slice(0, 2).map((alert) => ({
        title: alert.title,
        note: alert.chapter_ref ? `Chapter ${alert.chapter_ref}` : "Author alert",
        href: `/${bookId}/analysis`,
      })),
      ...chapterSignals,
    ].slice(0, 4)
  }, [bookId, chapters, recentAlerts, unitTitle])

  if (preWritingCheckError && recentAlerts.length === 0 && chapters.length === 0 && onRetryPreWritingCheck) {
    return (
      <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
        <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Recent signals</p>
        <div className="mt-4">
          <ErrorCard
            message="Failed to load recent signals"
            onRetry={onRetryPreWritingCheck}
            variant="compact"
            isDark={isDark}
          />
        </div>
      </section>
    )
  }

  return (
    <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Recent signals</p>
      <div className="mt-4 space-y-3">
        {recentEntries.length > 0 ? recentEntries.map((entry) => (
          <button
            key={`${entry.title}-${entry.note}`}
            type="button"
            onClick={() => onNavigate(entry.href)}
            className={`w-full rounded-md border px-4 py-3 text-left transition ${isDark ? "border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06]" : "border-slate-200 bg-white hover:bg-slate-50"}`}
          >
              <p className={`break-words text-sm font-medium leading-6 ${isDark ? "text-slate-100" : "text-slate-800"}`}>{entry.title}</p>
              <p className={`mt-1 break-words text-xs leading-5 ${isDark ? "text-slate-500" : "text-slate-400"}`}>{entry.note}</p>
            </button>
        )) : (
          <p className={isDark ? "text-sm text-slate-500" : "text-sm text-slate-400"}>Signals will appear here as the workspace syncs.</p>
        )}
      </div>
    </section>
  )
}

function AuthorOverviewTab({
  isDark,
  currentWords,
  targetWords,
  chapterCount,
  characterCount,
  worldArticleCount,
  percentComplete,
  dailyWords,
  dailyTarget,
  loginStreakDays,
  weeklyLoginActivity,
  totalRevisionItems,
  highSeverityItems,
  chapters,
  unitTitle,
  onNavigate,
  onOpenManuscript,
  bookId,
}: {
  isDark: boolean
  currentWords: number | null
  targetWords: number
  chapterCount: number | null
  characterCount: number
  worldArticleCount: number
  percentComplete: number
  dailyWords: number
  dailyTarget: number
  loginStreakDays: number
  weeklyLoginActivity: boolean[]
  totalRevisionItems: number
  highSeverityItems: number
  chapters: ChapterListResponse["chapters"]
  unitTitle: string
  onNavigate: (href: string) => void
  onOpenManuscript: () => void
  bookId: string
}) {
  const manuscriptProgress = clamp(percentComplete || (currentWords ? (currentWords / targetWords) * 100 : 0), 0, 100)
  const latestChapter = chapters[chapters.length - 1]

  return (
    <div className="grid gap-5 xl:auto-rows-fr xl:grid-cols-[minmax(0,0.86fr)_minmax(0,0.92fr)_minmax(0,1fr)]">
      <ProjectOverviewCard
        isDark={isDark}
        currentWords={currentWords}
        chapterCount={chapterCount}
        characterCount={characterCount}
        worldArticleCount={worldArticleCount}
      />
      <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
        <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>At a glance</p>
        <div className="mt-5 space-y-3">
          <CompactProgressRow isDark={isDark} label="Draft progress" value={`${Math.round(manuscriptProgress)}%`} percent={manuscriptProgress} />
          <CompactProgressRow isDark={isDark} label="Daily quota" value={`${dailyWords.toLocaleString()} / ${dailyTarget.toLocaleString()}`} percent={(dailyWords / dailyTarget) * 100} />
          <CompactProgressRow isDark={isDark} label="Revision pressure" value={`${totalRevisionItems} active`} percent={clamp(totalRevisionItems * 8, 0, 100)} tone="amber" />
          <InfoLine isDark={isDark} label="Last written" value={latestChapter ? `${unitTitle} ${latestChapter.number}` : "Syncing"} />
          <button type="button" onClick={() => onNavigate(`/${bookId}/reports`)} className={footerLinkClass(isDark)}>
            View workspace stats <Icon name="chevron" />
          </button>
        </div>
      </section>
      <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
        <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Up next</p>
        <div className="mt-5 space-y-3">
          <ActionRow isDark={isDark} icon="pen" title="Continue writing" body={latestChapter ? `${unitTitle} ${latestChapter.number}` : "Open manuscript"} onClick={onOpenManuscript} />
          <ActionRow isDark={isDark} icon="timeline" title="Review high severity risks" body={`${highSeverityItems} item${highSeverityItems === 1 ? "" : "s"} need attention`} onClick={() => onNavigate(`/${bookId}/analysis`)} tone="amber" />
          <ActionRow isDark={isDark} icon="analysis" title="Run story health scan" body="Open the current report" onClick={() => onNavigate(`/${bookId}/analysis`)} tone="teal" />
          <div className="pt-2">
            <WritingStreakCard isDark={isDark} streakDays={loginStreakDays} weekActivity={weeklyLoginActivity} compact />
          </div>
        </div>
      </section>
    </div>
  )
}

function RevisionHubTab({
  bookId,
  isDark,
  revisionIntelligence,
  writerWorkspace,
  chapters,
  storyHealth,
  onRevisionChange,
  onWriterWorkspaceChange,
  revisionIntelligenceError,
  onRetryRevisionIntelligence,
  writerWorkspaceError,
  onRetryWriterWorkspace,
  storyHealthError,
  onRetryStoryHealth,
}: {
  bookId: string
  isDark: boolean
  revisionIntelligence: RevisionIntelligence | null
  writerWorkspace: WriterWorkspace | null
  chapters: ChapterListResponse["chapters"]
  storyHealth: StoryHealth | null
  onRevisionChange: (revision: RevisionIntelligence) => void
  onWriterWorkspaceChange: (workspace: WriterWorkspace) => void
  revisionIntelligenceError?: boolean
  onRetryRevisionIntelligence?: () => void
  writerWorkspaceError?: boolean
  onRetryWriterWorkspace?: () => void
  storyHealthError?: boolean
  onRetryStoryHealth?: () => void
}) {
  const [selectedInsight, setSelectedInsight] = useState<RevisionInsightSelection | null>(null)
  const [chapterSeverityFilter, setChapterSeverityFilter] = useState<RevisionSeverityFilter>("all")
  const [selectedChapterKey, setSelectedChapterKey] = useState<string | null>(null)
  const [selectedRevisionItemId, setSelectedRevisionItemId] = useState<string | null>(null)
  const [chapterFindingsHighlighted, setChapterFindingsHighlighted] = useState(false)

  // Compute derived data before early returns to ensure hooks can be used consistently
  const allItems = revisionIntelligence
    ? [
        ...revisionIntelligence.change_impacts,
        ...revisionIntelligence.scene_advice,
        ...revisionIntelligence.confusion_map,
        ...revisionIntelligence.voice_alerts,
      ]
    : []

  const timelineItems = allItems.filter((item) =>
    [item.title, item.description, item.recommendation, item.source_label]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .match(/\btimeline\b|\border\b|\bsequence\b|\btransition\b|\bearlier\b|\blater\b|\bbefore\b|\bafter\b/)
  )

  const focusCards: RevisionInsightSelection[] = revisionIntelligence
    ? [
        {
          key: "continuity",
          title: "Continuity & logic",
          subtitle: "Downstream logic, contradictions, and dependency breaks LoreVia surfaced.",
          items: revisionIntelligence.change_impacts,
        },
        {
          key: "character",
          title: "Character consistency",
          subtitle: "Voice, behavior, and point-of-view consistency checks LoreVia flagged.",
          items: revisionIntelligence.voice_alerts,
        },
        {
          key: "world",
          title: "Worldbuilding gaps",
          subtitle: "Lore and anchoring issues that may leave the reader under-oriented.",
          items: revisionIntelligence.confusion_map,
        },
        {
          key: "timeline",
          title: "Timeline / order",
          subtitle: "Ordering, transition, and chronology issues surfaced across the current revision set.",
          items: timelineItems,
        },
      ]
    : []

  const filteredChapterItems = allItems.filter((item) =>
    chapterSeverityFilter === "all" ? true : item.severity === chapterSeverityFilter
  )

  const chaptersByNumber = new Map(chapters.map((chapter) => [chapter.number, chapter]))
  const visibleChapterNumbers = chapters.slice(-5).map((chapter) => chapter.number)
  const referencedChapterNumbers = filteredChapterItems
    .map((item) => item.chapter_ref)
    .filter((chapterNumber): chapterNumber is number => typeof chapterNumber === "number")
  const chapterNumbers = [...new Set([...visibleChapterNumbers, ...referencedChapterNumbers])].sort((left, right) => right - left)
  const chapterFindings: Array<{
    key: string
    chapterNumber: number | null
    title: string
    subtitle: string
    items: RevisionActionItem[]
  }> = chapterNumbers.map((chapterNumber) => {
    const chapter = chaptersByNumber.get(chapterNumber)
    return {
      key: `chapter-${chapterNumber}`,
      chapterNumber,
      title: `Chapter ${chapterNumber}`,
      subtitle: chapter?.title || "Referenced by revision intelligence",
      items: filteredChapterItems.filter((item) => item.chapter_ref === chapterNumber),
    }
  })

  const unassignedChapterItems = filteredChapterItems.filter((item) => typeof item.chapter_ref !== "number")
  if (unassignedChapterItems.length > 0) {
    chapterFindings.push({
      key: "book-wide",
      chapterNumber: null,
      title: "Book-wide findings",
      subtitle: "Not tied to a specific chapter yet",
      items: unassignedChapterItems,
    })
  }

  const selectedChapterFinding = chapterFindings.find((row) => row.key === selectedChapterKey) ?? null

  // All hooks must be called before any conditional returns
  useEffect(() => {
    if (!selectedInsight || !revisionIntelligence) return
    const nextSelection = [...focusCards].find((card) => card.key === selectedInsight.key) ?? null
    setSelectedInsight(nextSelection)
  }, [revisionIntelligence, selectedInsight, focusCards])

  useEffect(() => {
    if (selectedChapterKey === null || !revisionIntelligence) return
    const hasSelectedChapter = chapterFindings.some(({ key, items }) => key === selectedChapterKey && items.length > 0)
    if (!hasSelectedChapter) {
      setSelectedChapterKey(null)
    }
  }, [selectedChapterKey, chapterSeverityFilter, revisionIntelligence, chapterFindings])

  useEffect(() => {
    if (selectedRevisionItemId === null || !revisionIntelligence) return
    const hasSelectedItem = allItems.some((item) => item.id === selectedRevisionItemId)
    if (!hasSelectedItem) {
      setSelectedRevisionItemId(null)
    }
  }, [selectedRevisionItemId, revisionIntelligence, allItems])

  useEffect(() => {
    if (!chapterFindingsHighlighted) return
    const timeoutId = window.setTimeout(() => setChapterFindingsHighlighted(false), 1800)
    return () => window.clearTimeout(timeoutId)
  }, [chapterFindingsHighlighted])

  if (revisionIntelligenceError && !revisionIntelligence && onRetryRevisionIntelligence) {
    return (
      <ErrorCard
        message="Failed to load revision intelligence"
        onRetry={onRetryRevisionIntelligence}
        variant="compact"
        isDark={isDark}
      />
    )
  }

  if (!revisionIntelligence) {
    return (
      <EmptyTabState
        isDark={isDark}
        title="Revision intelligence is still syncing."
        body="LoreVia will populate the full revision hub here once the latest manuscript intelligence finishes processing."
      />
    )
  }

  const highCount = allItems.filter((item) => item.severity === "high").length || revisionIntelligence.summary.high_severity_count
  const mediumCount = allItems.filter((item) => item.severity === "medium").length
  const lowCount = allItems.filter((item) => item.severity === "low").length
  const readyScore = storyHealth?.score ?? Math.max(0, 100 - highCount * 6 - mediumCount * 3 - lowCount)

  const selectReadinessSeverity = (severity: RevisionSeverityFilter) => {
    setChapterSeverityFilter(severity)
    setSelectedChapterKey(null)
    setSelectedRevisionItemId(null)
    setChapterFindingsHighlighted(true)
  }

  const renderClickableFinding = (item: RevisionActionItem) => {
    const isActive = selectedRevisionItemId === item.id
    return (
      <button
        type="button"
        key={item.id}
        onClick={() => setSelectedRevisionItemId((current) => current === item.id ? null : item.id)}
        className={`w-full rounded-md border px-3 py-3 text-left transition ${isDark ? "border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06]" : "border-slate-200 bg-white hover:bg-slate-50"} ${isActive ? (isDark ? "ring-1 ring-sky-400/60" : "ring-1 ring-sky-500/50") : ""}`}
      >
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-full px-2 py-1 text-3xs font-semibold uppercase tracking-[0.18em] ${severityClass(item.severity, isDark)}`}>{item.severity}</span>
          {item.chapter_ref ? <span className={isDark ? "text-xs text-slate-500" : "text-xs text-slate-400"}>{`Chapter ${item.chapter_ref}`}</span> : null}
          <span className={isDark ? "text-xs text-slate-500" : "text-xs text-slate-400"}>{item.source_label || "Revision intelligence"}</span>
        </div>
        <p className={`mt-2 text-sm font-semibold leading-6 ${isDark ? "text-slate-100" : "text-slate-800"}`}>{item.title}</p>
        <p className={`mt-1 text-xs leading-5 ${isDark ? "text-slate-400" : "text-slate-500"}`}>{item.recommendation || item.description}</p>
        {isActive ? (
          <div className={`mt-3 rounded-md border px-3 py-3 ${isDark ? "border-sky-400/25 bg-sky-500/10" : "border-sky-200 bg-sky-50"}`}>
            <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-sky-200" : "text-sky-800"}`}>What LoreVia found</p>
            <p className={`mt-2 text-xs leading-5 ${isDark ? "text-slate-200" : "text-slate-700"}`}>{item.description}</p>
            {item.recommendation ? (
              <>
                <p className={`mt-3 text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-sky-200" : "text-sky-800"}`}>Suggested next step</p>
                <p className={`mt-2 text-xs leading-5 ${isDark ? "text-slate-200" : "text-slate-700"}`}>{item.recommendation}</p>
              </>
            ) : null}
            <div className={`mt-3 flex flex-wrap gap-2 text-3xs font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>
              <span>Status: {item.status.replace("_", " ")}</span>
              <span>Category: {item.category}</span>
            </div>
          </div>
        ) : null}
      </button>
    )
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-5 xl:auto-rows-fr xl:grid-cols-[minmax(13rem,0.75fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(13rem,0.7fr)]">
        <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Revision focus</p>
          <div className="mt-4 space-y-3">
            {focusCards.map((card, index) => {
              const severity = index === 0 ? "high" : index < 3 ? "medium" : "low"
              const isActive = selectedInsight?.key === card.key
              const count = card.items.length
              return (
              <button
                type="button"
                key={card.key}
                onClick={() => setSelectedInsight(isActive ? null : card)}
                className={`w-full rounded-md border px-3 py-3 text-left transition ${isDark ? "border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06]" : "border-slate-200 bg-white hover:bg-slate-50"} ${isActive ? (isDark ? "ring-1 ring-sky-400/60" : "ring-1 ring-sky-500/50") : ""}`}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className={`text-sm font-semibold ${isDark ? "text-slate-100" : "text-slate-800"}`}>{card.title}</span>
                  <span className={`rounded-full px-2 py-1 text-3xs font-semibold ${severityClass(String(severity)[0].toUpperCase() + String(severity).slice(1), isDark)}`}>{count}</span>
                </div>
              </button>
            )})}
          </div>
        </section>
        <section className={`${panelClass(isDark, "h-full p-4 sm:p-5 transition-shadow duration-300")} ${chapterFindingsHighlighted ? (isDark ? "shadow-[0_0_0_2px_rgba(56,189,248,0.5),0_0_30px_rgba(20,184,166,0.22)]" : "shadow-[0_0_0_2px_rgba(14,116,144,0.3),0_0_26px_rgba(14,165,233,0.2)]") : ""}`}>
          <div className="flex items-center justify-between gap-3">
            <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Chapter-specific findings</p>
            <div className="flex gap-1">
              {(["all", "high", "medium", "low"] as const).map((label) => {
                const isActive = chapterSeverityFilter === label
                return (
                  <button
                    type="button"
                    key={label}
                    onClick={() => {
                      setChapterSeverityFilter(label)
                      setSelectedChapterKey(null)
                    }}
                    className={`rounded-full px-2 py-1 text-3xs font-semibold transition ${isActive ? (isDark ? "bg-sky-500/15 text-sky-200" : "bg-sky-50 text-sky-700") : (isDark ? "bg-white/[0.05] text-slate-400 hover:bg-white/[0.08]" : "bg-slate-100 text-slate-500 hover:bg-slate-200")}`}
                  >
                    {label[0].toUpperCase() + label.slice(1)}
                  </button>
                )
              })}
            </div>
          </div>
          <div className="mt-4 space-y-2">
            {chapterFindings.map(({ key, title, subtitle, items }) => {
              const isActive = selectedChapterKey === key
              return (
                <button
                  type="button"
                  key={key}
                  onClick={() => {
                    setSelectedChapterKey(isActive ? null : key)
                    setSelectedRevisionItemId(null)
                  }}
                  className={`flex w-full items-center justify-between gap-3 rounded-md border px-3 py-3 text-left transition ${isDark ? "border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06]" : "border-slate-200 bg-white hover:bg-slate-50"} ${isActive ? (isDark ? "ring-1 ring-sky-400/60" : "ring-1 ring-sky-500/50") : ""}`}
                >
                  <div className="min-w-0">
                    <p className={`text-sm font-semibold ${isDark ? "text-slate-100" : "text-slate-800"}`}>{title}</p>
                    <p className={`mt-1 break-words text-xs leading-5 ${isDark ? "text-slate-500" : "text-slate-400"}`}>{subtitle}</p>
                  </div>
                  <span className="text-sm font-semibold text-teal-600">{items.length} issue{items.length === 1 ? "" : "s"}</span>
                </button>
            )})}
          </div>
        </section>
        <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Recommended fixes</p>
          <div className="mt-4 space-y-3">
            {allItems.slice(0, 3).map((item) => (
              <div key={item.id} className={`rounded-md border px-3 py-3 ${isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-white"}`}>
                <p className={`break-words text-sm font-semibold leading-6 ${isDark ? "text-slate-100" : "text-slate-800"}`}>{item.title}</p>
                <p className={`mt-1 break-words text-xs leading-5 ${isDark ? "text-slate-500" : "text-slate-400"}`}>{item.recommendation || item.description}</p>
              </div>
            ))}
            {allItems.length === 0 ? <p className={isDark ? "text-sm text-slate-500" : "text-sm text-slate-400"}>No high-impact fixes are currently surfaced.</p> : null}
          </div>
        </section>
        <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Readiness summary</p>
          <div className="mt-5 flex justify-center">
            <ScoreRing isDark={isDark} score={readyScore} label="ready" />
          </div>
          <div className="mt-4 space-y-2">
            <InfoLine
              isDark={isDark}
              label="High severity"
              value={String(highCount)}
              active={chapterSeverityFilter === "high"}
              onClick={() => selectReadinessSeverity("high")}
            />
            <InfoLine
              isDark={isDark}
              label="Medium severity"
              value={String(mediumCount)}
              active={chapterSeverityFilter === "medium"}
              onClick={() => selectReadinessSeverity("medium")}
            />
            <InfoLine
              isDark={isDark}
              label="Low severity"
              value={String(lowCount)}
              active={chapterSeverityFilter === "low"}
              onClick={() => selectReadinessSeverity("low")}
            />
          </div>
          <Link href={`/${bookId}/analysis` as Route} className={footerLinkClass(isDark)}>View readiness report <Icon name="chevron" /></Link>
        </section>
      </div>
      {selectedInsight ? (
        <section className={panelClass(isDark, "p-4 sm:p-5")}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Selected findings</p>
              <h3 className={`mt-2 text-lg font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{selectedInsight.title}</h3>
              <p className={`mt-1 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{selectedInsight.subtitle}</p>
            </div>
            <button
              type="button"
              onClick={() => setSelectedInsight(null)}
              className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${isDark ? "bg-white/10 text-slate-200 hover:bg-white/15" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}
            >
              Clear
            </button>
          </div>
          <div className="mt-4 space-y-3">
            {selectedInsight.items.length > 0 ? selectedInsight.items.map((item) => renderClickableFinding(item)) : (
              <p className={isDark ? "text-sm text-slate-500" : "text-sm text-slate-400"}>No findings are currently surfaced for this bucket.</p>
            )}
          </div>
        </section>
      ) : null}
      {selectedChapterFinding ? (
        <section className={panelClass(isDark, "p-4 sm:p-5")}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Chapter findings</p>
              <h3 className={`mt-2 text-lg font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{selectedChapterFinding.title}</h3>
              <p className={`mt-1 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
                {chapterSeverityFilter === "all"
                  ? "All surfaced revision findings for this row."
                  : `${chapterSeverityFilter[0].toUpperCase() + chapterSeverityFilter.slice(1)} severity findings for this row.`}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setSelectedChapterKey(null)}
              className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${isDark ? "bg-white/10 text-slate-200 hover:bg-white/15" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}
            >
              Clear
            </button>
          </div>
          <div className="mt-4 space-y-3">
            {selectedChapterFinding.items.length > 0 ? selectedChapterFinding.items.map((item) => renderClickableFinding(item)) : (
              <p className={isDark ? "text-sm text-slate-500" : "text-sm text-slate-400"}>No findings are currently surfaced for this chapter.</p>
            )}
          </div>
        </section>
      ) : null}
      <RevisionIntelligencePanel
        bookId={bookId}
        revision={revisionIntelligence}
        writerWorkspace={writerWorkspace}
        isDark={isDark}
        onRevisionChange={onRevisionChange}
        onWriterWorkspaceChange={onWriterWorkspaceChange}
      />
    </div>
  )
}

function PlanningTab({
  isDark,
  writerWorkspace,
  currentWords,
  targetWords,
  chapterCount,
  dailyWords,
  dailyTarget,
  loginStreakDays,
  saveState,
  saveMessage,
  onSaveGoalCalendar,
  onOpenManuscript,
  writerWorkspaceError,
  onRetryWriterWorkspace,
}: {
  isDark: boolean
  writerWorkspace: WriterWorkspace | null
  currentWords: number | null
  targetWords: number
  chapterCount: number | null
  dailyWords: number
  dailyTarget: number
  loginStreakDays: number
  saveState: WorkspaceSaveState
  saveMessage: string | null
  onSaveGoalCalendar: (goalCalendar: GoalCalendarItem[]) => Promise<boolean>
  onOpenManuscript: () => void
  writerWorkspaceError?: boolean
  onRetryWriterWorkspace?: () => void
}) {
  if (writerWorkspaceError && !writerWorkspace && onRetryWriterWorkspace) {
    return (
      <ErrorCard
        message="Failed to load workspace data"
        onRetry={onRetryWriterWorkspace}
        variant="compact"
        isDark={isDark}
      />
    )
  }

  const chapterTarget = writerWorkspace?.word_count_goals.chapter_target ?? 0
  const etaDays = currentWords && dailyTarget > 0 ? Math.max(1, Math.ceil(Math.max(0, targetWords - currentWords) / dailyTarget)) : null
  const incompleteItems = (writerWorkspace?.goal_calendar ?? []).filter((item) => !item.completed)

  return (
    <div className="space-y-5">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <PlanningMetric isDark={isDark} label="Book goal" value={`${targetWords.toLocaleString()} words`} />
        <PlanningMetric isDark={isDark} label="Chapter goal" value={chapterTarget > 0 ? `${chapterTarget.toLocaleString()} avg. words` : `${formatNumber(chapterCount)} chapters`} />
        <PlanningMetric isDark={isDark} label="Daily quota" value={`${dailyTarget.toLocaleString()} words`} />
        <PlanningMetric isDark={isDark} label="Writing streak" value={`${loginStreakDays} day${loginStreakDays === 1 ? "" : "s"}`} />
        <PlanningMetric isDark={isDark} label="Target completion" value={etaDays ? `In ${etaDays} days` : "Syncing"} />
      </div>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(18rem,0.45fr)] xl:auto-rows-fr">
        <GoalCalendarCard
          isDark={isDark}
          writerWorkspace={writerWorkspace}
          saveState={saveState}
          saveMessage={saveMessage}
          onSaveGoalCalendar={onSaveGoalCalendar}
          onOpenManuscript={onOpenManuscript}
        />
        <div className="space-y-5">
          <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
            <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Session goals</p>
            <div className="mt-4 space-y-3">
              {incompleteItems.slice(0, 3).map((item) => (
                <div key={item.id} className={`rounded-md border px-3 py-3 ${isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-white"}`}>
                  <p className={`break-words text-sm font-semibold leading-6 ${isDark ? "text-slate-100" : "text-slate-800"}`}>{item.title}</p>
                  <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>Due {formatPlannerDate(item.due_date)}</p>
                </div>
              ))}
              {incompleteItems.length === 0 ? <p className={isDark ? "text-sm text-slate-500" : "text-sm text-slate-400"}>Add a planning item to define the next session.</p> : null}
            </div>
          </section>
          <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
            <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Quotas</p>
            <div className="mt-4 space-y-3">
              <CompactProgressRow isDark={isDark} label="Daily quota" value={`${dailyWords} / ${dailyTarget}`} percent={(dailyWords / dailyTarget) * 100} />
              <CompactProgressRow isDark={isDark} label="Weekly quota" value="Workspace goal" percent={clamp((dailyWords / dailyTarget) * 70, 0, 100)} />
              <CompactProgressRow isDark={isDark} label="This month" value={`${formatNumber(currentWords)} / ${targetWords.toLocaleString()}`} percent={currentWords ? (currentWords / targetWords) * 100 : 0} />
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}

function WorkspaceStatsTab({
  isDark,
  currentWords,
  targetWords,
  chapterCount,
  characterCount,
  worldArticleCount,
  percentComplete,
  chapters,
  dailyWords,
  dailyTarget,
  loginStreakDays,
  weeklyLoginActivity,
  onOpenManuscript,
}: {
  isDark: boolean
  currentWords: number | null
  targetWords: number
  chapterCount: number | null
  characterCount: number
  worldArticleCount: number
  percentComplete: number
  chapters: ChapterListResponse["chapters"]
  dailyWords: number
  dailyTarget: number
  loginStreakDays: number
  weeklyLoginActivity: boolean[]
  onOpenManuscript: () => void
}) {
  const averageWords = chapterCount && currentWords ? Math.round(currentWords / chapterCount) : 0
  const progress = clamp(percentComplete || (currentWords ? (currentWords / targetWords) * 100 : 0), 0, 100)

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,0.92fr)_minmax(0,1fr)_minmax(0,1fr)]">
      <div className="xl:col-span-3">
        <ProjectOverviewCard isDark={isDark} currentWords={currentWords} chapterCount={chapterCount} characterCount={characterCount} worldArticleCount={worldArticleCount} />
      </div>
      <div className="space-y-5">
        <DailyGoalCard isDark={isDark} dailyWords={dailyWords} dailyTarget={dailyTarget} onUpdateGoal={onOpenManuscript} />
        <WritingStreakCard isDark={isDark} streakDays={loginStreakDays} weekActivity={weeklyLoginActivity} />
        <ProgressBreakdownCard isDark={isDark} progress={progress} />
      </div>
      <div className="space-y-5">
        <BarChartCard isDark={isDark} title="Chapter cadence" eyebrow="Average words per chapter" value={averageWords ? averageWords.toLocaleString() : "Syncing"} labels={chapters.slice(-5).map((chapter) => `Ch. ${chapter.number}`)} values={chapters.slice(-5).map((_, index) => Math.max(20, progress - index * 7))} />
        <BarChartCard isDark={isDark} title="Writing velocity" eyebrow="Average words per day" value={dailyWords > 0 ? dailyWords.toLocaleString() : averageWords ? Math.round(averageWords / 10).toLocaleString() : "Syncing"} labels={["M", "T", "W", "T", "F", "S", "S"]} values={weeklyLoginActivity.map((active, index) => active ? 40 + index * 8 : 12)} />
      </div>
      <div className="space-y-5">
        <TrendCard isDark={isDark} progress={progress} currentWords={currentWords} />
        <InsightsCard isDark={isDark} worldArticleCount={worldArticleCount} progress={progress} />
      </div>
    </div>
  )
}

function StoryMapTab({
  isDark,
  bookId,
  preWritingCheck,
  revisionIntelligence,
  onOpenRelationships,
  onNavigate,
  preWritingCheckError,
  onRetryPreWritingCheck,
  revisionIntelligenceError,
  onRetryRevisionIntelligence,
}: {
  isDark: boolean
  bookId: string
  preWritingCheck: PreWritingCheck | null
  revisionIntelligence: RevisionIntelligence | null
  onOpenRelationships: () => void
  onNavigate: (href: string) => void
  preWritingCheckError?: boolean
  onRetryPreWritingCheck?: () => void
  revisionIntelligenceError?: boolean
  onRetryRevisionIntelligence?: () => void
}) {
  if (preWritingCheckError && !preWritingCheck && onRetryPreWritingCheck) {
    return (
      <ErrorCard
        message="Failed to load story map data"
        onRetry={onRetryPreWritingCheck}
        variant="compact"
        isDark={isDark}
      />
    )
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-5 xl:grid-cols-[minmax(0,0.98fr)_minmax(0,1.02fr)]">
        <section className={panelClass(isDark, "p-4 sm:p-5")}>
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Memory map</p>
              <h3 className={`mt-2 text-xl font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Who is in play and what still needs closure.</h3>
            </div>
            <button type="button" onClick={onOpenRelationships} className="text-sm font-semibold text-teal-700">
              Open graph
            </button>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <div className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-white"}`}>
              <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Active characters</p>
              <div className="mt-3 space-y-3">
                {(preWritingCheck?.active_characters ?? []).slice(0, 4).map((character) => (
                  <div key={character.id}>
                    <p className={`text-sm font-medium ${isDark ? "text-slate-100" : "text-slate-800"}`}>{character.name}</p>
                    <p className={`mt-1 text-xs leading-5 ${isDark ? "text-slate-500" : "text-slate-400"}`}>
                      {character.role || "Character"}{character.last_seen_chapter ? ` / last seen in Chapter ${character.last_seen_chapter}` : ""}
                    </p>
                  </div>
                ))}
                {(preWritingCheck?.active_characters.length ?? 0) === 0 ? <p className={isDark ? "text-sm text-slate-500" : "text-sm text-slate-400"}>Character memory is still syncing.</p> : null}
              </div>
            </div>

            <div className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-white"}`}>
              <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Unresolved threads</p>
              <div className="mt-3 space-y-3">
                {(preWritingCheck?.unresolved_threads ?? []).slice(0, 4).map((thread) => (
                  <div key={thread.id}>
                    <p className={`text-sm font-medium ${isDark ? "text-slate-100" : "text-slate-800"}`}>{thread.title}</p>
                    <p className={`mt-1 text-xs leading-5 ${isDark ? "text-slate-500" : "text-slate-400"}`}>
                      {thread.status}{thread.introduced_at ? ` / introduced in Chapter ${thread.introduced_at}` : ""}
                    </p>
                  </div>
                ))}
                {(preWritingCheck?.unresolved_threads.length ?? 0) === 0 ? <p className={isDark ? "text-sm text-slate-500" : "text-sm text-slate-400"}>No open threads are surfaced yet.</p> : null}
              </div>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <button type="button" onClick={() => onNavigate(`/${bookId}/timeline`)} className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-teal-800/10 text-teal-100 hover:bg-teal-800/20" : "bg-teal-50 text-teal-800 hover:bg-teal-100"}`}>
              Open timeline
            </button>
            <button type="button" onClick={() => onNavigate(`/${bookId}/characters`)} className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-white/[0.06] text-slate-200 hover:bg-white/[0.1]" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}>
              Open character bible
            </button>
          </div>
        </section>

        <section className={panelClass(isDark, "p-4 sm:p-5")}>
          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Continuity findings</p>
          <div className="mt-4 space-y-3">
            {(preWritingCheck?.alerts ?? []).slice(0, 5).map((alert) => (
              <div key={`${alert.title}-${alert.chapter_ref ?? "na"}`} className={`rounded-md border px-4 py-3 ${isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-white"}`}>
                <div className="flex items-center justify-between gap-3">
                  <p className={`text-sm font-semibold ${isDark ? "text-slate-100" : "text-slate-800"}`}>{alert.title}</p>
                  {alert.chapter_ref ? <span className={`text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>Ch {alert.chapter_ref}</span> : null}
                </div>
                <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{alert.body}</p>
              </div>
            ))}
            {(preWritingCheck?.alerts.length ?? 0) === 0 ? <p className={isDark ? "text-sm text-slate-500" : "text-sm text-slate-400"}>Continuity findings will appear here after the next intelligence pass.</p> : null}
          </div>
        </section>
      </div>

      {revisionIntelligence ? (
        <RevisionIntelligencePanel
          bookId={bookId}
          revision={revisionIntelligence}
          writerWorkspace={null}
          isDark={isDark}
          onRevisionChange={() => {}}
          onWriterWorkspaceChange={() => {}}
          variant="story-map"
        />
      ) : null}
    </div>
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
    { label: "Total words", value: formatNumber(currentWords), icon: "spark" as IconName },
    { label: "Chapters", value: formatNumber(chapterCount), icon: "book" as IconName },
    { label: "Characters", value: formatNumber(characterCount), icon: "users" as IconName },
    { label: "World items", value: formatNumber(worldArticleCount), icon: "file" as IconName },
  ]

  return (
    <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Workspace stats</p>
      <div className="mt-5 grid grid-cols-1 gap-3">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className={`flex min-w-0 items-start gap-3 rounded-md border px-4 py-3 ${isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-white"}`}
          >
            <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-sm ${isDark ? "bg-white/[0.04]" : "bg-slate-50"}`}>
              <Icon name={stat.icon} className="h-5 w-5 text-teal-700" />
            </div>
            <div className="min-w-0 flex-1">
              <p className={`text-xs leading-tight ${isDark ? "text-slate-500" : "text-slate-400"}`}>{stat.label}</p>
              <p className={`mt-1 text-2xl font-semibold tabular-nums ${isDark ? "text-white" : "text-slate-950"}`}>{stat.value}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

function WritingStreakCard({ isDark, streakDays, weekActivity, compact = false }: { isDark: boolean; streakDays: number; weekActivity: boolean[]; compact?: boolean }) {
  return (
    <section className={compact ? "min-w-0" : panelClass(isDark, "h-full p-4 sm:p-5")}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Writing streak</p>
      <div className="mt-5 flex items-center gap-3">
        <Icon name="flame" className="h-8 w-8 text-orange-400" />
        <div>
          <p className={`text-2xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{streakDays} days</p>
          <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>Tracked from daily sign-ins.</p>
        </div>
      </div>
      <div className="mt-6 grid grid-cols-7 gap-2">
        {["M", "T", "W", "T", "F", "S", "S"].map((day, index) => (
          <div key={`${day}-${index}`} className="text-center">
            <div className={`mx-auto h-9 w-4 rounded-full ${weekActivity[index] ? "bg-teal-800" : isDark ? "bg-white/10" : "bg-slate-200"}`} />
            <p className={`mt-2 text-3xs font-semibold ${isDark ? "text-slate-500" : "text-slate-400"}`}>{day}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

function DailyGoalCard({ isDark, dailyWords, dailyTarget, onUpdateGoal }: { isDark: boolean; dailyWords: number; dailyTarget: number; onUpdateGoal?: () => void }) {
  const goalPercent = clamp((dailyWords / dailyTarget) * 100, 0, 100)

  return (
    <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Daily goal</p>
      <div className="mt-6 flex items-center justify-center">
        <div
          className="relative flex h-32 w-32 items-center justify-center rounded-full"
          style={{ background: `conic-gradient(#8b5cf6 0 ${goalPercent}%, ${isDark ? "#1b2430" : "#edf0f5"} ${goalPercent}% 100%)` }}
        >
          <div className={`flex h-24 w-24 flex-col items-center justify-center rounded-full ${isDark ? "bg-[#0d141c]" : "bg-white"}`}>
            <span className={`text-2xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{dailyWords.toLocaleString()}</span>
            <span className={`text-3xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>/ {dailyTarget.toLocaleString()} words</span>
          </div>
        </div>
      </div>
      {onUpdateGoal ? (
        <button type="button" onClick={onUpdateGoal} className={footerLinkClass(isDark)}>
          Update goal <Icon name="chevron" />
        </button>
      ) : null}
    </section>
  )
}

function CompactProgressRow({ isDark, label, value, percent, tone = "teal" }: { isDark: boolean; label: string; value: string; percent: number; tone?: "teal" | "amber" | "rose" }) {
  const color = tone === "amber" ? "bg-amber-400" : tone === "rose" ? "bg-rose-400" : "bg-teal-500"
  return (
    <div className={`rounded-md border px-4 py-3 ${isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-white"}`}>
      <div className="flex items-center justify-between gap-3">
        <span className={`min-w-0 text-sm ${isDark ? "text-slate-300" : "text-slate-600"}`}>{label}</span>
        <span className={`max-w-[58%] break-words text-right text-sm font-semibold ${isDark ? "text-slate-100" : "text-slate-800"}`}>{value}</span>
      </div>
      <div className={`mt-3 h-1.5 overflow-hidden rounded-full ${isDark ? "bg-white/[0.08]" : "bg-slate-100"}`}>
        <div className={`h-full rounded-full ${color}`} style={{ width: `${clamp(percent, 0, 100)}%` }} />
      </div>
    </div>
  )
}

function InfoLine({ isDark, label, value, onClick, active = false }: { isDark: boolean; label: string; value: string; onClick?: () => void; active?: boolean }) {
  const baseClass = `flex w-full items-center justify-between gap-3 rounded-md border px-4 py-3 text-sm ${isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-white"}`

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={`${baseClass} transition ${isDark ? "hover:bg-white/[0.06]" : "hover:bg-slate-50"} ${active ? (isDark ? "ring-1 ring-sky-400/60" : "ring-1 ring-sky-500/50") : ""}`}
      >
        <span className={isDark ? "min-w-0 text-left text-slate-500" : "min-w-0 text-left text-slate-400"}>{label}</span>
        <span className={`max-w-[56%] break-words text-right font-semibold ${isDark ? "text-slate-100" : "text-slate-800"}`}>{value}</span>
      </button>
    )
  }

  return (
    <div className={baseClass}>
      <span className={isDark ? "min-w-0 text-slate-500" : "min-w-0 text-slate-400"}>{label}</span>
      <span className={`max-w-[56%] break-words text-right font-semibold ${isDark ? "text-slate-100" : "text-slate-800"}`}>{value}</span>
    </div>
  )
}

function ModeToggle({
  isDark,
  activeMode,
  modeSaving,
  onModeChange,
}: {
  isDark: boolean
  activeMode: "reader" | "author"
  modeSaving: boolean
  onModeChange: (nextMode: "reader" | "author") => void
}) {
  const thumbClass = activeMode === "author" ? "translate-x-full" : "translate-x-0"

  return (
    <div
      role="group"
      aria-label="Workspace mode"
      className={isDark ? "relative inline-grid h-11 grid-cols-2 rounded-full border border-white/10 bg-white/[0.04] p-1" : "relative inline-grid h-11 grid-cols-2 rounded-full border border-slate-200 bg-slate-50 p-1"}
    >
      <span
        aria-hidden="true"
        className={`pointer-events-none absolute inset-y-1 left-1 w-[calc(50%-0.25rem)] rounded-full bg-teal-800 transition-transform duration-300 ease-out ${thumbClass}`}
      />
      {(["reader", "author"] as const).map((mode) => (
        <button
          key={mode}
          type="button"
          onClick={() => onModeChange(mode)}
          disabled={modeSaving}
          aria-pressed={activeMode === mode}
          className={`relative z-10 min-w-[5.8rem] rounded-full px-4 text-xs font-semibold uppercase tracking-[0.18em] transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-teal-500/60 ${
            activeMode === mode
              ? "text-white"
              : isDark ? "text-slate-300 hover:text-white" : "text-slate-600 hover:text-slate-900"
          }`}
        >
          {mode}
        </button>
      ))}
    </div>
  )
}

function ActionRow({ isDark, icon, title, body, onClick, tone = "default" }: { isDark: boolean; icon: IconName; title: string; body: string; onClick: () => void; tone?: "default" | "amber" | "teal" }) {
  const iconClass = tone === "amber" ? "text-amber-300" : tone === "teal" ? "text-teal-400" : "text-slate-400"
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full items-center gap-3 rounded-md border px-4 py-3 text-left transition ${isDark ? "border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06]" : "border-slate-200 bg-white hover:bg-slate-50"}`}
    >
      <Icon name={icon} className={`h-5 w-5 ${iconClass}`} />
      <div className="min-w-0 flex-1">
        <p className={`break-words text-sm font-semibold leading-6 ${isDark ? "text-slate-100" : "text-slate-800"}`}>{title}</p>
        <p className={`mt-1 break-words text-xs leading-5 ${isDark ? "text-slate-500" : "text-slate-400"}`}>{body}</p>
      </div>
      <Icon name="chevron" className="h-4 w-4 text-teal-600" />
    </button>
  )
}

function ScoreRing({ isDark, score, label }: { isDark: boolean; score: number; label: string }) {
  const safeScore = clamp(Math.round(score), 0, 100)
  return (
    <div
      className="relative flex h-28 w-28 items-center justify-center rounded-full"
      style={{ background: `conic-gradient(#8b5cf6 0 ${safeScore}%, ${isDark ? "#1b2430" : "#edf0f5"} ${safeScore}% 100%)` }}
    >
      <div className={`flex h-20 w-20 flex-col items-center justify-center rounded-full ${isDark ? "bg-[#0d141c]" : "bg-white"}`}>
        <span className={`text-2xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{safeScore}</span>
        <span className={`text-3xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>{label}</span>
      </div>
    </div>
  )
}

function PlanningMetric({ isDark, label, value }: { isDark: boolean; label: string; value: string }) {
  return (
    <div className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-white"}`}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>{label}</p>
      <p className={`mt-2 break-words text-lg font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{value}</p>
    </div>
  )
}

function ProgressBreakdownCard({ isDark, progress }: { isDark: boolean; progress: number }) {
  const rows: Array<{ label: string; value: number; tone: "teal" | "amber" | "rose" }> = [
    { label: "Plot / structure", value: progress + 8, tone: "teal" },
    { label: "Characters / arcs", value: progress + 2, tone: "teal" },
    { label: "Worldbuilding", value: progress - 4, tone: "amber" },
    { label: "Pacing / momentum", value: progress - 12, tone: "rose" },
    { label: "Theme / symbolism", value: progress - 18, tone: "rose" },
    { label: "Overall workspace progress", value: progress, tone: "teal" },
  ]
  return (
    <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Progress breakdown</p>
      <div className="mt-4 space-y-3">
        {rows.map(({ label, value, tone }) => (
          <CompactProgressRow key={label} isDark={isDark} label={label} value={`${Math.round(clamp(value, 0, 100))}%`} percent={value} tone={tone} />
        ))}
      </div>
    </section>
  )
}

function BarChartCard({ isDark, title, eyebrow, value, labels, values }: { isDark: boolean; title: string; eyebrow: string; value: string; labels: string[]; values: number[] }) {
  const normalizedLabels = labels.length > 0 ? labels : ["1", "2", "3"]
  const normalizedValues = values.length > 0 ? values : [20, 34, 26]
  return (
    <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>{title}</p>
      <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>{eyebrow}</p>
      <p className={`mt-1 text-2xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{value}</p>
      <div className="mt-5 flex h-32 items-end gap-3 border-b border-white/10 px-2">
        {normalizedValues.map((item, index) => (
          <div key={`${normalizedLabels[index] ?? index}-${index}`} className="flex flex-1 flex-col items-center justify-end gap-2">
            <div className="w-full rounded-t-lg bg-teal-500/80" style={{ height: `${clamp(item, 8, 100)}%` }} />
            <span className={`text-3xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>{normalizedLabels[index]}</span>
          </div>
        ))}
      </div>
    </section>
  )
}

function TrendCard({ isDark, progress, currentWords }: { isDark: boolean; progress: number; currentWords: number | null }) {
  return (
    <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Trend overview</p>
      <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>30-day writing trend</p>
      <p className="mt-2 text-2xl font-semibold text-teal-500">+{Math.max(0, Math.round(progress / 4))}%</p>
      <div className="mt-5 grid h-28 grid-cols-8 items-end gap-2">
        {[24, 34, 28, 44, 52, 49, 64, 76].map((height, index) => (
          <div key={index} className="rounded-t-lg bg-teal-500/70" style={{ height: `${height}%` }} />
        ))}
      </div>
      <p className={`mt-4 text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>Total words this period: {formatNumber(currentWords)}</p>
    </section>
  )
}

function InsightsCard({ isDark, worldArticleCount, progress }: { isDark: boolean; worldArticleCount: number; progress: number }) {
  const insights = [
    "Your most productive time appears in recent evening writing windows.",
    progress < 70 ? "Pacing dips may need another pass before reader review." : "Pacing balance is stable across the current sample.",
    worldArticleCount > 0 ? "Worldbuilding is growing steadily with the manuscript." : "Worldbuilding items will appear once notes or templates are added.",
  ]
  return (
    <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Insights</p>
      <div className="mt-4 space-y-3">
        {insights.map((insight, index) => (
          <div key={insight} className={`rounded-md border px-4 py-3 text-sm leading-6 ${isDark ? "border-white/[0.06] bg-white/[0.03] text-slate-300" : "border-slate-200 bg-white text-slate-600"}`}>
            <span className="mr-2 font-semibold text-teal-600">{index + 1}.</span>{insight}
          </div>
        ))}
      </div>
      <button type="button" className={footerLinkClass(isDark)}>View all insights <Icon name="chevron" /></button>
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
    <section className="space-y-5">
      <div className={panelClass(isDark, "p-4 sm:p-5")}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Planning calendar</p>
            <h3 className={`mt-2 text-xl font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Attach every revision promise to a day.</h3>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {goalChips.map((goal) => (
              <div key={goal.label} className={`rounded-full px-3 py-2 text-xs ${isDark ? "bg-white/[0.05] text-slate-300" : "bg-slate-100 text-slate-600"}`}>
                {goal.label}: {typeof goal.value === "number" && goal.value > 0 ? `${goal.value.toLocaleString()} ${goal.unit}` : "Not set"}
              </div>
            ))}
          </div>
        </div>
      </div>

      <section className={panelClass(isDark, "p-4 sm:p-5")}>
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{formatPlannerMonth(visibleMonth)}</p>
            <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>{monthCompletedCount}/{monthItemCount || 0} done this month</p>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setVisibleMonth((current) => shiftMonthValue(current, -1))}
              aria-label="Show previous month"
              className={`flex h-9 w-9 items-center justify-center rounded-full border transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-300 hover:bg-[#17212d]" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}`}
            >
              <Icon name="chevron" className="h-4 w-4 rotate-180" />
            </button>
            <button
              type="button"
              onClick={() => setVisibleMonth((current) => shiftMonthValue(current, 1))}
              aria-label="Show next month"
              className={`flex h-9 w-9 items-center justify-center rounded-full border transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-300 hover:bg-[#17212d]" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}`}
            >
              <Icon name="chevron" className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(20rem,0.92fr)]">
          <div className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-slate-50/70"}`}>
            <div className="grid grid-cols-7 gap-2">
              {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((label) => (
                <div key={label} className={`px-1 text-center text-3xs font-semibold ${isDark ? "text-slate-500" : "text-slate-400"}`}>{label}</div>
              ))}
              {calendarDays.map((day) => {
                const dayItems = itemsByDate.get(day.value) ?? []
                const selected = day.value === selectedDate
                const isToday = day.value === today

                return (
                  <button
                    key={day.value}
                    type="button"
                    onClick={() => setSelectedDate(day.value)}
                    className={`min-h-[5.8rem] rounded-md border p-2 text-left transition ${
                      selected
                        ? isDark ? "border-teal-800/25 bg-teal-800/10" : "border-teal-300 bg-teal-50"
                        : isDark ? "border-white/[0.05] bg-[#101720] hover:bg-[#16202b]" : "border-slate-200 bg-white hover:bg-slate-50"
                    } ${!day.inMonth ? (isDark ? "text-slate-600" : "text-slate-300") : ""}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className={`text-sm font-semibold ${selected ? "text-teal-700" : day.inMonth ? (isDark ? "text-slate-200" : "text-slate-700") : ""}`}>{day.label}</span>
                      {isToday ? <span className="rounded-full bg-teal-800 px-1.5 py-0.5 text-3xs font-semibold text-white">Today</span> : null}
                    </div>
                    <div className="mt-3 space-y-1">
                      {dayItems.length > 0 ? (
                        <>
                          <p className={`text-3xs font-medium ${isDark ? "text-slate-300" : "text-slate-600"}`}>{dayItems.length} item{dayItems.length === 1 ? "" : "s"}</p>
                          <p className={`text-3xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>{dayItems.filter((item) => item.completed).length}/{dayItems.length} complete</p>
                        </>
                      ) : (
                        <p className={`text-3xs ${isDark ? "text-slate-600" : "text-slate-300"}`}>Open</p>
                      )}
                    </div>
                  </button>
                )
              })}
            </div>
          </div>

          <div className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-white"}`}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{formatPlannerDate(selectedDate)}</p>
                <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>
                  {selectedItems.length > 0 ? `${selectedItems.length} scheduled item${selectedItems.length === 1 ? "" : "s"}` : "No goals scheduled yet."}
                </p>
              </div>
              <div className="text-right">
                <p className={`text-3xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>Selected quota</p>
                <p className={`mt-1 text-sm font-semibold ${isDark ? "text-slate-200" : "text-slate-700"}`}>{selectedQuotaTotal > 0 ? selectedQuotaTotal.toLocaleString() : "-"}</p>
              </div>
            </div>

            <div className="mt-4 space-y-3">
              {selectedItems.length > 0 ? selectedItems.map((item) => (
                <div key={item.id} className={`rounded-md border p-3 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-slate-50"}`}>
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
                        <p className={`text-sm font-semibold ${item.completed ? (isDark ? "text-slate-500 line-through" : "text-slate-400 line-through") : isDark ? "text-slate-200" : "text-slate-700"}`}>{item.title}</p>
                        {formatQuotaLabel(item.quota_value, item.quota_unit) ? (
                          <span className={`rounded-full px-2 py-1 text-3xs font-semibold ${isDark ? "bg-teal-800/10 text-teal-200" : "bg-teal-50 text-teal-800"}`}>{formatQuotaLabel(item.quota_value, item.quota_unit)}</span>
                        ) : null}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => void removeCalendarItem(item.id)}
                      disabled={!editable || saveState === "saving"}
                      className={`text-xs font-semibold ${isDark ? "text-slate-500 hover:text-rose-300 disabled:text-slate-700" : "text-slate-400 hover:text-rose-600 disabled:text-slate-300"}`}
                    >
                      Remove
                    </button>
                  </div>
                </div>
              )) : (
                <div className={`rounded-md border border-dashed p-4 text-sm ${isDark ? "border-white/[0.08] text-slate-500" : "border-slate-200 text-slate-400"}`}>
                  Nothing is scheduled for this day yet.
                </div>
              )}
            </div>

            <div className={`mt-5 rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-[#0d141c]" : "border-slate-200 bg-slate-50/60"}`}>
              <p className={`text-sm font-semibold ${isDark ? "text-slate-200" : "text-slate-700"}`}>Add planning item</p>
              <div className="mt-4 grid gap-3">
                <input
                  value={draftTitle}
                  onChange={(event) => setDraftTitle(event.target.value)}
                  disabled={!editable || saveState === "saving"}
                  aria-label="Planning item"
                  className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-teal-700" : "border-slate-200 bg-white text-slate-900 focus:border-teal-700"}`}
                />
                <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_9rem]">
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={draftQuotaValue}
                    onChange={(event) => setDraftQuotaValue(event.target.value)}
                    disabled={!editable || saveState === "saving"}
                    aria-label="Planning quota"
                    className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-teal-700" : "border-slate-200 bg-white text-slate-900 focus:border-teal-700"}`}
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
                </div>
                <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
                  <input
                    type="date"
                    value={selectedDate}
                    onChange={(event) => setSelectedDate(event.target.value)}
                    disabled={!editable || saveState === "saving"}
                    className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-teal-700" : "border-slate-200 bg-white text-slate-900 focus:border-teal-700"}`}
                  />
                  <button
                    type="button"
                    onClick={() => void addCalendarItem()}
                    disabled={!editable || saveState === "saving" || !draftTitle.trim()}
                    className={`inline-flex h-11 items-center justify-center rounded-md px-4 text-sm font-semibold transition ${isDark ? "bg-teal-800 text-white hover:bg-teal-700 disabled:bg-teal-800/35" : "bg-teal-800 text-white hover:bg-teal-800 disabled:bg-teal-300"}`}
                  >
                    Add item
                  </button>
                </div>
              </div>

              <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                <p className={`text-xs ${saveState === "error" ? "text-rose-400" : isDark ? "text-slate-500" : "text-slate-400"}`}>
                  {saveMessage || (editable ? "Changes save back into this book workspace." : "Loading planner...")}
                </p>
                <button type="button" onClick={onOpenManuscript} className="text-xs font-semibold text-teal-700">
                  Adjust word goals
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </section>
  )
}

function HeroMetric({
  isDark,
  label,
  value,
  note,
  progress,
}: {
  isDark: boolean
  label: string
  value: string
  note: string
  progress: number
}) {
  return (
    <div className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-white"}`}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>{label}</p>
      <p className={`mt-3 text-xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{value}</p>
      <p className={`mt-1 text-xs leading-5 ${isDark ? "text-slate-500" : "text-slate-400"}`}>{note}</p>
      <div className={`mt-4 h-1.5 overflow-hidden rounded-full ${isDark ? "bg-white/[0.08]" : "bg-slate-100"}`}>
        <div className="h-full rounded-full bg-teal-700" style={{ width: `${clamp(progress, 0, 100)}%` }} />
      </div>
    </div>
  )
}

function StatusPill({
  isDark,
  label,
  tone,
}: {
  isDark: boolean
  label: string
  tone: "violet" | "slate"
}) {
  const toneClass = tone === "violet"
    ? isDark ? "bg-teal-800/10 text-teal-100" : "bg-teal-50 text-teal-800"
    : isDark ? "bg-white/[0.06] text-slate-300" : "bg-slate-100 text-slate-600"

  return <span className={`rounded-full px-3 py-1 text-3xs font-semibold ${toneClass}`}>{label}</span>
}

function RevisionPreviewPlaceholder({ isDark }: { isDark: boolean }) {
  return (
    <section className={panelClass(isDark, "p-4 sm:p-5")}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Revision hub</p>
      <h2 className={`mt-2 text-xl font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Revision intelligence is syncing.</h2>
      <p className={`mt-3 text-sm leading-6 ${isDark ? "text-slate-400" : "text-slate-500"}`}>
        The dashboard will surface active revision pressure here once the latest manuscript analysis is ready.
      </p>
    </section>
  )
}

function EmptyTabState({ isDark, title, body }: { isDark: boolean; title: string; body: string }) {
  return (
    <div className={`rounded-md border border-dashed px-5 py-10 text-center ${isDark ? "border-white/[0.08] text-slate-400" : "border-slate-200 text-slate-500"}`}>
      <p className={`text-lg font-semibold ${isDark ? "text-slate-200" : "text-slate-800"}`}>{title}</p>
      <p className="mt-2 text-sm leading-6">{body}</p>
    </div>
  )
}

function panelClass(isDark: boolean, extra = "") {
  return `min-w-0 rounded-lg border ${
    isDark ? "border-white/[0.065] bg-[#0d141c]" : "border-slate-200/70 bg-white"
  } ${extra}`
}

function secondaryButtonClass(isDark: boolean) {
  return `inline-flex min-h-11 items-center gap-2 rounded-md border px-4 py-2.5 text-sm font-semibold transition ${
    isDark ? "border-white/10 bg-white/[0.04] text-slate-100 hover:bg-white/[0.08]" : "border-slate-200 bg-white text-slate-800 hover:bg-slate-50"
  }`
}

function footerLinkClass(isDark: boolean) {
  return `mt-5 inline-flex w-full items-center justify-center gap-2 rounded-md border px-4 py-3 text-sm font-semibold transition ${
    isDark ? "border-white/10 bg-white/[0.04] text-teal-200 hover:bg-white/[0.08]" : "border-slate-200 bg-white text-teal-800 hover:bg-slate-50"
  }`
}

function severityClass(severity: string, isDark: boolean) {
  if (severity === "High") return isDark ? "bg-rose-500/10 text-rose-300" : "bg-rose-50 text-rose-600"
  if (severity === "Medium") return isDark ? "bg-amber-500/10 text-amber-300" : "bg-amber-50 text-amber-600"
  return isDark ? "bg-emerald-500/10 text-emerald-300" : "bg-emerald-50 text-emerald-600"
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value))
}

function formatNumber(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return "Syncing"
  return value.toLocaleString()
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

function Icon({ name, className = "h-4 w-4" }: { name: IconName; className?: string }) {
  const common = { className, fill: "none", viewBox: "0 0 24 24", stroke: "currentColor", strokeWidth: 1.8 }

  switch (name) {
    case "analysis":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M5 19V9M10 19V5M15 19v-7M20 19V8M4 19h17" /></svg>
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
    case "graph":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M5 19V9M10 19V5M15 19v-7M20 19V8M4 19h17" /></svg>
    case "moon":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M20 15.5A8 8 0 018.5 4 8.5 8.5 0 1020 15.5z" /></svg>
    case "pen":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M4 20h4l11-11a2.6 2.6 0 10-4-4L4 16v4z" /></svg>
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
