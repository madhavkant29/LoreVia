"use client"
import { useState, useEffect, useRef, useMemo } from "react"
import { useReader } from "@/lib/hooks/useReader"
import { ReaderToolbar } from "./ReaderToolbar"
import { ChapterText } from "./ChapterText"
import { ContextPanel } from "./ContextPanel"
import { SummaryPanel } from "./SummaryPanel"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { ReaderDisplayStyle } from "@/types/reader"

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

export function ReaderView({ bookId, chapterNum }: Props) {
  const { data, loading, error, tap, contextResult, contextLoading, clearContext, saveProgress } = useReader(bookId, chapterNum)
  const { theme: appTheme, setTheme: setAppTheme } = usePreferencesStore()
  const [showSummary, setShowSummary] = useState(false)
  const [selectedQuote, setSelectedQuote] = useState<string | null>(null)
  const [theme, setTheme] = useState<ReaderTheme>(appTheme)
  const [fontSize, setFontSize] = useState(20)
  const [fontFamily, setFontFamily] = useState<"serif" | "sans" | "mono">("serif")
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
    const storedTheme = window.localStorage.getItem("reader-theme") || window.localStorage.getItem("app-theme")
    if (storedTheme === "light" || storedTheme === "dark") setTheme(storedTheme)
    setSelectedQuote(null)
    setScrollPct(0)

    const storedSize = window.localStorage.getItem("reader-font-size")
    if (storedSize) setFontSize(parseInt(storedSize))

    const storedFont = window.localStorage.getItem("reader-font-family")
    if (storedFont === "serif" || storedFont === "sans" || storedFont === "mono") setFontFamily(storedFont)

    const storedDisplayStyle = window.localStorage.getItem("reader-display-style")
    if (storedDisplayStyle === "relaxed" || storedDisplayStyle === "published") setDisplayStyle(storedDisplayStyle)

    if (!storedTheme) {
      setTheme(window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
    }

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
    setTheme(appTheme)
  }, [appTheme])

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

  const toggleTheme = () => setTheme(current => current === "dark" ? "light" : "dark")
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
  const hasActiveContext = Boolean(contextResult || selectedQuote)
  const showMobileSheet = canUseQuoteMode && (hasActiveContext || contextLoading)

  if (loading) return <div className="flex justify-center py-20 text-gray-400">Loading chapter...</div>
  if (error || !data) return <div className="flex justify-center py-20 text-gray-400">{error ?? "Chapter not found"}</div>

  return (
    <div className={`reader-display-shell flex h-[100dvh] min-h-[100dvh] overflow-hidden transition-colors ${theme === "dark"
        ? "bg-[radial-gradient(circle_at_top,#20253f,#0b1020_58%,#090b12)] text-stone-100"
        : "bg-[linear-gradient(180deg,#fcf7ef_0%,#f7f2eb_45%,#f3efe9_100%)] text-slate-950"
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
        />
        <div ref={scrollRef} className="reader-scrollbar min-h-0 flex-1 overflow-y-auto overscroll-y-contain">
          <ChapterText
            bookId={bookId}
            chapterNum={chapterNum}
            chapterTitle={data.chapter_title}
            totalChapters={data.total_chapters ?? null}
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
        </div>
      </div>

      {showMobileSheet ? (
        <button
          type="button"
          aria-label="Close reading context"
          onClick={clearPanel}
          className="fixed inset-0 z-30 bg-[rgba(2,6,23,0.44)] backdrop-blur-[2px] md:hidden"
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
    </div>
  )
}

function countWords(text: string): number {
  const normalized = text.replace(/\[\[IMAGE:[^\]]+\]\]/g, " ")
  const matches = normalized.match(/\b[\p{L}\p{N}']+\b/gu)
  return matches?.length ?? 0
}
