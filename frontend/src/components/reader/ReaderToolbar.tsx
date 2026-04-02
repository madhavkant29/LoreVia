"use client"
import { useState } from "react"
import Link from "next/link"

interface Props {
  bookId: string
  chapterNum: number
  totalChapters: number | null
  onSummary: () => void
  theme: "light" | "dark"
  onToggleTheme: () => void
  fontSize: number
  onSetFontSize: (s: number) => void
  fontFamily: "serif" | "sans" | "mono"
  onSetFontFamily: (f: "serif" | "sans" | "mono") => void
  onBookmark: () => void
  bookmarked: boolean
  quoteModeEnabled: boolean
  canUseQuoteMode: boolean
  onToggleQuoteMode: () => void
}

export function ReaderToolbar({
  bookId,
  chapterNum,
  totalChapters,
  onSummary,
  theme,
  onToggleTheme,
  fontSize,
  onSetFontSize,
  fontFamily,
  onSetFontFamily,
  onBookmark,
  bookmarked,
  quoteModeEnabled,
  canUseQuoteMode,
  onToggleQuoteMode,
}: Props) {
  const [mobileToolsOpen, setMobileToolsOpen] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  const chromeClass = theme === "dark"
    ? "border-white/10 bg-[#15181b] text-stone-100"
    : "border-gray-100 bg-white text-black"
  const mutedActionClass = theme === "dark"
    ? "text-stone-300 hover:text-white hover:bg-white/10"
    : "text-gray-600 hover:text-gray-900 hover:bg-gray-100"
  const navClass = theme === "dark"
    ? "border border-white/15 text-stone-100 hover:bg-white/10"
    : "border border-gray-200 text-black hover:bg-gray-50"
  const linkClass = theme === "dark"
    ? "text-xs text-stone-400 hover:text-white"
    : "text-xs text-gray-500 hover:text-gray-700"

  const increaseFont = () => onSetFontSize(Math.min(fontSize + 2, 32))
  const decreaseFont = () => onSetFontSize(Math.max(fontSize - 2, 12))

  return (
    <header className={`z-10 shrink-0 border-b px-3 py-2 transition-colors sm:px-4 ${chromeClass}`}>
      <div className="hidden flex-col gap-2 md:flex md:flex-row md:items-center md:justify-between">
        <div className="app-scroll flex w-full items-center gap-3 overflow-x-auto sm:w-auto">
          <Link prefetch={false} href="/library" className={linkClass}>
            {"<- Dashboard"}
          </Link>
          <div className="mx-1 h-4 w-px bg-current opacity-10" />
          <Link prefetch={false} href={`/${bookId}`} className={theme === "dark" ? "text-xs text-stone-500 hover:text-white" : "text-xs text-gray-400 hover:text-gray-600"}>
            {"<- Overview"}
          </Link>
          <div className="mx-1 h-4 w-px bg-current opacity-10" />
          <span className={theme === "dark" ? "text-xs font-medium text-stone-300" : "text-xs font-medium text-gray-500"}>
            Ch. {chapterNum}{totalChapters ? ` of ${totalChapters}` : ""}
          </span>
        </div>

        <div className="app-scroll flex w-full items-center gap-1.5 overflow-x-auto md:gap-3 sm:w-auto">
          <div className={`mx-1 flex shrink-0 items-center gap-1 rounded-full border px-2 py-1 ${theme === "dark" ? "border-white/10 bg-white/5" : "border-gray-200 bg-gray-50"}`}>
            <span className={theme === "dark" ? "px-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-stone-400" : "px-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-gray-500"}>
              Type
            </span>
            <button onClick={decreaseFont} className={`rounded px-2 py-1 text-xs transition-colors ${mutedActionClass}`} title="Decrease font size">
              A-
            </button>
            <span className={theme === "dark" ? "min-w-8 text-center text-xs text-stone-300" : "min-w-8 text-center text-xs text-gray-600"}>
              {fontSize}
            </span>
            <button onClick={increaseFont} className={`rounded px-2 py-1 text-xs transition-colors ${mutedActionClass}`} title="Increase font size">
              A+
            </button>
            <div className="mx-1 h-3 w-px bg-current opacity-15" />
            <button
              onClick={() => onSetFontFamily(fontFamily === "serif" ? "sans" : fontFamily === "sans" ? "mono" : "serif")}
              className={`rounded px-2 py-1 text-[10px] font-bold uppercase tracking-wider transition-colors ${mutedActionClass}`}
            >
              {fontFamily}
            </button>
          </div>

          <button onClick={onSummary} className={`shrink-0 rounded-lg px-2.5 py-1.5 text-xs transition-colors ${mutedActionClass}`}>
            Summary
          </button>
          <button onClick={onBookmark} className={`shrink-0 rounded-lg px-2.5 py-1.5 text-xs transition-colors ${mutedActionClass}`}>
            {bookmarked ? "Bookmarked" : "Bookmark"}
          </button>
          {canUseQuoteMode ? (
            <button onClick={onToggleQuoteMode} className={`shrink-0 rounded-lg px-2.5 py-1.5 text-xs transition-colors ${quoteModeEnabled ? (theme === "dark" ? "bg-white/12 text-white" : "bg-slate-950 text-white") : mutedActionClass}`}>
              {quoteModeEnabled ? "Quote mode on" : "Quote select"}
            </button>
          ) : null}
          <Link prefetch={false} href={`/${bookId}/search`} className={`shrink-0 rounded-lg px-2.5 py-1.5 text-xs transition-colors ${mutedActionClass}`}>
            Search
          </Link>

          <button onClick={onToggleTheme} className={`shrink-0 rounded-lg px-2 py-1.5 text-xs transition-colors ${mutedActionClass}`}>
            {theme === "dark" ? "Light" : "Dark"}
          </button>

          <div className="ml-1 flex shrink-0 items-center gap-1">
            {chapterNum > 1 && (
              <Link prefetch={false} href={`/${bookId}/chapter/${chapterNum - 1}`} className={`rounded-lg p-1.5 text-xs transition-colors ${navClass}`}>
                {"<-"}
              </Link>
            )}
            <Link prefetch={false} href={`/${bookId}/chapter/${chapterNum + 1}`} className={`rounded-lg p-1.5 text-xs transition-colors ${navClass}`}>
              {"->"}
            </Link>
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-2 md:hidden">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className={theme === "dark" ? "text-[11px] uppercase tracking-[0.22em] text-stone-500" : "text-[11px] uppercase tracking-[0.22em] text-gray-400"}>
              Reader
            </p>
            <p className={theme === "dark" ? "truncate text-sm font-semibold text-stone-100" : "truncate text-sm font-semibold text-gray-900"}>
              Chapter {chapterNum}{totalChapters ? ` of ${totalChapters}` : ""}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setMobileNavOpen((current) => !current)} className={`rounded-full px-3 py-2 text-xs transition-colors ${mutedActionClass}`}>
              {mobileNavOpen ? "Close" : "Go"}
            </button>
            <button onClick={() => setMobileToolsOpen((current) => !current)} className={`rounded-full px-3 py-2 text-xs transition-colors ${mutedActionClass}`}>
              {mobileToolsOpen ? "Hide tools" : "Tools"}
            </button>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <button onClick={onSummary} className={`rounded-full px-3 py-2 text-xs transition-colors ${mutedActionClass}`}>
            Summary
          </button>
          <button onClick={onBookmark} className={`rounded-full px-3 py-2 text-xs transition-colors ${mutedActionClass}`}>
            {bookmarked ? "Bookmarked" : "Bookmark"}
          </button>
          {canUseQuoteMode ? (
            <button onClick={onToggleQuoteMode} className={`rounded-full px-3 py-2 text-xs transition-colors ${quoteModeEnabled ? (theme === "dark" ? "bg-white/12 text-white" : "bg-slate-950 text-white") : mutedActionClass}`}>
              {quoteModeEnabled ? "Quote on" : "Quote"}
            </button>
          ) : null}
        </div>

        {mobileNavOpen ? (
          <div className={`rounded-3xl border p-3 ${theme === "dark" ? "border-white/10 bg-white/[0.04]" : "border-gray-200 bg-gray-50"}`}>
            <div className="grid grid-cols-2 gap-2">
              <Link prefetch={false} href="/library" className={`rounded-2xl px-3 py-3 text-sm transition-colors ${mutedActionClass}`}>
                Dashboard
              </Link>
              <Link prefetch={false} href={`/${bookId}`} className={`rounded-2xl px-3 py-3 text-sm transition-colors ${mutedActionClass}`}>
                Overview
              </Link>
              {chapterNum > 1 ? (
                <Link prefetch={false} href={`/${bookId}/chapter/${chapterNum - 1}`} className={`rounded-2xl px-3 py-3 text-sm transition-colors ${navClass}`}>
                  Previous chapter
                </Link>
              ) : (
                <div className={`rounded-2xl border px-3 py-3 text-sm opacity-40 ${theme === "dark" ? "border-white/10 text-stone-500" : "border-gray-200 text-gray-400"}`}>
                  Previous chapter
                </div>
              )}
              <Link prefetch={false} href={`/${bookId}/chapter/${chapterNum + 1}`} className={`rounded-2xl px-3 py-3 text-sm transition-colors ${navClass}`}>
                Next chapter
              </Link>
            </div>
          </div>
        ) : null}

        {mobileToolsOpen ? (
          <div className={`rounded-3xl border p-3 ${theme === "dark" ? "border-white/10 bg-white/[0.04]" : "border-gray-200 bg-gray-50"}`}>
            <div className="space-y-3">
              <div>
                <p className={theme === "dark" ? "text-[11px] uppercase tracking-[0.22em] text-stone-500" : "text-[11px] uppercase tracking-[0.22em] text-gray-500"}>
                  Font size
                </p>
                <div className="mt-2 flex items-center gap-2">
                  <button onClick={decreaseFont} className={`rounded-full px-3 py-2 text-xs transition-colors ${mutedActionClass}`}>A-</button>
                  <div className={theme === "dark" ? "min-w-10 text-center text-sm text-stone-200" : "min-w-10 text-center text-sm text-gray-700"}>{fontSize}</div>
                  <button onClick={increaseFont} className={`rounded-full px-3 py-2 text-xs transition-colors ${mutedActionClass}`}>A+</button>
                </div>
              </div>

              <div>
                <p className={theme === "dark" ? "text-[11px] uppercase tracking-[0.22em] text-stone-500" : "text-[11px] uppercase tracking-[0.22em] text-gray-500"}>
                  Font family
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {(["serif", "sans", "mono"] as const).map((option) => (
                    <button
                      key={option}
                      onClick={() => onSetFontFamily(option)}
                      className={`rounded-full px-3 py-2 text-xs uppercase transition-colors ${
                        fontFamily === option
                          ? (theme === "dark" ? "bg-white text-slate-950" : "bg-slate-950 text-white")
                          : mutedActionClass
                      }`}
                    >
                      {option}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                <button onClick={onToggleTheme} className={`rounded-full px-3 py-2 text-xs transition-colors ${mutedActionClass}`}>
                  {theme === "dark" ? "Light mode" : "Dark mode"}
                </button>
                <Link prefetch={false} href={`/${bookId}/search`} className={`rounded-full px-3 py-2 text-xs transition-colors ${mutedActionClass}`}>
                  Search
                </Link>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </header>
  )
}
