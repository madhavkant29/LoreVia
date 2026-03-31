"use client"
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
}: Props) {
  const chromeClass = theme === "dark"
    ? "border-white/10 bg-black text-white"
    : "border-gray-100 bg-white text-black"
  const mutedActionClass = theme === "dark"
    ? "text-gray-300 hover:text-white hover:bg-white/5"
    : "text-gray-600 hover:text-gray-900 hover:bg-gray-100"
  const navClass = theme === "dark"
    ? "border border-white/15 text-white hover:bg-white/10"
    : "border border-gray-200 text-black hover:bg-gray-50"
  const linkClass = theme === "dark"
    ? "text-xs text-gray-400 hover:text-white"
    : "text-xs text-gray-500 hover:text-gray-700"

  const increaseFont = () => onSetFontSize(Math.min(fontSize + 2, 32))
  const decreaseFont = () => onSetFontSize(Math.max(fontSize - 2, 12))

  return (
    <header className={`z-10 flex shrink-0 items-center justify-between border-b px-4 py-2 transition-colors ${chromeClass}`}>
      <div className="flex items-center gap-3">
        <Link prefetch={false} href="/library" className={linkClass}>
          {"<- Library"}
        </Link>
        <div className="mx-1 h-4 w-px bg-current opacity-10" />
        <Link prefetch={false} href={`/${bookId}`} className={theme === "dark" ? "text-xs text-gray-500 hover:text-white" : "text-xs text-gray-400 hover:text-gray-600"}>
          {"<- Overview"}
        </Link>
        <div className="mx-1 h-4 w-px bg-current opacity-10" />
        <span className={theme === "dark" ? "text-xs font-medium text-gray-300" : "text-xs font-medium text-gray-500"}>
          Ch. {chapterNum}{totalChapters ? ` of ${totalChapters}` : ""}
        </span>
      </div>

      <div className="flex items-center gap-1.5 md:gap-3">
        <div className="mx-1 flex items-center gap-1 border-x border-current px-2 opacity-30">
          <button onClick={decreaseFont} className={`rounded p-1 text-xs transition-colors ${mutedActionClass}`} title="Decrease font size">
            A-
          </button>
          <button onClick={increaseFont} className={`rounded p-1 text-xs transition-colors ${mutedActionClass}`} title="Increase font size">
            A+
          </button>
          <div className="mx-1 h-3 w-px bg-current opacity-20" />
          <button
            onClick={() => onSetFontFamily(fontFamily === "serif" ? "sans" : fontFamily === "sans" ? "mono" : "serif")}
            className={`rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider transition-colors ${mutedActionClass}`}
          >
            {fontFamily}
          </button>
        </div>

        <button onClick={onSummary} className={`hidden rounded-lg px-2.5 py-1.5 text-xs transition-colors sm:block ${mutedActionClass}`}>
          Summary
        </button>
        <Link prefetch={false} href={`/${bookId}/search`} className={`hidden rounded-lg px-2.5 py-1.5 text-xs transition-colors md:block ${mutedActionClass}`}>
          Search
        </Link>

        <button onClick={onToggleTheme} className={`rounded-lg px-2 py-1.5 text-xs transition-colors ${mutedActionClass}`}>
          {theme === "dark" ? "Light" : "Dark"}
        </button>

        <div className="ml-1 flex items-center gap-1">
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
    </header>
  )
}
