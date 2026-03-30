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

export function ReaderToolbar({ bookId, chapterNum, totalChapters, onSummary, theme, onToggleTheme, fontSize, onSetFontSize, fontFamily, onSetFontFamily }: Props) {
  const chromeClass = theme === "dark"
    ? "border-white/10 bg-black text-white"
    : "border-gray-100 bg-white text-black"
  const mutedActionClass = theme === "dark"
    ? "text-gray-300 hover:text-white hover:bg-white/5"
    : "text-gray-600 hover:text-gray-900 hover:bg-gray-100"
  const navClass = theme === "dark"
    ? "border border-white/15 text-white hover:bg-white/10"
    : "border border-gray-200 text-black hover:bg-gray-50"

  const increaseFont = () => onSetFontSize(Math.min(fontSize + 2, 32))
  const decreaseFont = () => onSetFontSize(Math.max(fontSize - 2, 12))

  return (
    <header className={`flex items-center justify-between px-4 py-2 border-b shrink-0 transition-colors z-10 ${chromeClass}`}>
      <div className="flex items-center gap-3">
        <Link prefetch={false} href={`/${bookId}`} className={theme === "dark" ? "text-xs text-gray-500 hover:text-white" : "text-xs text-gray-400 hover:text-gray-600"}>
          {"<- Overview"}
        </Link>
        <div className="h-4 w-px bg-current opacity-10 mx-1" />
        <span className={theme === "dark" ? "text-xs font-medium text-gray-300" : "text-xs font-medium text-gray-500"}>
          Ch. {chapterNum}{totalChapters ? ` of ${totalChapters}` : ""}
        </span>
      </div>

      <div className="flex items-center gap-1.5 md:gap-3">
        {/* Typography Controls */}
        <div className="flex items-center border-x border-current opacity-30 px-2 mx-1 gap-1">
           <button onClick={decreaseFont} className={`p-1 rounded text-xs transition-colors ${mutedActionClass}`} title="Decrease font size">A-</button>
           <button onClick={increaseFont} className={`p-1 rounded text-xs transition-colors ${mutedActionClass}`} title="Increase font size">A+</button>
           <div className="w-px h-3 bg-current opacity-20 mx-1" />
           <button 
             onClick={() => onSetFontFamily(fontFamily === "serif" ? "sans" : fontFamily === "sans" ? "mono" : "serif")} 
             className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider transition-colors ${mutedActionClass}`}
            >
             {fontFamily}
           </button>
        </div>

        <button onClick={onSummary} className={`text-xs px-2.5 py-1.5 rounded-lg transition-colors hidden sm:block ${mutedActionClass}`}>
          Summary
        </button>
        <Link prefetch={false} href={`/${bookId}/search`} className={`text-xs px-2.5 py-1.5 rounded-lg transition-colors hidden md:block ${mutedActionClass}`}>
          Search
        </Link>
        
        <button onClick={onToggleTheme} className={`text-xs p-1.5 rounded-lg transition-colors ${mutedActionClass}`}>
          {theme === "dark" ? "☾" : "☼"}
        </button>

        <div className="flex items-center gap-1 ml-1">
          {chapterNum > 1 && (
            <Link prefetch={false} href={`/${bookId}/chapter/${chapterNum - 1}`} className={`text-xs p-1.5 rounded-lg transition-colors ${navClass}`}>
              {"<-"}
            </Link>
          )}
          <Link prefetch={false} href={`/${bookId}/chapter/${chapterNum + 1}`} className={`text-xs p-1.5 rounded-lg transition-colors ${navClass}`}>
            {"->"}
          </Link>
        </div>
      </div>
    </header>
  )
}
