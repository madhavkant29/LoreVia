"use client"
import { useState } from "react"
import Link from "next/link"

interface Props {
  bookId: string
  chapterNum: number
  chapterTitle: string | null
  totalChapters: number | null
  wordsRead: number
  totalWords: number
  onSummary: () => void
  theme: "light" | "dark"
  onToggleTheme: () => void
  fontSize: number
  onSetFontSize: (s: number) => void
  fontFamily: "serif" | "sans" | "mono"
  onSetFontFamily: (f: "serif" | "sans" | "mono") => void
  quoteModeEnabled: boolean
  canUseQuoteMode: boolean
  onToggleQuoteMode: () => void
}

export function ReaderToolbar({
  bookId,
  chapterNum,
  chapterTitle,
  totalChapters,
  wordsRead,
  totalWords,
  onSummary,
  theme,
  onToggleTheme,
  fontSize,
  onSetFontSize,
  fontFamily,
  onSetFontFamily,
  quoteModeEnabled,
  canUseQuoteMode,
  onToggleQuoteMode,
}: Props) {
  const [mobileToolsOpen, setMobileToolsOpen] = useState(false)
  const atLastChapter = totalChapters !== null && chapterNum >= totalChapters

  const toneClass = theme === "dark"
    ? {
        shell: "border-white/10 bg-[#0f1320]/92 text-stone-100",
        subShell: "border-white/10 bg-[#121828]/88",
        text: "text-stone-300",
        muted: "text-stone-400 hover:bg-white/6 hover:text-white",
        active: "bg-indigo-500 text-white hover:bg-indigo-400",
        pill: "border-white/10 bg-white/5 text-stone-300",
        border: "border-white/10",
        heading: "text-white",
      }
    : {
        shell: "border-stone-200/80 bg-[#fcfaf4]/92 text-stone-950",
        subShell: "border-stone-200/80 bg-white/72",
        text: "text-stone-500",
        muted: "text-stone-500 hover:bg-stone-100 hover:text-stone-900",
        active: "bg-[linear-gradient(135deg,#4f46e5,#4338ca)] text-white hover:opacity-95",
        pill: "border-stone-200 bg-white text-stone-600",
        border: "border-stone-200",
        heading: "text-stone-900",
      }

  const increaseFont = () => onSetFontSize(Math.min(fontSize + 2, 32))
  const decreaseFont = () => onSetFontSize(Math.max(fontSize - 2, 12))

  return (
    <header className="sticky top-0 z-20 shrink-0">
      <div className={`border-b backdrop-blur-xl ${toneClass.shell}`}>
        <div className="flex items-center justify-between gap-4 px-4 py-4 sm:px-8">
          <div className="min-w-0">
            <div className="flex items-center gap-4">
              <Link
                prefetch={false}
                href="/library"
                className={theme === "dark" ? "text-2xl italic text-indigo-200" : "text-2xl italic text-violet-700"}
                style={{ fontFamily: "var(--reader-display)" }}
              >
                LoreVia
              </Link>
              <nav className="hidden items-center gap-6 text-sm lg:flex" style={{ fontFamily: "var(--reader-label)" }}>
                <Link prefetch={false} href="/library" className={theme === "dark" ? "font-medium text-indigo-200" : "font-medium text-violet-700"}>
                  Library
                </Link>
                <Link prefetch={false} href="/settings" className={toneClass.muted}>
                  Settings
                </Link>
                <button onClick={onToggleTheme} className={`rounded-full px-3 py-1.5 transition-colors ${toneClass.muted}`}>
                  {theme === "dark" ? "Light" : "Dark"}
                </button>
              </nav>
            </div>
            <p className={`mt-2 hidden text-sm lg:block ${toneClass.text}`}>
              {chapterTitle || `Chapter ${chapterNum}`} • {wordsRead.toLocaleString()} of {totalWords.toLocaleString()} words
            </p>
          </div>

          <div className="hidden items-center gap-2 md:flex" style={{ fontFamily: "var(--reader-label)" }}>
            <Link prefetch={false} href={`/${bookId}`} className={`rounded-full px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] transition ${toneClass.active}`}>
              Back to book
            </Link>
            <button onClick={onSummary} className={`rounded-full px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] transition ${toneClass.muted}`}>
              Summary
            </button>
            <Link prefetch={false} href={`/${bookId}/graph`} className={`rounded-full px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] transition ${toneClass.muted}`}>
              Graph
            </Link>
            <Link prefetch={false} href={`/${bookId}/ask`} className={`rounded-full border px-4 py-2 text-xs transition ${toneClass.pill}`}>
              Ask with citations
            </Link>
            <Link prefetch={false} href={`/${bookId}/search`} className={`rounded-full border px-4 py-2 text-xs transition ${toneClass.pill}`}>
              Search passages
            </Link>
          </div>

          <button
            onClick={() => setMobileToolsOpen((current) => !current)}
            className={`rounded-full px-3 py-2 text-xs md:hidden ${toneClass.muted}`}
          >
            {mobileToolsOpen ? "Close" : "Menu"}
          </button>
        </div>
      </div>

      <div className={`border-b backdrop-blur-xl ${toneClass.subShell}`}>
        <div className="hidden items-center justify-between gap-4 px-6 py-3 md:flex" style={{ fontFamily: "var(--reader-label)" }}>
          <div className="flex items-center gap-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-violet-500">Overview</p>
            <p className={`text-[11px] uppercase tracking-[0.28em] ${toneClass.text}`}>
              Chapter {chapterNum}{totalChapters ? ` of ${totalChapters}` : ""}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <div className={`flex items-center gap-1 rounded-full border px-1.5 py-1 ${toneClass.pill}`}>
              <button onClick={decreaseFont} className={`rounded-full px-2 py-1 text-xs transition ${toneClass.muted}`} title="Decrease font size">
                A-
              </button>
              <span className="min-w-8 text-center text-xs">{fontSize}</span>
              <button onClick={increaseFont} className={`rounded-full px-2 py-1 text-xs transition ${toneClass.muted}`} title="Increase font size">
                A+
              </button>
              <div className={`mx-1 h-3 w-px ${toneClass.border}`} />
              {(["serif", "sans", "mono"] as const).map((option) => (
                <button
                  key={option}
                  onClick={() => onSetFontFamily(option)}
                  className={`rounded-full px-2 py-1 text-[10px] font-bold uppercase tracking-[0.18em] transition ${
                    fontFamily === option ? toneClass.active : toneClass.muted
                  }`}
                >
                  {option}
                </button>
              ))}
            </div>

            {canUseQuoteMode ? (
              <button
                onClick={onToggleQuoteMode}
                className={`rounded-full px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] transition ${
                  quoteModeEnabled ? toneClass.active : toneClass.muted
                }`}
              >
                {quoteModeEnabled ? "Quote mode" : "Quote select"}
              </button>
            ) : null}

            {chapterNum > 1 ? (
              <Link prefetch={false} href={`/${bookId}/chapter/${chapterNum - 1}`} className={`rounded-full border px-4 py-2 text-xs transition ${toneClass.pill}`}>
                Prev
              </Link>
            ) : null}
            {!atLastChapter ? (
              <Link prefetch={false} href={`/${bookId}/chapter/${chapterNum + 1}`} className={`rounded-full border px-4 py-2 text-xs transition ${toneClass.pill}`}>
                Next
              </Link>
            ) : null}
          </div>
        </div>

        <div className="space-y-3 px-4 py-3 md:hidden" style={{ fontFamily: "var(--reader-label)" }}>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[11px] uppercase tracking-[0.28em] text-violet-500">Chapter {chapterNum}</p>
              <p className={`mt-1 truncate text-lg font-semibold ${toneClass.heading}`}>
                {chapterTitle || `Chapter ${chapterNum}`}
              </p>
              <p className={`mt-1 text-xs ${toneClass.text}`}>
                {totalChapters ? `${chapterNum} of ${totalChapters}` : "Reader"} • {wordsRead.toLocaleString()} / {totalWords.toLocaleString()} words
              </p>
            </div>
            <div className="flex items-center gap-2">
              {chapterNum > 1 ? (
                <Link prefetch={false} href={`/${bookId}/chapter/${chapterNum - 1}`} className={`rounded-full border px-3 py-2 text-xs transition ${toneClass.pill}`}>
                  Prev
                </Link>
              ) : null}
              {!atLastChapter ? (
                <Link prefetch={false} href={`/${bookId}/chapter/${chapterNum + 1}`} className={`rounded-full border px-3 py-2 text-xs transition ${toneClass.pill}`}>
                  Next
                </Link>
              ) : null}
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Link prefetch={false} href={`/${bookId}`} className={`rounded-full px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] transition ${toneClass.active}`}>
              Back to book
            </Link>
            <button onClick={onSummary} className={`rounded-full px-4 py-2 text-xs transition ${toneClass.muted}`}>
              Summary
            </button>
            <Link prefetch={false} href={`/${bookId}/graph`} className={`rounded-full px-4 py-2 text-xs transition ${toneClass.muted}`}>
              Graph
            </Link>
            <Link prefetch={false} href={`/${bookId}/ask`} className={`rounded-full px-4 py-2 text-xs transition ${toneClass.muted}`}>
              Ask
            </Link>
            {canUseQuoteMode ? (
              <button onClick={onToggleQuoteMode} className={`rounded-full px-4 py-2 text-xs transition ${quoteModeEnabled ? toneClass.active : toneClass.muted}`}>
                {quoteModeEnabled ? "Quote on" : "Quote"}
              </button>
            ) : null}
          </div>

          {mobileToolsOpen ? (
            <div className={`rounded-[1.2rem] border p-3 ${toneClass.pill}`}>
              <div className="flex flex-wrap items-center gap-2">
                <button onClick={decreaseFont} className={`rounded-full px-3 py-2 text-xs transition ${toneClass.muted}`}>A-</button>
                <span className="text-xs">{fontSize}px</span>
                <button onClick={increaseFont} className={`rounded-full px-3 py-2 text-xs transition ${toneClass.muted}`}>A+</button>
                {(["serif", "sans", "mono"] as const).map((option) => (
                  <button
                    key={option}
                    onClick={() => onSetFontFamily(option)}
                    className={`rounded-full px-3 py-2 text-[11px] uppercase tracking-[0.18em] transition ${
                      fontFamily === option ? toneClass.active : toneClass.muted
                    }`}
                  >
                    {option}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </header>
  )
}
