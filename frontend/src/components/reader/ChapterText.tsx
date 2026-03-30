"use client"
import { useEffect, useState, useCallback } from "react"
import type { ChapterCharacter } from "@/types/reader"

interface Props {
  textUrl: string | null
  textContent: string | null
  characters: ChapterCharacter[]
  onTap: (word: string) => void
  theme: "light" | "dark"
  fontSize: number
  fontFamily: "serif" | "sans" | "mono"
}

export function ChapterText({ textUrl, textContent, characters, onTap, theme, fontSize, fontFamily }: Props) {
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
    const sel = window.getSelection()?.toString().trim()
    if (sel && sel.length > 1 && sel.length < 50) {
      setSelected(sel)
      onTap(sel)
    }
  }, [onTap])

  if (!text) return (
    <div className="max-w-2xl mx-auto px-6 py-12">
      <div className="flex justify-center"><div className="w-5 h-5 rounded-full border-2 border-indigo-400 border-t-transparent animate-spin" /></div>
    </div>
  )

  const segments = annotate(text, characters)
  const surfaceClass = theme === "dark" ? "bg-black text-white" : "bg-white text-black"
  const mentionClass = theme === "dark"
    ? "border-b border-dashed border-white/40 cursor-pointer hover:bg-white/10 rounded transition-colors px-0.5"
    : "border-b border-dashed border-black/40 cursor-pointer hover:bg-black/5 rounded transition-colors px-0.5"
  const helperClass = theme === "dark" ? "text-gray-500" : "text-gray-500"

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
        maxWidth: `${Math.min(1120, 760 + Math.max(0, fontSize - 18) * 18)}px`
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
      <p className={`text-xs mt-12 text-center opacity-40 italic ${helperClass}`} style={{ fontSize: "12px" }}>
        {selected ? `Context for "${selected}"` : "Tap any character name or select text for instant details"}
      </p>
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
