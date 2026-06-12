"use client"
import dynamic from "next/dynamic"
import { useState, useEffect, useRef, useMemo } from "react"
import type { Route } from "next"
import { useRouter } from "next/navigation"

import { useReader } from "@/lib/hooks/useReader"
import { isReaderFontFamily, type ReaderFontFamily } from "@/lib/utils/readerTypography"
import { ReaderToolbar } from "./ReaderToolbar"
import { ChapterText } from "./ChapterText"
import { ReaderQuickRail } from "./ReaderQuickRail"
import { ReadingProgressRail } from "./ReadingProgressRail"
import { MobileActionBar } from "@/components/ui/MobileActionBar"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { ReaderDisplayStyle } from "@/types/reader"
import { Skeleton } from "@/components/ui/Skeleton"

interface Props { bookId: string; chapterNum: number }
type ReaderTheme = "light" | "dark"
interface ReaderBookmark {
  bookId: string
  chapter: number
  chapterTitle: string | null
  scrollPct: number
  selectedText: string | null
  savedAt: string
}

const ContextPanel = dynamic(
  () => import("./ContextPanel").then((module) => module.ContextPanel),
  { ssr: false }
)

const SummaryPanel = dynamic(
  () => import("./SummaryPanel").then((module) => module.SummaryPanel),
  { ssr: false }
)

const ReaderChapterFeedback = dynamic(
  () => import("./ReaderChapterFeedback").then((module) => module.ReaderChapterFeedback),
  { ssr: false }
)

export function ReaderView({ bookId, chapterNum }: Props) {
  const router = useRouter()
  const { data, loading, error, tap, contextResult, contextLoading, clearContext, saveProgress } = useReader(bookId, chapterNum)
  const { setTheme: setAppTheme } = usePreferencesStore()

  useEffect(() => {
    if (error) {
      router.replace("/library")
    }
  }, [error, router])
  const [showSummary, setShowSummary] = useState(false)
  const [showFeedbackPanel, setShowFeedbackPanel] = useState(false)
  const [selectedQuote, setSelectedQuote] = useState<string | null>(null)
  const [theme, setTheme] = useState<ReaderTheme>("dark")
  const [fontSize, setFontSize] = useState(20)
  const [fontFamily, setFontFamily] = useState<ReaderFontFamily>("serif")
  const [displayStyle, setDisplayStyle] = useState<ReaderDisplayStyle>("published")
  const [quoteModeEnabled, setQuoteModeEnabled] = useState(false)
  const [canUseQuoteMode, setCanUseQuoteMode] = useState(false)
  const [scrollPct, setScrollPct] = useState(0)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const restoreBookmarkRef = useRef<ReaderBookmark | null>(null)
  const progressTimeoutRef = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (progressTimeoutRef.current) {
        window.clearTimeout(progressTimeoutRef.current)
      }
    }
  }, [])

  useEffect(() => {
    setShowFeedbackPanel(false)

    if (typeof window !== "undefined" && "requestIdleCallback" in window) {
      const idleId = window.requestIdleCallback(() => setShowFeedbackPanel(true), { timeout: 1800 })
      return () => window.cancelIdleCallback(idleId)
    }

    const timeoutId = globalThis.setTimeout(() => setShowFeedbackPanel(true), 1200)
    return () => globalThis.clearTimeout(timeoutId)
  }, [bookId, chapterNum])

  useEffect(() => {
    const storedTheme = window.localStorage.getItem("reader-theme")
    if (storedTheme === "light" || storedTheme === "dark") setTheme(storedTheme)
    setSelectedQuote(null)
    setScrollPct(0)

    const storedSize = window.localStorage.getItem("reader-font-size")
    if (storedSize) setFontSize(parseInt(storedSize))

    const storedFont = window.localStorage.getItem("reader-font-family")
    if (isReaderFontFamily(storedFont)) setFontFamily(storedFont)

    const storedDisplayStyle = window.localStorage.getItem("reader-display-style")
    if (storedDisplayStyle === "relaxed" || storedDisplayStyle === "published") setDisplayStyle(storedDisplayStyle)

    if (!storedTheme) setTheme("dark")

    const bookmarkKey = `reader-bookmark:${bookId}`
    const bookmark = window.localStorage.getItem(bookmarkKey)
    if (bookmark) {
      try {
        const parsed = JSON.parse(bookmark) as ReaderBookmark
        restoreBookmarkRef.current = parsed?.chapter === chapterNum ? parsed : null
      } catch { }
    }

    const updateQuoteModeCapability = () => {
      const mobile = window.matchMedia("(max-width: 767px)").matches || window.matchMedia("(pointer: coarse)").matches
      setCanUseQuoteMode(mobile)
      if (!mobile) setQuoteModeEnabled(false)
    }

    updateQuoteModeCapability()
    window.addEventListener("resize", updateQuoteModeCapability)
    return () => window.removeEventListener("resize", updateQuoteModeCapability)
  }, [bookId, chapterNum])

  useEffect(() => {
    window.localStorage.setItem("reader-theme", theme)
    window.localStorage.setItem("app-theme", theme)
    window.localStorage.setItem("reader-font-size", fontSize.toString())
    window.localStorage.setItem("reader-font-family", fontFamily)
    window.localStorage.setItem("reader-display-style", displayStyle)
    setAppTheme(theme)
  }, [theme, fontSize, fontFamily, displayStyle, setAppTheme])

  const chapterText = useMemo(() => data?.text_content ?? "", [data?.text_content])

  useEffect(() => {
    const container = scrollRef.current
    if (!container) return

    const computeScrollPct = () => {
      const maxScroll = Math.max(1, container.scrollHeight - container.clientHeight)
      return Math.max(0, Math.min(1, container.scrollTop / maxScroll))
    }

    const syncProgress = () => {
      const nextPct = computeScrollPct()
      setScrollPct(nextPct)
      if (progressTimeoutRef.current) window.clearTimeout(progressTimeoutRef.current)
      progressTimeoutRef.current = window.setTimeout(() => {
        saveProgress(nextPct)
      }, 350)
    }

    syncProgress()
    container.addEventListener("scroll", syncProgress, { passive: true })
    return () => {
      container.removeEventListener("scroll", syncProgress)
      if (progressTimeoutRef.current) window.clearTimeout(progressTimeoutRef.current)
    }
  }, [chapterNum, data, saveProgress])

  useEffect(() => {
    if (!data) return
    const pendingBookmark = restoreBookmarkRef.current
    const container = scrollRef.current
    if (!container || !pendingBookmark || pendingBookmark.chapter !== chapterNum) return

    let attempts = 0
    const restoreScroll = () => {
      attempts += 1
      const maxScroll = Math.max(0, container.scrollHeight - container.clientHeight)
      if (maxScroll > 0 || attempts >= 12) {
        const nextTop = maxScroll * Math.max(0, Math.min(1, pendingBookmark.scrollPct ?? 0))
        container.scrollTop = nextTop
        setScrollPct(pendingBookmark.scrollPct ?? 0)
        if (pendingBookmark.selectedText) setSelectedQuote(pendingBookmark.selectedText)
        restoreBookmarkRef.current = null
        return
      }
      window.setTimeout(restoreScroll, 120)
    }

    window.setTimeout(restoreScroll, 80)
  }, [chapterNum, data])

  useEffect(() => {
    if (typeof window === "undefined" || !data) return
    const bookmarkKey = `reader-bookmark:${bookId}`
    const bookmark: ReaderBookmark = {
      bookId,
      chapter: chapterNum,
      chapterTitle: data.chapter_title ?? null,
      scrollPct,
      selectedText: selectedQuote?.trim() ? selectedQuote.trim() : null,
      savedAt: new Date().toISOString(),
    }
    window.localStorage.setItem(bookmarkKey, JSON.stringify(bookmark))
    restoreBookmarkRef.current = bookmark
  }, [bookId, chapterNum, data, scrollPct, selectedQuote])

  const toggleTheme = () => setTheme((current) => current === "dark" ? "light" : "dark")
  const clearPanel = () => {
    clearContext()
    setSelectedQuote(null)
    setQuoteModeEnabled(false)
  }
  const toggleQuoteMode = () => {
    if (!canUseQuoteMode) return
    if (quoteModeEnabled) setSelectedQuote(null)
    setQuoteModeEnabled((current) => !current)
  }

  const totalWords = countWords(chapterText)
  const wordsRead = totalWords > 0 ? Math.min(totalWords, Math.max(0, Math.round(totalWords * scrollPct))) : 0
  const progressPercent = totalWords > 0 ? Math.round(scrollPct * 100) : null
  const hasActiveContext = Boolean(contextResult || selectedQuote)
  const showMobileSheet = canUseQuoteMode && (hasActiveContext || contextLoading)

  if (loading) {
    return <ReaderChapterSkeleton />
  }

  if (error || !data) {
    return (
      <div className="reader-display-shell flex min-h-[100dvh] items-center justify-center bg-[#080d17] px-6 text-slate-300">
        <div className="w-full max-w-md rounded-lg border border-white/10 bg-white/[0.03] px-8 py-10 text-center">
          <p className="text-sm uppercase tracking-[0.22em] text-slate-500">Reader</p>
          <p className="mt-3 text-lg text-slate-100">{error ?? "Chapter not found"}</p>
        </div>
      </div>
    )
  }

  return (
    <div className={`reader-display-shell flex h-[100dvh] min-h-[100dvh] overflow-hidden transition-colors ${theme === "dark"
        ? "bg-[#070c16] text-stone-100"
        : "bg-stone-50 text-slate-950"
      }`}>
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <ReaderToolbar
          bookId={bookId}
          chapterNum={chapterNum}
          chapterTitle={data.chapter_title}
          totalChapters={data.total_chapters ?? null}
          wordsRead={wordsRead}
          totalWords={totalWords}
          onSummary={() => setShowSummary(true)}
          theme={theme}
          onToggleTheme={toggleTheme}
          fontSize={fontSize}
          onSetFontSize={setFontSize}
          fontFamily={fontFamily}
          onSetFontFamily={setFontFamily}
          displayStyle={displayStyle}
          onSetDisplayStyle={setDisplayStyle}
          quoteModeEnabled={quoteModeEnabled}
          canUseQuoteMode={canUseQuoteMode}
          onToggleQuoteMode={toggleQuoteMode}
          progressPercent={progressPercent}
        />
        <div
          ref={scrollRef}
          className={`reader-scrollbar min-h-0 flex-1 overflow-y-auto overscroll-y-contain ${theme === "dark" ? "bg-[#071211]" : ""}`}
        >
          <div className="mx-auto w-full max-w-[1620px] px-4 pb-12 pt-4 sm:px-6 lg:px-8 xl:px-10">
            <div className="grid gap-6 xl:grid-cols-[64px_minmax(0,1fr)_88px] xl:items-start">
              <ReaderQuickRail
                bookId={bookId}
                chapterNum={chapterNum}
                theme={theme}
                onSummary={() => setShowSummary(true)}
              />
              <ChapterText
                bookId={bookId}
                chapterNum={chapterNum}
                chapterTitle={data.chapter_title}
                totalChapters={data.total_chapters ?? null}
                canCopyManuscript={data.can_copy_manuscript ?? true}
                textUrl={data.text_url}
                textContent={data.text_content ?? null}
                htmlContent={data.html_content ?? null}
                media={data.media ?? []}
                characters={data.characters}
                onTap={tap}
                onQuoteSelect={(text) => setSelectedQuote(text)}
                theme={theme}
                fontSize={fontSize}
                fontFamily={fontFamily}
                displayStyle={displayStyle}
                quoteModeEnabled={quoteModeEnabled}
                canUseQuoteMode={canUseQuoteMode}
              />
              <ReadingProgressRail
                theme={theme}
                progressPercent={progressPercent}
                wordsRead={wordsRead}
                totalWords={totalWords}
              />
            </div>
            {showFeedbackPanel ? (
              <ReaderChapterFeedback
                bookId={bookId}
                chapterNum={chapterNum}
                theme={theme}
                chapterFeedback={data.beta_feedback ?? []}
              />
            ) : null}
          </div>
        </div>
      </div>

      {showMobileSheet ? (
        <button
          type="button"
          aria-label="Close reading context"
          onClick={clearPanel}
          className="fixed inset-0 z-30 bg-[rgba(2,6,23,0.52)] md:hidden"
        />
      ) : null}

      {(hasActiveContext || contextLoading) && (
        <ContextPanel
          result={contextResult}
          loading={contextLoading}
          onClose={clearPanel}
          mobileSheet={canUseQuoteMode}
          theme={theme}
          selectedQuote={selectedQuote}
          chapterNumber={chapterNum}
          chapterTitle={data.chapter_title}
          characters={data.characters}
        />
      )}

      {showSummary && (
        <SummaryPanel bookId={bookId} chapterNum={chapterNum} onClose={() => setShowSummary(false)} theme={theme} />
      )}
      <MobileActionBar
        actions={[
          { id: "reader-summary", label: "Summary", onSelect: () => setShowSummary(true), tone: "secondary" },
          { id: "reader-ask", label: "Ask LoreVia", href: `/${bookId}/ask` as Route },
        ]}
      />
    </div>
  )
}

function countWords(text: string): number {
  const normalized = text.replace(/\[\[IMAGE:[^\]]+\]\]/g, " ")
  const matches = normalized.match(/\b[\p{L}\p{N}']+\b/gu)
  return matches?.length ?? 0
}

function ReaderChapterSkeleton() {
  return (
    <div className="reader-display-shell flex h-[100dvh] min-h-[100dvh] overflow-hidden bg-[#070c16] text-stone-100" role="status" aria-label="Loading chapter" aria-busy="true">
      <span className="sr-only">Loading chapter</span>
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <header className="reader-app-chrome sticky top-0 z-20 shrink-0 border-b border-white/[0.08] bg-[#070d18]/96">
          <div className="mx-auto flex w-full max-w-[1620px] flex-col gap-4 px-4 py-4 sm:px-6 lg:px-8 xl:px-10">
            <div className="flex items-center justify-between gap-4">
              <Skeleton className="h-10 w-[154px] rounded-md bg-white/10" />
              <div className="hidden items-center gap-3 md:flex">
                <Skeleton className="h-11 w-28 rounded-md bg-white/10" />
                <Skeleton className="h-11 w-24 rounded-md bg-white/10" />
                <Skeleton className="h-11 w-24 rounded-md bg-white/10" />
              </div>
              <Skeleton className="h-10 w-20 rounded-md bg-white/10 md:hidden" />
            </div>
            <div>
              <Skeleton className="h-4 w-72 max-w-full bg-white/10" />
              <div className="mt-2.5 flex items-center gap-4">
                <Skeleton className="h-1 w-full rounded-full bg-white/10" />
                <Skeleton className="h-4 w-9 bg-white/10" />
              </div>
            </div>
          </div>
        </header>
        <div className="border-b border-white/[0.08] bg-[#0b1120]/94">
          <div className="mx-auto flex w-full max-w-[1620px] flex-wrap gap-3 px-4 py-3 sm:px-6 lg:px-8 xl:px-10">
            <Skeleton className="h-10 w-44 rounded-md bg-white/10" />
            <Skeleton className="h-10 w-64 rounded-md bg-white/10" />
            <Skeleton className="h-10 w-48 rounded-md bg-white/10" />
          </div>
        </div>
        <main className="reader-scrollbar min-h-0 flex-1 overflow-y-auto bg-[#071211]">
          <div className="mx-auto w-full max-w-[1620px] px-4 pb-12 pt-4 sm:px-6 lg:px-8 xl:px-10">
            <div className="grid gap-6 xl:grid-cols-[64px_minmax(0,1fr)_88px] xl:items-start">
              <div className="hidden space-y-3 xl:block">
                <Skeleton className="h-12 w-12 rounded-md bg-white/10" />
                <Skeleton className="h-12 w-12 rounded-md bg-white/10" />
              </div>
              <article className="mx-auto w-full max-w-[72ch] rounded-md border border-white/10 bg-white/[0.03] px-5 py-8 sm:px-8">
                <Skeleton className="h-8 w-2/3 bg-white/10" />
                <div className="mt-8 space-y-4">
                  {Array.from({ length: 12 }).map((_, index) => (
                    <Skeleton key={index} className={`h-5 bg-white/10 ${index % 4 === 3 ? "w-4/5" : "w-full"}`} />
                  ))}
                </div>
              </article>
              <div className="hidden space-y-3 xl:block">
                <Skeleton className="h-24 w-full rounded-md bg-white/10" />
                <Skeleton className="h-36 w-full rounded-md bg-white/10" />
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
