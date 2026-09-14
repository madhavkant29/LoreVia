"use client"
import { memo, useState, type ReactNode } from "react"
import Link from "next/link"
import { ThemeBrandImage } from "@/components/layout/ThemeBrandImage"
import { Tooltip } from "@/components/ui/Tooltip"
import { READER_FONT_OPTIONS, type ReaderFontFamily } from "@/lib/utils/readerTypography"
import type { ReaderDisplayStyle } from "@/types/reader"

interface Props {
  bookId: string
  chapterNum: number
  chapterTitle: string | null
  totalChapters: number | null
  wordsRead: number
  totalWords: number
  progressPercent: number | null
  onSummary: () => void
  theme: "light" | "dark"
  onToggleTheme: () => void
  fontSize: number
  onSetFontSize: (s: number) => void
  fontFamily: ReaderFontFamily
  onSetFontFamily: (f: ReaderFontFamily) => void
  displayStyle: ReaderDisplayStyle
  onSetDisplayStyle: (style: ReaderDisplayStyle) => void
  quoteModeEnabled: boolean
  canUseQuoteMode: boolean
  onToggleQuoteMode: () => void
}

export const ReaderToolbar = memo(function ReaderToolbar({
  bookId,
  chapterNum,
  chapterTitle,
  totalChapters,
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
  const [mobileToolsOpen, setMobileToolsOpen] = useState(false)
  const atLastChapter = totalChapters !== null && chapterNum >= totalChapters
  const progressWidth = progressPercent !== null ? `${Math.max(0, Math.min(100, progressPercent))}%` : "0%"
  const chapterMeta = `${chapterTitle || `Chapter ${chapterNum}`} | ${wordsRead.toLocaleString()} of ${totalWords.toLocaleString()} words`
  const breadcrumbLabel = `Chapter ${chapterNum}${totalChapters ? ` of ${totalChapters}` : ""}`

  const toneClass = theme === "dark"
    ? {
        shell: "border-white/[0.08] bg-[#070d18]/96 text-slate-100",
        subShell: "border-white/[0.08] bg-[#0b1120]/94",
        meta: "text-slate-400",
        subtle: "text-slate-500",
        heading: "text-white",
        ui: "text-slate-200",
        border: "border-white/10",
        card: "border-white/10 bg-[#0f1627]/92",
        divider: "bg-white/10",
        navLink: "text-slate-300 hover:text-white",
        ghost: "border-white/10 bg-[#11192b] text-slate-200 hover:bg-[#162036] hover:text-white",
        primary: "border-white/10 bg-[#151f35] text-white hover:bg-[#1a2741]",
        active: "border-[#7f86ff]/40 bg-[#353f71] text-white",
        progressTrack: "bg-white/[0.08]",
        progressFill: "bg-teal-600",
      }
    : {
        shell: "border-stone-200/80 bg-[#faf7f0]/94 text-stone-950",
        subShell: "border-stone-200/70 bg-white/88",
        meta: "text-stone-500",
        subtle: "text-stone-400",
        heading: "text-stone-950",
        ui: "text-stone-700",
        border: "border-stone-200",
        card: "border-stone-200 bg-white/92",
        divider: "bg-stone-200",
        navLink: "text-stone-600 hover:text-stone-950",
        ghost: "border-stone-200 bg-white text-stone-700 hover:bg-stone-50 hover:text-stone-950",
        primary: "border-violet-300/60 bg-white text-stone-950 hover:border-violet-400",
        active: "border-violet-400 bg-violet-50 text-violet-900",
        progressTrack: "bg-stone-200/90",
        progressFill: "bg-teal-700",
      }

  const increaseFont = () => onSetFontSize(Math.min(fontSize + 2, 32))
  const decreaseFont = () => onSetFontSize(Math.max(fontSize - 2, 12))

  return (
    <header className="reader-app-chrome sticky top-0 z-20 shrink-0">
      <div className={`border-b ${toneClass.shell}`}>
        <div className="mx-auto flex w-full max-w-[1620px] flex-col gap-4 px-4 py-4 sm:px-6 lg:px-8 xl:px-10">
          <div className="flex items-center justify-between gap-4">
            <div className="flex min-w-0 items-center gap-4">
              <Link prefetch={false} href="/library" className="shrink-0">
                <ThemeBrandImage variant="lockup" alt="LoreVia" className="h-10 w-[154px] object-contain object-left" priority />
              </Link>
              <nav className="hidden items-center gap-6 lg:flex" style={{ fontFamily: "var(--reader-label)" }}>
                <Link prefetch={false} href={`/${bookId}`} className={`text-base font-medium transition ${toneClass.navLink}`}>
                  Home
                </Link>
                <Link prefetch={false} href="/settings" className={`text-base font-medium transition ${toneClass.navLink}`}>
                  Settings
                </Link>
                <button
                  type="button"
                  onClick={onToggleTheme}
                  className={`rounded-md border px-4 py-2 text-base font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ${toneClass.ghost}`}
                >
                  {theme === "dark" ? "Light" : "Dark"}
                </button>
              </nav>
            </div>

            <div className="hidden flex-wrap items-center justify-end gap-3 md:flex" style={{ fontFamily: "var(--reader-label)" }}>
              <Link
                prefetch={false}
                href={`/${bookId}`}
                className={`inline-flex min-h-11 items-center rounded-md border px-4 py-2 text-base font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ${toneClass.primary}`}
              >
                Project overview
              </Link>
              <button
                type="button"
                onClick={onSummary}
                className={`inline-flex min-h-11 items-center rounded-md border px-4 py-2 text-base font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ${toneClass.ghost}`}
              >
                Summary
              </button>
              <Link
                prefetch={false}
                href={`/${bookId}/graph`}
                className={`inline-flex min-h-11 items-center rounded-md border px-4 py-2 text-base font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ${toneClass.ghost}`}
              >
                Graph
              </Link>
              <Link
                prefetch={false}
                href={`/${bookId}/ask`}
                className={`inline-flex min-h-11 items-center rounded-md border px-4 py-2 text-base font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ${toneClass.ghost}`}
              >
                Ask with citations
              </Link>
              <Link
                prefetch={false}
                href={`/${bookId}/search`}
                className={`inline-flex min-h-11 items-center rounded-md border px-4 py-2 text-base font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ${toneClass.ghost}`}
              >
                Search passages
              </Link>
            </div>

            <button
              type="button"
              onClick={() => setMobileToolsOpen((current) => !current)}
              aria-expanded={mobileToolsOpen}
              aria-label="Toggle reader menu"
              className={`rounded-md border px-4 py-2 text-base font-medium transition md:hidden ${toneClass.ghost}`}
            >
              {mobileToolsOpen ? "Close" : "Menu"}
            </button>
          </div>

          <div className="min-w-0">
            <p className={`text-sm ${toneClass.meta}`} style={{ fontFamily: "var(--reader-label)" }}>
              {chapterMeta}
            </p>
            <div className="mt-2.5 flex items-center gap-4">
              <div className={`h-[4px] flex-1 overflow-hidden rounded-full ${toneClass.progressTrack}`}>
                <div className={`h-full rounded-full ${toneClass.progressFill}`} style={{ width: progressWidth }} />
              </div>
              {progressPercent !== null ? (
                <span className={`w-9 text-right text-sm font-medium ${toneClass.ui}`} style={{ fontFamily: "var(--reader-label)" }}>
                  {progressPercent}%
                </span>
              ) : null}
            </div>
          </div>

          {mobileToolsOpen ? (
            <div className={`grid gap-3 rounded-lg border p-3 md:hidden ${toneClass.card}`} style={{ fontFamily: "var(--reader-label)" }}>
              <div className="flex flex-wrap gap-2">
                <Link prefetch={false} href={`/${bookId}`} className={`rounded-md border px-4 py-2 text-sm font-medium transition ${toneClass.ghost}`}>
                  Home
                </Link>
                <Link prefetch={false} href="/settings" className={`rounded-md border px-4 py-2 text-sm font-medium transition ${toneClass.ghost}`}>
                  Settings
                </Link>
                <button type="button" onClick={onToggleTheme} className={`rounded-md border px-4 py-2 text-sm font-medium transition ${toneClass.ghost}`}>
                  {theme === "dark" ? "Light" : "Dark"}
                </button>
              </div>
              <div className={`grid gap-2 border-t pt-3 ${toneClass.border}`}>
                <div className="flex flex-wrap gap-2">
                  <Link prefetch={false} href={`/${bookId}`} className={`rounded-md border px-4 py-2 text-sm font-medium transition ${toneClass.primary}`}>
                    Project overview
                  </Link>
                  <button type="button" onClick={onSummary} className={`rounded-md border px-4 py-2 text-sm font-medium transition ${toneClass.ghost}`}>
                    Summary
                  </button>
                  <Link prefetch={false} href={`/${bookId}/graph`} className={`rounded-md border px-4 py-2 text-sm font-medium transition ${toneClass.ghost}`}>
                    Graph
                  </Link>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Link prefetch={false} href={`/${bookId}/ask`} className={`rounded-md border px-4 py-2 text-sm font-medium transition ${toneClass.ghost}`}>
                    Ask with citations
                  </Link>
                  <Link prefetch={false} href={`/${bookId}/search`} className={`rounded-md border px-4 py-2 text-sm font-medium transition ${toneClass.ghost}`}>
                    Search passages
                  </Link>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <div className={`border-b ${toneClass.subShell}`}>
        <div className="mx-auto flex w-full max-w-[1620px] flex-col gap-3 px-4 py-3 sm:px-6 lg:px-8 xl:px-10" style={{ fontFamily: "var(--reader-label)" }}>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <Link prefetch={false} href={`/${bookId}`} className={`text-3xs font-semibold uppercase tracking-[0.28em] ${toneClass.navLink}`}>
              Home
            </Link>
            <span className={toneClass.subtle}>&gt;</span>
            <Link prefetch={false} href={`/${bookId}`} className={`text-3xs font-semibold uppercase tracking-[0.28em] ${toneClass.navLink}`}>
              Project overview
            </Link>
            <span className={toneClass.subtle}>&gt;</span>
            <p className={`text-3xs uppercase tracking-[0.28em] ${toneClass.ui}`}>
              {breadcrumbLabel}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 lg:gap-3">
            <SegmentGroup label="Font size" toneClass={toneClass}>
              <SegmentButton label="A-" ariaLabel="Decrease font size" tooltip="Decrease font size" onClick={decreaseFont} toneClass={toneClass} />
              <span className={`min-w-9 text-center text-sm ${toneClass.ui}`}>{fontSize}</span>
              <SegmentButton label="A+" ariaLabel="Increase font size" tooltip="Increase font size" onClick={increaseFont} toneClass={toneClass} />
            </SegmentGroup>

            <SegmentGroup label="Font family" toneClass={toneClass}>
              {READER_FONT_OPTIONS.map((option) => (
                <SegmentToggle
                  key={option.value}
                  label={option.label}
                  ariaLabel={`Use ${option.label} font`}
                  tooltip={`Use ${option.label} font`}
                  selected={fontFamily === option.value}
                  onClick={() => onSetFontFamily(option.value)}
                  toneClass={toneClass}
                />
              ))}
            </SegmentGroup>

            <SegmentGroup label="Reading mode" toneClass={toneClass}>
              {(["published", "relaxed"] as const).map((option) => (
                <SegmentToggle
                  key={option}
                  label={option === "published" ? "Published" : "Relaxed"}
                  ariaLabel={option === "published" ? "Use published reading mode" : "Use relaxed reading mode"}
                  tooltip={option === "published" ? "Use published reading mode" : "Use relaxed reading mode"}
                  selected={displayStyle === option}
                  onClick={() => onSetDisplayStyle(option)}
                  toneClass={toneClass}
                />
              ))}
            </SegmentGroup>

            {canUseQuoteMode ? (
              <SegmentGroup label="Selection" toneClass={toneClass}>
                <SegmentToggle
                  label={quoteModeEnabled ? "Quote mode" : "Quote select"}
                  ariaLabel={quoteModeEnabled ? "Turn off quote selection mode" : "Turn on quote selection mode"}
                  tooltip={quoteModeEnabled ? "Turn off quote selection mode" : "Turn on quote selection mode"}
                  selected={quoteModeEnabled}
                  onClick={onToggleQuoteMode}
                  toneClass={toneClass}
                />
              </SegmentGroup>
            ) : null}

            <SegmentGroup label="Navigation" toneClass={toneClass}>
              {chapterNum > 1 ? (
                <Link
                  prefetch={false}
                  href={`/${bookId}/chapter/${chapterNum - 1}`}
                  className={`inline-flex min-h-10 items-center rounded-md border px-3 py-2 text-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ${toneClass.ghost}`}
                >
                  Prev
                </Link>
              ) : null}
              {!atLastChapter ? (
                <Link
                  prefetch={false}
                  href={`/${bookId}/chapter/${chapterNum + 1}`}
                  className={`inline-flex min-h-10 items-center rounded-md border px-3 py-2 text-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ${toneClass.ghost}`}
                >
                  Next
                </Link>
              ) : null}
            </SegmentGroup>
          </div>
        </div>
      </div>
    </header>
  )
})

type ToneClass = {
  card: string
  divider: string
  subtle: string
  ui: string
  ghost: string
  active: string
}

function SegmentGroup({
  label,
  toneClass,
  children,
}: {
  label: string
  toneClass: ToneClass
  children: ReactNode
}) {
  return (
    <div role="group" aria-label={label} className={`flex min-h-11 min-w-0 max-w-full items-center gap-1 overflow-x-auto rounded-md border px-1.5 py-1 ${toneClass.card}`}>
      <span className={`shrink-0 px-2 text-3xs uppercase tracking-[0.22em] ${toneClass.subtle}`}>{label}</span>
      <div className={`mx-1 h-4 w-px shrink-0 ${toneClass.divider}`} />
      {children}
    </div>
  )
}

function SegmentButton({
  label,
  ariaLabel,
  tooltip,
  onClick,
  toneClass,
}: {
  label: string
  ariaLabel: string
  tooltip: string
  onClick: () => void
  toneClass: ToneClass
}) {
  const button = (
    <button
      type="button"
      aria-label={ariaLabel}
      onClick={onClick}
      className={`shrink-0 rounded-md border px-3 py-2 text-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ${toneClass.ghost}`}
    >
      {label}
    </button>
  )

  return <Tooltip content={tooltip}>{button}</Tooltip>
}

function SegmentToggle({
  label,
  ariaLabel,
  tooltip,
  selected,
  onClick,
  toneClass,
}: {
  label: string
  ariaLabel: string
  tooltip: string
  selected: boolean
  onClick: () => void
  toneClass: ToneClass
}) {
  const button = (
    <button
      type="button"
      aria-label={ariaLabel}
      aria-pressed={selected}
      onClick={onClick}
      className={`shrink-0 rounded-md border px-3 py-2 text-sm font-medium capitalize transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ${selected ? toneClass.active : toneClass.ghost}`}
    >
      {label}
    </button>
  )

  return <Tooltip content={tooltip}>{button}</Tooltip>
}
