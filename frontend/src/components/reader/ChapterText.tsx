"use client"
import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import type { ChapterCharacter, ChapterMedia } from "@/types/reader"

interface Props {
  bookId: string
  chapterNum: number
  chapterTitle: string | null
  totalChapters: number | null
  textUrl: string | null
  textContent: string | null
  media: ChapterMedia[]
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
  chapterTitle,
  totalChapters,
  textUrl,
  textContent,
  media,
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
    fetch(textUrl).then((r) => r.text()).then(setText).catch(() => setText(""))
  }, [textUrl, textContent])

  const handleMouseUp = useCallback(() => {
    if (!canUseQuoteMode || !quoteModeEnabled) return
    const rawSelection = window.getSelection()?.toString() ?? ""
    const next = rawSelection.trim()
    if (next && next.length > 1) {
      setSelected(next)
      onQuoteSelect(rawSelection)
    }
  }, [canUseQuoteMode, onQuoteSelect, quoteModeEnabled])

  if (!text) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-12">
        <div className="flex justify-center">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-violet-500 border-t-transparent" />
        </div>
      </div>
    )
  }

  const blocks = annotateWithMedia(text, characters, media)
  const mentionClass = theme === "dark"
    ? "cursor-pointer rounded border-b border-dashed border-indigo-200/45 px-0.5 text-stone-100 transition-colors hover:bg-indigo-200/10 hover:text-white"
    : "cursor-pointer rounded border-b border-dashed border-violet-500/55 px-0.5 text-stone-900 transition-colors hover:bg-violet-50"

  const cardTone = theme === "dark"
    ? {
        shell: "border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.04),rgba(255,255,255,0.02))] text-stone-100",
        helper: "text-stone-400",
        prose: "text-stone-100",
        heading: "text-white",
        media: "border-white/10 bg-white/5",
        aside: "border-white/10 bg-white/[0.04]",
        asideBox: "bg-black/20 text-stone-300",
        nav: "border-white/10 bg-white/5 text-stone-100 hover:bg-white/10",
        divider: "bg-white/10",
      }
    : {
        shell: "border-white/75 bg-[radial-gradient(circle_at_top,#f8f4ff,transparent_30%),linear-gradient(180deg,rgba(255,255,255,0.97),rgba(255,255,255,0.84))] text-stone-950",
        helper: "text-stone-500",
        prose: "text-stone-900",
        heading: "text-stone-950",
        media: "border-stone-200 bg-[#f7f3ee]",
        aside: "border-stone-200 bg-white/78 backdrop-blur",
        asideBox: "bg-[#f6f1ff] text-stone-600",
        nav: "border-stone-200 bg-white text-stone-700 hover:bg-stone-50",
        divider: "bg-violet-400",
      }

  const fontStack =
    fontFamily === "serif"
      ? '"Newsreader", "Merriweather", Georgia, serif'
      : fontFamily === "mono"
        ? '"SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace'
        : '"Inter", ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'

  return (
    <div className="mx-auto w-full px-4 pb-28 pt-8 sm:px-8 lg:px-10" onMouseUp={handleMouseUp} style={{ maxWidth: "1000px" }}>
      <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)] xl:items-start">
        <section className={`overflow-hidden rounded-[2rem] border shadow-[0_28px_100px_-68px_rgba(79,70,229,0.38)] ${cardTone.shell}`}>
          <div className="mx-auto max-w-[82ch] px-6 py-10 sm:px-10 sm:py-14">
            <p className={`text-center text-[12px] italic tracking-[0.02em] ${cardTone.helper}`} style={{ fontFamily: "var(--reader-label)" }}>
              Tap any word or select text for instant context
            </p>

            <header className="mb-14 mt-8">
              <p className="text-[11px] uppercase tracking-[0.36em] text-stone-400" style={{ fontFamily: "var(--reader-label)" }}>
                Chapter {chapterNum}{totalChapters ? ` of ${totalChapters}` : ""}
              </p>
              <h1 className={`mt-4 text-5xl font-light leading-tight sm:text-6xl ${cardTone.heading}`} style={{ fontFamily: "var(--reader-display)" }}>
                {chapterTitle || `Chapter ${chapterNum}`}
              </h1>
              <div className={`mt-6 h-[2px] w-16 ${cardTone.divider}`} />
            </header>

            <div
              className={`reader-text whitespace-pre-wrap ${cardTone.prose}`}
              style={{
                fontFamily: fontStack,
                fontSize: `${fontSize}px`,
                lineHeight: fontFamily === "sans" ? "1.88" : "1.96",
                maxWidth: "100%",
                wordBreak: "normal",
                overflowWrap: "normal",
                hyphens: "none",
              }}
            >
              {blocks.map((block, index) =>
                block.type === "media" ? (
                  mediaSrc(block.item) ? (
                    <figure key={`media-${index}`} className={`my-10 overflow-hidden rounded-[1.5rem] border p-3 ${cardTone.media}`}>
                      <div className="flex justify-center py-4">
                        <img
                          src={mediaSrc(block.item)}
                          alt={block.item.caption ?? `Inline chapter image ${block.item.sort_order + 1}`}
                          className="max-h-[28rem] w-auto rounded-[1rem] object-contain"
                        />
                      </div>
                      <figcaption className={`px-3 pb-3 text-center text-xs italic ${cardTone.helper}`} style={{ fontFamily: "var(--reader-label)" }}>
                        {block.item.caption ?? "Image from the source material, preserved in the reading flow."}
                      </figcaption>
                    </figure>
                  ) : null
                ) : (
                  <p key={`block-${index}`} className="mb-8">
                    {block.segments.map((segment, segmentIndex) =>
                      segment.type === "text" ? (
                        <span key={`text-${index}-${segmentIndex}`}>{segment.content}</span>
                      ) : (
                        <span
                          key={`mention-${index}-${segmentIndex}`}
                          className={mentionClass}
                          onClick={() => onTap(segment.content)}
                          title={`Tap for context: ${segment.content}`}
                        >
                          {segment.content}
                        </span>
                      )
                    )}
                  </p>
                )
              )}
            </div>

            <footer
              className={`mt-20 flex flex-col gap-3 border-t pt-8 text-sm italic sm:flex-row sm:items-center sm:justify-between ${theme === "dark" ? "border-white/10 text-stone-400" : "border-stone-200 text-stone-500"}`}
              style={{ fontFamily: "var(--reader-label)" }}
            >
              <span>{chapterTitle || `Chapter ${chapterNum}`}</span>
              <span>{countWords(text).toLocaleString()} words in this chapter</span>
            </footer>
          </div>
        </section>

        <div className="mx-auto mt-8 max-w-[72ch]">
          <div className={`rounded-[1.5rem] border p-4 ${cardTone.aside}`}>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${cardTone.helper}`}>Continue reading</p>
                <p className={`mt-1 text-sm ${cardTone.helper}`}>
                  {totalChapters ? `Chapter ${chapterNum} of ${totalChapters}` : `Chapter ${chapterNum}`}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link prefetch={false} href={`/${bookId}`} className={`rounded-full border px-4 py-2 text-sm font-medium transition ${cardTone.nav}`}>
                  Back to book
                </Link>
                {chapterNum > 1 ? (
                  <Link prefetch={false} href={`/${bookId}/chapter/${chapterNum - 1}`} className={`rounded-full border px-4 py-2 text-sm font-medium transition ${cardTone.nav}`}>
                    Previous chapter
                  </Link>
                ) : null}
                {totalChapters === null || chapterNum < totalChapters ? (
                  <Link prefetch={false} href={`/${bookId}/chapter/${chapterNum + 1}`} className={`rounded-full border px-4 py-2 text-sm font-medium transition ${cardTone.nav}`}>
                    Next chapter
                  </Link>
                ) : null}
              </div>
            </div>
          </div>
        </div>

        <div className={`mx-auto mt-8 max-w-[72ch] rounded-[1.5rem] border p-4 xl:hidden ${cardTone.aside}`}>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${cardTone.helper}`}>Chapter navigation</p>
              <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${cardTone.helper}`}>Continue reading</p>
              <p className={`mt-1 text-sm ${cardTone.helper}`}>
                {totalChapters ? `Chapter ${chapterNum} of ${totalChapters}` : `Chapter ${chapterNum}`}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link prefetch={false} href={`/${bookId}`} className={`rounded-full border px-4 py-2 text-sm font-medium transition ${cardTone.nav}`}>
                Back to book
              </Link>
              {chapterNum > 1 ? (
                <Link prefetch={false} href={`/${bookId}/chapter/${chapterNum - 1}`} className={`rounded-full border px-4 py-2 text-sm font-medium transition ${cardTone.nav}`}>
                  Previous chapter
                </Link>
              ) : null}
              {totalChapters === null || chapterNum < totalChapters ? (
                <Link prefetch={false} href={`/${bookId}/chapter/${chapterNum + 1}`} className={`rounded-full border px-4 py-2 text-sm font-medium transition ${cardTone.nav}`}>
                  Next chapter
                </Link>
              ) : null}
            </div>
          </div>
        </div>
      </div>

      <div className={`mx-auto mt-8 max-w-[72ch] rounded-[1.5rem] border p-4 xl:hidden ${cardTone.aside}`}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${cardTone.helper}`}>Chapter navigation</p>
            <p className={`mt-1 text-sm ${cardTone.helper}`}>
              {totalChapters ? `Chapter ${chapterNum} of ${totalChapters}` : `Chapter ${chapterNum}`}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link prefetch={false} href={`/${bookId}`} className={`rounded-full border px-4 py-2 text-sm font-medium transition ${cardTone.nav}`}>
              Back to book
            </Link>
            {chapterNum > 1 ? (
              <Link prefetch={false} href={`/${bookId}/chapter/${chapterNum - 1}`} className={`rounded-full border px-4 py-2 text-sm font-medium transition ${cardTone.nav}`}>
                Previous
              </Link>
            ) : null}
            {totalChapters === null || chapterNum < totalChapters ? (
              <Link prefetch={false} href={`/${bookId}/chapter/${chapterNum + 1}`} className={`rounded-full border px-4 py-2 text-sm font-medium transition ${cardTone.nav}`}>
                Next
              </Link>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  )
}

type Segment = { type: "text" | "mention"; content: string }
type RenderBlock = { type: "text"; segments: Segment[] } | { type: "media"; item: ChapterMedia }

function annotateWithMedia(text: string, characters: ChapterCharacter[], media: ChapterMedia[]): RenderBlock[] {
  const mediaMap = new Map(media.map((item) => [item.marker, item]))
  const parts = text.split(/(\[\[IMAGE:[^\]]+\]\])/g)
  const blocks: RenderBlock[] = []
  const usedMarkers = new Set<string>()

  for (const part of parts) {
    if (!part) continue
    const mediaItem = mediaMap.get(part)
    if (mediaItem) {
      blocks.push({ type: "media", item: mediaItem })
      usedMarkers.add(mediaItem.marker)
      continue
    }
    if (/^\[\[IMAGE:[^\]]+\]\]$/.test(part)) continue
    blocks.push({ type: "text", segments: annotate(part, characters) })
  }

  for (const item of media) {
    if (usedMarkers.has(item.marker)) continue
    blocks.push({ type: "media", item })
  }

  return blocks
}

function annotate(text: string, characters: ChapterCharacter[]): Segment[] {
  const names = characters
    .flatMap((character) => [character.name, ...(character.aliases ?? [])])
    .filter(Boolean)
    .sort((a, b) => b.length - a.length)

  const segments: Segment[] = []
  let remaining = text
  let lowerText = text.toLowerCase()

  while (remaining.length > 0) {
    let earliest = -1
    let matchedName = ""
    for (const name of names) {
      const index = lowerText.indexOf(name.toLowerCase())
      if (index !== -1 && (earliest === -1 || index < earliest)) {
        earliest = index
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
    lowerText = remaining.toLowerCase()
  }

  return segments
}

function mediaSrc(item: ChapterMedia): string {
  if (item.url) return item.url
  if (item.content_base64 && item.content_type) return `data:${item.content_type};base64,${item.content_base64}`
  return ""
}

function countWords(text: string): number {
  const normalized = text.replace(/\[\[IMAGE:[^\]]+\]\]/g, " ")
  const matches = normalized.match(/\b[\p{L}\p{N}']+\b/gu)
  return matches?.length ?? 0
}
