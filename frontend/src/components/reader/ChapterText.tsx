"use client"
import { useEffect, useState, useCallback } from "react"
import type { ChapterCharacter } from "@/types/reader"

interface Props {
  textUrl: string | null
  textContent: string | null
  characters: ChapterCharacter[]
  onTap: (word: string) => void
}

export function ChapterText({ textUrl, textContent, characters, onTap }: Props) {
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

  // Annotate character names inline
  const segments = annotate(text, characters)

  return (
    <div className="max-w-2xl mx-auto px-6 py-12" onMouseUp={handleMouseUp}>
      <div className="reader-text select-text">
        {segments.map((seg, i) =>
          seg.type === "text" ? (
            <span key={i}>{seg.content}</span>
          ) : (
            <span
              key={i}
              className="border-b border-dashed border-indigo-300 cursor-pointer hover:bg-indigo-50 rounded transition-colors px-0.5"
              onClick={() => onTap(seg.content)}
              title={`Tap for context: ${seg.content}`}
            >
              {seg.content}
            </span>
          )
        )}
      </div>
      <p className="text-xs text-gray-300 mt-8 text-center">Tap any word or select text for instant context</p>
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
    let earliest = -1, matchedName = ""
    for (const name of names) {
      const idx = remaining.indexOf(name)
      if (idx !== -1 && (earliest === -1 || idx < earliest)) {
        earliest = idx; matchedName = name
      }
    }
    if (earliest === -1) { segments.push({ type: "text", content: remaining }); break }
    if (earliest > 0) segments.push({ type: "text", content: remaining.slice(0, earliest) })
    segments.push({ type: "mention", content: matchedName })
    remaining = remaining.slice(earliest + matchedName.length)
  }
  return segments
}
