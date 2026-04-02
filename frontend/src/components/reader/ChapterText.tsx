"use client"
import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import type { ChapterCharacter } from "@/types/reader"

interface Props {
  bookId: string
  chapterNum: number
  totalChapters: number | null
  textUrl: string | null
  textContent: string | null
  characters: ChapterCharacter[]
  onTap: (word: string) => void
  onQuoteSelect: (text: string) => void
  theme: "light" | "dark"
  fontSize: number
  fontFamily: "serif" | "sans" | "mono"
  quoteModeEnabled: boolean
  canUseQuoteMode: boolean
}

export function ChapterText({
  bookId,
  chapterNum,
  totalChapters,
  textUrl,
  textContent,
  characters,
  onTap,
  onQuoteSelect,
  theme,
  fontSize,
  fontFamily,
  quoteModeEnabled,
  canUseQuoteMode,
}: Props) {
  const [text, setText] = useState("")
  const [selected, setSelected] = useState("")

  useEffect(() => {
    if (textContent) {
      setText(textContent)
      return
    }
    if (!textUrl) return
    fetch(textUrl).then(r => r.text()).then(setText).catch(() => setText(""))
  }, [textUrl, textContent])

  const handleMouseUp = useCallback(() => {
    if (!canUseQuoteMode || !quoteModeEnabled) return
    const rawSelection = window.getSelection()?.toString() ?? ""
    const sel = rawSelection.trim()
    if (sel && sel.length > 1) {
      setSelected(sel)
      onQuoteSelect(rawSelection)
    }
  }, [canUseQuoteMode, quoteModeEnabled, onQuoteSelect])

  if (!text) return (
    <div className="mx-auto max-w-2xl px-6 py-12">
      <div className="flex justify-center"><div className="h-5 w-5 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent" /></div>
    </div>
  )

  const segments = annotate(text, characters)
  const surfaceClass = theme === "dark" ? "bg-[#111315] text-stone-100" : "bg-white text-black"
  const mentionClass = theme === "dark"
    ? "cursor-pointer rounded border-b border-dashed border-stone-300/45 px-0.5 transition-colors hover:bg-white/10"
    : "cursor-pointer rounded border-b border-dashed border-black/40 px-0.5 transition-colors hover:bg-black/5"
  const helperClass = theme === "dark" ? "text-stone-400" : "text-gray-500"
  const navShellClass = theme === "dark"
    ? "border-white/10 bg-white/[0.04]"
    : "border-slate-200 bg-slate-50"
  const navLinkClass = theme === "dark"
    ? "border-white/10 bg-white/5 text-stone-100 hover:bg-white/10"
    : "border-slate-200 bg-white text-slate-900 hover:bg-slate-100"
  const navMetaClass = theme === "dark" ? "text-stone-400" : "text-slate-500"

  const fontStack =
    fontFamily === "serif"
      ? '"Merriweather", Georgia, serif'
      : fontFamily === "mono"
        ? '"SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace'
        : 'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'

  return (
    <div
      className={`mx-auto px-6 py-12 transition-colors ${surfaceClass}`}
      onMouseUp={handleMouseUp}
      style={{
        maxWidth: `${Math.min(1120, 760 + Math.max(0, fontSize - 18) * 18)}px`,
      }}
    >
      <div
        className="reader-text select-text whitespace-pre-wrap"
        style={{
          fontFamily: fontStack,
          fontSize: `${fontSize}px`,
          lineHeight: "1.75",
          maxWidth: "100%",
          wordBreak: "normal",
          overflowWrap: "normal",
          hyphens: "none",
        }}
      >
        {segments.map((seg, i) =>
          seg.type === "text" ? (
            <span key={i}>{seg.content}</span>
          ) : (
            <span
              key={i}
              className={mentionClass}
              onClick={() => onTap(seg.content)}
              title={`Tap for context: ${seg.content}`}
            >
              {seg.content}
            </span>
          )
        )}
      </div>
      <p className={`mt-12 text-center text-xs italic ${helperClass}`} style={{ fontSize: "12px", opacity: theme === "dark" ? 0.72 : 0.48 }}>
        {quoteModeEnabled && canUseQuoteMode
          ? (selected ? "Selected text is ready for the side context panel." : "Quote mode is on. Select a passage to save it.")
          : "Tap any character name for instant details."}
      </p>
      <div className={`mt-10 rounded-3xl border p-4 ${navShellClass}`}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${navMetaClass}`}>Chapter navigation</p>
            <p className={`mt-1 text-sm ${navMetaClass}`}>
              {totalChapters ? `Chapter ${chapterNum} of ${totalChapters}` : `Chapter ${chapterNum}`}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              prefetch={false}
              href={`/${bookId}`}
              className={`rounded-full border px-4 py-2 text-sm font-medium transition ${navLinkClass}`}
            >
              Back to book
            </Link>
            {chapterNum > 1 ? (
              <Link
                prefetch={false}
                href={`/${bookId}/chapter/${chapterNum - 1}`}
                className={`rounded-full border px-4 py-2 text-sm font-medium transition ${navLinkClass}`}
              >
                Previous chapter
              </Link>
            ) : null}
            {totalChapters === null || chapterNum < totalChapters ? (
              <Link
                prefetch={false}
                href={`/${bookId}/chapter/${chapterNum + 1}`}
                className={`rounded-full border px-4 py-2 text-sm font-medium transition ${navLinkClass}`}
              >
                Next chapter
              </Link>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  )
}

type Segment = { type: "text" | "mention"; content: string }

function annotate(text: string, characters: ChapterCharacter[]): Segment[] {
  const names = characters
    .flatMap(c => [c.name, ...(c.aliases ?? [])])
    .filter(Boolean)
    .sort((a, b) => b.length - a.length)

  const segments: Segment[] = []
  let remaining = text

  while (remaining.length > 0) {
    let earliest = -1
    let matchedName = ""
    for (const name of names) {
      const idx = remaining.indexOf(name)
      if (idx !== -1 && (earliest === -1 || idx < earliest)) {
        earliest = idx
        matchedName = name
      }
    }
    if (earliest === -1) {
      segments.push({ type: "text", content: remaining })
      break
    }
    if (earliest > 0) segments.push({ type: "text", content: remaining.slice(0, earliest) })
    segments.push({ type: "mention", content: matchedName })
    remaining = remaining.slice(earliest + matchedName.length)
  }
  return segments
}
