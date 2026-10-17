"use client"

import Link from "next/link"
import type { Route } from "next"
import { memo, useEffect, useRef, useState, type ReactNode } from "react"

import { ThemeBrandImage } from "@/components/layout/ThemeBrandImage"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"
import { READER_FONT_OPTIONS, type ReaderFontFamily } from "@/lib/utils/readerTypography"
import type { ReaderDisplayStyle } from "@/types/reader"

interface Props {
  bookId: string
  chapterNum: number
  chapterTitle: string | null
  totalChapters: number | null
  previousChapter?: number | null
  nextChapter?: number | null
  wordsRead: number
  totalWords: number
  progressPercent: number | null
  onSummary: () => void
  theme: "light" | "dark"
  onToggleTheme: () => void
  fontSize: number
  onSetFontSize: (size: number) => void
  fontFamily: ReaderFontFamily
  onSetFontFamily: (family: ReaderFontFamily) => void
  displayStyle: ReaderDisplayStyle
  onSetDisplayStyle: (style: ReaderDisplayStyle) => void
  quoteModeEnabled: boolean
  canUseQuoteMode: boolean
  onToggleQuoteMode: () => void
}

type ToneClass = {
  shell: string
  panel: string
  border: string
  heading: string
  meta: string
  subtle: string
  ui: string
  ghost: string
  active: string
  progressTrack: string
  progressFill: string
}

export const ReaderToolbar = memo(function ReaderToolbar({
  bookId,
  chapterNum,
  chapterTitle,
  totalChapters,
  previousChapter = chapterNum > 1 ? chapterNum - 1 : null,
  nextChapter = totalChapters && chapterNum < totalChapters ? chapterNum + 1 : null,
  wordsRead,
  totalWords,
  progressPercent,
  onSummary,
  theme,
  onToggleTheme,
  fontSize,
  onSetFontSize,
  fontFamily,
  onSetFontFamily,
  displayStyle,
  onSetDisplayStyle,
  quoteModeEnabled,
  canUseQuoteMode,
  onToggleQuoteMode,
}: Props) {
  const [chapterToolsOpen, setChapterToolsOpen] = useState(false)
  const [readingSettingsOpen, setReadingSettingsOpen] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const headerRef = useRef<HTMLElement>(null)
  useEffect(() => {
    const close = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || (!chapterToolsOpen && !readingSettingsOpen && !mobileMenuOpen)) return
      const trigger = headerRef.current?.querySelector<HTMLButtonElement>('button[aria-expanded="true"]')
      setChapterToolsOpen(false); setReadingSettingsOpen(false); setMobileMenuOpen(false)
      trigger?.focus()
    }
    document.addEventListener("keydown", close)
    return () => document.removeEventListener("keydown", close)
  }, [chapterToolsOpen, readingSettingsOpen, mobileMenuOpen])
  const progressWidth = progressPercent !== null ? `${Math.max(0, Math.min(100, progressPercent))}%` : "0%"
  const chapterLabel = `Chapter ${chapterNum}`
  const wordLabel = `${wordsRead.toLocaleString()} of ${totalWords.toLocaleString()} words`

  const toneClass: ToneClass = theme === "dark"
    ? {
        shell: "border-white/[0.08] bg-[#070d18]/96 text-slate-100",
        panel: "border-white/[0.08] bg-[#0b1120]/96",
        border: "border-white/10",
        heading: "text-white",
        meta: "text-slate-400",
        subtle: "text-slate-400",
        ui: "text-slate-200",
        ghost: "border-white/10 bg-white/[0.025] text-slate-200 hover:bg-white/[0.06] hover:text-white",
        active: "border-teal-400/40 bg-teal-300/10 text-teal-50",
        progressTrack: "bg-white/[0.08]",
        progressFill: "bg-teal-500",
      }
    : {
        shell: "border-stone-200/80 bg-[#faf7f0]/96 text-stone-950",
        panel: "border-stone-200/80 bg-white/96",
        border: "border-stone-200",
        heading: "text-stone-950",
        meta: "text-stone-500",
        subtle: "text-stone-600",
        ui: "text-stone-700",
        ghost: "border-stone-200 bg-white text-stone-700 hover:border-stone-300 hover:text-stone-950",
        active: "border-teal-600/45 bg-teal-50 text-teal-950",
        progressTrack: "bg-stone-200/90",
        progressFill: "bg-teal-700",
      }

  const increaseFont = () => onSetFontSize(Math.min(fontSize + 2, 32))
  const decreaseFont = () => onSetFontSize(Math.max(fontSize - 2, 12))
  const openRecap = () => {
    setChapterToolsOpen(false)
    setMobileMenuOpen(false)
    onSummary()
  }

  const readingControls = (
    <ReadingControls
      toneClass={toneClass}
      fontSize={fontSize}
      onDecreaseFont={decreaseFont}
      onIncreaseFont={increaseFont}
      fontFamily={fontFamily}
      onSetFontFamily={onSetFontFamily}
      displayStyle={displayStyle}
      onSetDisplayStyle={onSetDisplayStyle}
      quoteModeEnabled={quoteModeEnabled}
      canUseQuoteMode={canUseQuoteMode}
      onToggleQuoteMode={onToggleQuoteMode}
    />
  )

  return (
    <header ref={headerRef} className="reader-app-chrome sticky top-0 z-20 shrink-0" style={{ fontFamily: "var(--reader-label)" }}>
      <div className={`border-b ${toneClass.shell}`}>
        <div className="mx-auto w-full max-w-[1620px] px-4 py-3 sm:px-6 lg:px-8 xl:px-10">
          <div className="flex items-center gap-3">
            <Link
              prefetch={false}
              href={`/${bookId}`}
              aria-label="Back to project overview"
              className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-md border ${toneClass.ghost}`}
            >
              <ThemeBrandImage variant="icon" alt="" className="h-6 w-6 object-contain" priority />
            </Link>

            <div className="min-w-0">
              <Link prefetch={false} href={`/${bookId}`} className={`text-xs font-medium ${toneClass.meta}`}>
                Project overview
              </Link>
              <p className={`truncate text-sm font-semibold ${toneClass.heading}`}>
                {chapterLabel} · {chapterTitle || "Untitled chapter"}
              </p>
            </div>

            <div className="ml-auto hidden items-center gap-2 md:flex">
              <ChapterNavigation bookId={bookId} previousChapter={previousChapter} nextChapter={nextChapter} toneClass={toneClass} />
              <button type="button" onClick={openRecap} className={`reader-control ${toneClass.ghost}`}>
                Recap
              </button>
              <button
                type="button"
                aria-expanded={chapterToolsOpen}
                aria-controls="reader-chapter-tools"
                onClick={() => {
                  setChapterToolsOpen((current) => !current)
                  setReadingSettingsOpen(false)
                }}
                className={`reader-control ${chapterToolsOpen ? toneClass.active : toneClass.ghost}`}
              >
                Chapter tools
              </button>
              <button
                type="button"
                aria-expanded={readingSettingsOpen}
                aria-controls="reader-reading-settings"
                onClick={() => {
                  setReadingSettingsOpen((current) => !current)
                  setChapterToolsOpen(false)
                }}
                className={`reader-control ${readingSettingsOpen ? toneClass.active : toneClass.ghost}`}
              >
                Text
              </button>
              <button type="button" onClick={onToggleTheme} className={`reader-control ${toneClass.ghost}`}>
                {theme === "dark" ? "Light" : "Dark"}
              </button>
            </div>

            <div className="ml-auto flex items-center gap-2 md:hidden">
              <ChapterNavigation bookId={bookId} previousChapter={previousChapter} nextChapter={nextChapter} toneClass={toneClass} compact />
              <button
                type="button"
                onClick={() => setMobileMenuOpen((current) => !current)}
                aria-expanded={mobileMenuOpen}
                aria-controls="reader-mobile-menu"
                className={`reader-control ${mobileMenuOpen ? toneClass.active : toneClass.ghost}`}
              >
                {mobileMenuOpen ? "Close" : "Menu"}
              </button>
            </div>
          </div>

          <div className="mt-3 flex items-center gap-3">
            <div role="progressbar" aria-label="Chapter scroll position" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progressPercent ?? undefined} className={`h-1 flex-1 overflow-hidden rounded-full ${toneClass.progressTrack}`}>
              <div className={`h-full rounded-full ${toneClass.progressFill}`} style={{ width: progressWidth }} />
            </div>
            <span className={`shrink-0 text-xs ${toneClass.meta}`}>{progressPercent !== null ? `${progressPercent}%` : wordLabel}</span>
          </div>
        </div>
      </div>

      {chapterToolsOpen ? (
        <div id="reader-chapter-tools" className={`hidden border-b md:block ${toneClass.panel}`}>
          <div className="mx-auto flex w-full max-w-[1620px] items-center gap-5 px-6 py-3 lg:px-8 xl:px-10">
            <p className={`text-xs font-semibold ${toneClass.heading}`}>This chapter</p>
            <ChapterToolLinks bookId={bookId} chapterNum={chapterNum} onSummary={openRecap} toneClass={toneClass} />
          </div>
        </div>
      ) : null}

      {readingSettingsOpen ? (
        <div id="reader-reading-settings" className={`hidden border-b md:block ${toneClass.panel}`}>
          <div className="mx-auto w-full max-w-[1620px] px-6 py-3 lg:px-8 xl:px-10">{readingControls}</div>
        </div>
      ) : null}

      {mobileMenuOpen ? (
        <div id="reader-mobile-menu" className={`max-h-[60dvh] overflow-y-auto border-b md:hidden ${toneClass.panel}`}>
          <div className="space-y-4 px-4 py-4 sm:px-6">
            <div>
              <p className={`mb-2 text-xs font-semibold ${toneClass.heading}`}>This chapter</p>
              <ChapterToolLinks bookId={bookId} chapterNum={chapterNum} onSummary={openRecap} toneClass={toneClass} />
            </div>
            <div className={`border-t pt-4 ${toneClass.border}`}>
              <div className="mb-3 flex items-center justify-between">
                <p className={`text-xs font-semibold ${toneClass.heading}`}>Reading settings</p>
                <button type="button" onClick={onToggleTheme} className={`reader-control ${toneClass.ghost}`}>
                  Use {theme === "dark" ? "light" : "dark"} theme
                </button>
              </div>
              {readingControls}
            </div>
          </div>
        </div>
      ) : null}
    </header>
  )
})

function ChapterNavigation({
  bookId,
  previousChapter,
  nextChapter,
  toneClass,
  compact = false,
}: {
  bookId: string
  previousChapter: number | null
  nextChapter: number | null
  toneClass: ToneClass
  compact?: boolean
}) {
  return (
    <nav aria-label="Chapter navigation" className="flex items-center gap-1">
      {previousChapter !== null ? (
        <Link prefetch={false} href={`/${bookId}/chapter/${previousChapter}`} aria-label="Previous chapter" className={`reader-control ${toneClass.ghost}`}>
          {compact ? "←" : "Previous"}
        </Link>
      ) : null}
      {nextChapter !== null ? (
        <Link prefetch={false} href={`/${bookId}/chapter/${nextChapter}`} aria-label="Next chapter" className={`reader-control ${toneClass.ghost}`}>
          {compact ? "→" : "Next"}
        </Link>
      ) : null}
    </nav>
  )
}

function ChapterToolLinks({
  bookId,
  chapterNum,
  onSummary,
  toneClass,
}: {
  bookId: string
  chapterNum: number
  onSummary: () => void
  toneClass: ToneClass
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <button type="button" onClick={onSummary} className={`text-sm font-medium ${toneClass.ui}`}>
        Recap
      </button>
      <Link prefetch={false} href={`/${bookId}/ask` as Route} className={`text-sm font-medium ${toneClass.ui}`}>
        Ask with citations
      </Link>
      <Link prefetch={false} href={`/${bookId}/search?chapter=${chapterNum}` as Route} className={`text-sm font-medium ${toneClass.ui}`}>
        Search this chapter
      </Link>
      <Link prefetch={false} href={`/${bookId}/notes?chapter=${chapterNum}` as Route} className={`text-sm font-medium ${toneClass.ui}`}>
        Chapter notes
      </Link>
      <button type="button" className={`min-h-11 text-sm font-medium ${toneClass.ui}`} onClick={() => window.dispatchEvent(new Event(SUPPORT_HELP_EVENT))}>Help</button>
    </div>
  )
}

function ReadingControls({
  toneClass,
  fontSize,
  onDecreaseFont,
  onIncreaseFont,
  fontFamily,
  onSetFontFamily,
  displayStyle,
  onSetDisplayStyle,
  quoteModeEnabled,
  canUseQuoteMode,
  onToggleQuoteMode,
}: {
  toneClass: ToneClass
  fontSize: number
  onDecreaseFont: () => void
  onIncreaseFont: () => void
  fontFamily: ReaderFontFamily
  onSetFontFamily: (family: ReaderFontFamily) => void
  displayStyle: ReaderDisplayStyle
  onSetDisplayStyle: (style: ReaderDisplayStyle) => void
  quoteModeEnabled: boolean
  canUseQuoteMode: boolean
  onToggleQuoteMode: () => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <ControlGroup label="Size" toneClass={toneClass}>
        <ControlButton label="A−" ariaLabel="Decrease font size" disabled={fontSize <= 12} onClick={onDecreaseFont} toneClass={toneClass} />
        <span className={`min-w-8 text-center text-sm ${toneClass.ui}`}>{fontSize}</span>
        <ControlButton label="A+" ariaLabel="Increase font size" disabled={fontSize >= 32} onClick={onIncreaseFont} toneClass={toneClass} />
      </ControlGroup>

      <ControlGroup label="Typeface" toneClass={toneClass}>
        {READER_FONT_OPTIONS.map((option) => (
          <ControlToggle
            key={option.value}
            label={option.label}
            ariaLabel={`Use ${option.label} font`}
            selected={fontFamily === option.value}
            onClick={() => onSetFontFamily(option.value)}
            toneClass={toneClass}
          />
        ))}
      </ControlGroup>

      <ControlGroup label="Layout" toneClass={toneClass}>
        <ControlToggle label="Published" ariaLabel="Use published reading mode" selected={displayStyle === "published"} onClick={() => onSetDisplayStyle("published")} toneClass={toneClass} />
        <ControlToggle label="Relaxed" ariaLabel="Use relaxed reading mode" selected={displayStyle === "relaxed"} onClick={() => onSetDisplayStyle("relaxed")} toneClass={toneClass} />
      </ControlGroup>

      {canUseQuoteMode ? (
        <ControlToggle
          label={quoteModeEnabled ? "Selecting quotes" : "Select a quote"}
          ariaLabel={quoteModeEnabled ? "Turn off quote selection mode" : "Turn on quote selection mode"}
          selected={quoteModeEnabled}
          onClick={onToggleQuoteMode}
          toneClass={toneClass}
        />
      ) : null}
    </div>
  )
}

function ControlGroup({ label, toneClass, children }: { label: string; toneClass: ToneClass; children: ReactNode }) {
  return (
    <div role="group" aria-label={label} className={`flex min-h-10 max-w-full flex-wrap items-center gap-1 rounded-md border px-1.5 py-1 ${toneClass.border}`}>
      <span className={`px-2 text-xs ${toneClass.subtle}`}>{label}</span>
      {children}
    </div>
  )
}

function ControlButton({ label, ariaLabel, onClick, toneClass, disabled }: { label: string; ariaLabel: string; onClick: () => void; toneClass: ToneClass; disabled?: boolean }) {
  return (
    <button type="button" disabled={disabled} aria-label={ariaLabel} onClick={onClick} className={`reader-control px-2 disabled:opacity-40 ${toneClass.ghost}`}>
      {label}
    </button>
  )
}

function ControlToggle({
  label,
  ariaLabel,
  selected,
  onClick,
  toneClass,
}: {
  label: string
  ariaLabel: string
  selected: boolean
  onClick: () => void
  toneClass: ToneClass
}) {
  return (
    <button
      type="button"
      aria-label={ariaLabel}
      aria-pressed={selected}
      onClick={onClick}
      className={`reader-control ${selected ? toneClass.active : toneClass.ghost}`}
    >
      {label}
    </button>
  )
}
