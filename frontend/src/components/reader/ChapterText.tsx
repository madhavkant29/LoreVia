"use client"
import React, { useCallback, useEffect, useMemo, useState } from "react"
import { parsePublishedTextBlocks } from "@/lib/utils/publishedLayout"
import { resolveReaderFontStack } from "@/lib/utils/readerTypography"
import { renderRichTextHtml } from "@/lib/utils/richText"
import { PRIVATE_SHARE_COPY_NOTICE, preventProtectedManuscriptCopy } from "@/lib/utils/manuscriptCopyProtection"
import type { ChapterCharacter, ChapterMedia, ReaderDisplayStyle } from "@/types/reader"
import { resolveMediaAssetSrc } from "@/lib/utils/assetUrls"
import type { PublishedBlockType } from "@/lib/utils/publishedLayout"
import type { ReaderFontFamily } from "@/lib/utils/readerTypography"

interface Props {
  bookId: string
  chapterNum: number
  chapterTitle: string | null
  totalChapters: number | null
  textUrl: string | null
  textContent: string | null
  htmlContent: string | null
  media: ChapterMedia[]
  characters: ChapterCharacter[]
  onTap: (word: string) => void
  onQuoteSelect: (text: string) => void
  theme: "light" | "dark"
  fontSize: number
  fontFamily: ReaderFontFamily
  displayStyle: ReaderDisplayStyle
  quoteModeEnabled: boolean
  canUseQuoteMode: boolean
  canCopyManuscript: boolean
}

export function ChapterText({
  bookId,
  chapterNum,
  chapterTitle,
  totalChapters,
  textUrl,
  textContent,
  htmlContent,
  media,
  characters,
  onTap,
  onQuoteSelect,
  theme,
  fontSize,
  fontFamily,
  displayStyle,
  quoteModeEnabled,
  canUseQuoteMode,
  canCopyManuscript,
}: Props) {
  const [text, setText] = useState("")
  const [copyNotice, setCopyNotice] = useState<string | null>(null)

  const handleMentionClick = useCallback((event: React.MouseEvent<HTMLElement>) => {
    const target = event.target
    if (!(target instanceof Element)) return

    const mentionElement = target.closest<HTMLElement>("[data-mention]")
    const mention = mentionElement?.dataset.mention?.trim()
    if (!mention) return

    event.preventDefault()
    onTap(mention)
  }, [onTap])

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
      onQuoteSelect(rawSelection)
    }
  }, [canUseQuoteMode, onQuoteSelect, quoteModeEnabled])

  useEffect(() => {
    if (canCopyManuscript) {
      setCopyNotice(null)
    }
  }, [canCopyManuscript])

  const handleProtectedCopy = useCallback((event: { preventDefault: () => void }) => {
    if (preventProtectedManuscriptCopy(event, canCopyManuscript)) {
      setCopyNotice(PRIVATE_SHARE_COPY_NOTICE)
    }
  }, [canCopyManuscript])

  const isPublishedLayout = displayStyle === "published"

  const hasHtmlImages = useMemo(
    () => Boolean(htmlContent && /<img\b/i.test(htmlContent)),
    [htmlContent],
  )
  const shouldRenderHtml = Boolean(htmlContent && (hasHtmlImages || !text))

  const blocks = useMemo(
    () => annotateWithMedia(text, characters, media, isPublishedLayout),
    [text, characters, media, isPublishedLayout],
  )

  const mentionClass = useMemo(
    () =>
      theme === "dark"
        ? "cursor-pointer rounded border-b border-dashed border-indigo-200/45 px-0.5 text-stone-100 transition-colors hover:bg-indigo-200/10 hover:text-white"
        : "cursor-pointer rounded border-b border-dashed border-violet-500/55 px-0.5 text-stone-900 transition-colors hover:bg-violet-50",
    [theme],
  )

  const cardTone = useMemo(
    () =>
      theme === "dark"
        ? {
            shell: "border-white/10 bg-white/[0.03] text-stone-100",
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
            shell: "border-stone-200 bg-white text-stone-950",
            helper: "text-stone-500",
            prose: "text-stone-900",
            heading: "text-stone-950",
            media: "border-stone-200 bg-[#f7f3ee]",
            aside: "border-stone-200 bg-white",
            asideBox: "bg-[#f6f1ff] text-stone-600",
            nav: "border-stone-200 bg-white text-stone-700 hover:bg-stone-50",
            divider: "bg-violet-400",
          },
    [theme],
  )

  const fontStack = useMemo(
    () => resolveReaderFontStack(fontFamily, displayStyle),
    [fontFamily, displayStyle],
  )

  if (!text && !htmlContent) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-12">
        <div className="flex justify-center">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-violet-500 border-t-transparent" />
        </div>
      </div>
    )
  }

  return (
    <div
      className={`mx-auto w-full max-w-[960px] px-1 pb-20 pt-2 sm:px-2 lg:px-3 ${isPublishedLayout ? "reader-display-published" : "reader-display-relaxed"}`}
      onMouseUp={handleMouseUp}
      onCopyCapture={handleProtectedCopy}
      onCutCapture={handleProtectedCopy}
    >
      <section className={`book-layout overflow-hidden rounded-lg border ${cardTone.shell}`}>
        <div className={isPublishedLayout ? "book-layout__page mx-auto px-5 py-8 sm:px-10 sm:py-12 lg:px-12 lg:py-14" : "mx-auto max-w-[82ch] px-5 py-8 sm:px-10 sm:py-12"}>
          <div className="reader-nonprint mb-14 text-center">
            <p className={`inline-flex items-center gap-2 text-3xs italic tracking-[0.01em] ${cardTone.helper}`} style={{ fontFamily: "var(--reader-label)" }}>
              <svg viewBox="0 0 16 16" aria-hidden="true" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.4">
                <path d="M8 1.75v3.1M8 11.15v3.1M1.75 8h3.1M11.15 8h3.1M3.25 3.25l2.2 2.2M10.55 10.55l2.2 2.2M12.75 3.25l-2.2 2.2M5.45 10.55l-2.2 2.2" />
              </svg>
              <span>Tap any word or select text for instant context</span>
            </p>
            {!canCopyManuscript ? (
              <p className={`reader-nonprint mt-3 text-center text-3xs font-semibold uppercase tracking-[0.18em] ${theme === "dark" ? "text-amber-300" : "text-amber-700"}`} style={{ fontFamily: "var(--reader-label)" }}>
                Private share: copying disabled
              </p>
            ) : null}
            {copyNotice ? (
              <p className={`reader-nonprint mt-2 text-center text-sm ${theme === "dark" ? "text-amber-200" : "text-amber-800"}`}>
                {copyNotice}
              </p>
            ) : null}
          </div>

          <header className={isPublishedLayout ? "book-layout__chapter-heading chapter-title" : "mb-14 mt-6"}>
            <p className="text-3xs uppercase tracking-[0.36em] text-stone-400" style={{ fontFamily: "var(--reader-label)" }}>
              Chapter {chapterNum}{totalChapters ? ` of ${totalChapters}` : ""}
            </p>
            <h1 className={`mt-4 text-5xl font-light leading-tight sm:text-6xl ${cardTone.heading}`} style={{ fontFamily: isPublishedLayout ? fontStack : "var(--reader-display)" }}>
              {chapterTitle || `Chapter ${chapterNum}`}
            </h1>
            <div className={`mt-6 h-[2px] w-20 ${isPublishedLayout ? "book-layout__title-rule" : cardTone.divider}`} />
          </header>

          {shouldRenderHtml ? (
            <div
              className={`reader-text note-rich-content ${isPublishedLayout ? "book-layout__body" : ""} ${cardTone.prose}`}
              onClick={handleMentionClick}
              style={{
                fontFamily: fontStack,
                fontSize: `${fontSize}px`,
                lineHeight: isPublishedLayout ? "1.78" : fontFamily === "sans" ? "1.9" : "1.98",
                maxWidth: "100%",
                wordBreak: "normal",
                overflowWrap: "normal",
                hyphens: "none",
              }}
              dangerouslySetInnerHTML={{ __html: renderRichTextHtml(htmlContent || text) }}
            />
          ) : (
            <div
              className={`reader-text ${isPublishedLayout ? "book-layout__body" : "whitespace-pre-wrap"} ${cardTone.prose}`}
              style={{
                fontFamily: fontStack,
                fontSize: `${fontSize}px`,
                lineHeight: isPublishedLayout ? "1.78" : fontFamily === "sans" ? "1.9" : "1.98",
                maxWidth: "100%",
                wordBreak: "normal",
                overflowWrap: "normal",
                hyphens: "none",
              }}
            >
              {blocks.map((block, index) =>
                block.type === "media" ? (
                  mediaSrc(block.item) ? (
                    <figure key={`media-${index}`} className={`my-12 overflow-hidden rounded-lg border p-3 ${cardTone.media}`}>
                      <div className="flex justify-center py-4">
                        <img
                          src={mediaSrc(block.item)}
                          alt={block.item.caption ?? `Inline chapter image ${block.item.sort_order + 1}`}
                          loading="lazy"
                          decoding="async"
                          className="max-h-[28rem] w-auto rounded-md object-contain"
                        />
                      </div>
                      <figcaption className={`px-3 pb-3 text-center text-xs italic ${cardTone.helper}`} style={{ fontFamily: "var(--reader-label)" }}>
                        {block.item.caption ?? "Image from the source material, preserved in the reading flow."}
                      </figcaption>
                    </figure>
                  ) : null
                ) : (
                  isPublishedLayout
                    ? renderPublishedTextBlock(block, index, mentionClass, onTap, fontStack)
                    : renderRelaxedTextBlock(block, index, mentionClass, onTap)
                )
              )}
            </div>
          )}

          <footer
            className={`reader-nonprint mt-20 flex flex-col gap-3 border-t pt-8 text-sm italic sm:flex-row sm:items-center sm:justify-between ${theme === "dark" ? "border-white/10 text-stone-400" : "border-stone-200 text-stone-500"}`}
            style={{ fontFamily: "var(--reader-label)" }}
          >
            <span>{chapterTitle || `Chapter ${chapterNum}`}</span>
            <span>{countWords(text).toLocaleString()} words in this chapter</span>
          </footer>
        </div>
      </section>
    </div>
  )
}

type Segment = { type: "text" | "mention"; content: string }
type RenderBlock =
  | { type: "text"; semanticType: PublishedBlockType; segments: Segment[] }
  | { type: "media"; item: ChapterMedia }

function annotateWithMedia(text: string, characters: ChapterCharacter[], media: ChapterMedia[], published: boolean): RenderBlock[] {
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
    if (published) {
      for (const parsedBlock of parsePublishedTextBlocks(part)) {
        blocks.push({
          type: "text",
          semanticType: parsedBlock.type,
          segments: annotate(parsedBlock.content, characters),
        })
      }
    } else {
      blocks.push({ type: "text", semanticType: "paragraph", segments: annotate(part, characters) })
    }
  }

  for (const item of media) {
    if (usedMarkers.has(item.marker)) continue
    blocks.push({ type: "media", item })
  }

  return blocks
}

function renderRelaxedTextBlock(
  block: Extract<RenderBlock, { type: "text" }>,
  index: number,
  mentionClass: string,
  onTap: (word: string) => void,
) {
  return (
    <p key={`block-${index}`} className="mb-8">
      {renderSegments(block.segments, index, mentionClass, onTap)}
    </p>
  )
}

function renderPublishedTextBlock(
  block: Extract<RenderBlock, { type: "text" }>,
  index: number,
  mentionClass: string,
  onTap: (word: string) => void,
  fontStack: string,
) {
  const blockClass = `book-block book-block--${block.semanticType}`
  const blockStyle = block.semanticType === "artifact" ? undefined : { fontFamily: fontStack }

  if (block.semanticType === "scene_break") {
    return (
      <div key={`block-${index}`} className={`${blockClass} scene-break`} style={blockStyle} aria-hidden="true">
        {renderSegments(block.segments, index, mentionClass, onTap)}
      </div>
    )
  }

  if (block.semanticType === "quote") {
    return (
      <blockquote
        key={`block-${index}`}
        className={`${blockClass} book-special-block`}
        style={{
          ...blockStyle,
          marginLeft: "clamp(1rem, 5vw, 2.8rem)",
          marginRight: "clamp(1rem, 5vw, 2.8rem)",
          paddingLeft: "1.25rem",
          paddingRight: "1.25rem",
        }}
      >
        {renderSegments(block.segments, index, mentionClass, onTap)}
      </blockquote>
    )
  }

  if (block.semanticType !== "paragraph" && block.semanticType !== "chapter_title") {
    return (
      <div key={`block-${index}`} className={`${blockClass} book-special-block`} style={blockStyle}>
        {renderSegments(block.segments, index, mentionClass, onTap)}
      </div>
    )
  }

  return (
    <p key={`block-${index}`} className={blockClass} style={blockStyle}>
      {renderSegments(block.segments, index, mentionClass, onTap)}
    </p>
  )
}

function renderSegments(
  segments: Segment[],
  blockIndex: number,
  mentionClass: string,
  onTap: (word: string) => void,
) {
  return segments.map((segment, segmentIndex) =>
    segment.type === "text" ? (
      <span key={`text-${blockIndex}-${segmentIndex}`}>{segment.content}</span>
    ) : (
      <span
        key={`mention-${blockIndex}-${segmentIndex}`}
        className={mentionClass}
        onClick={() => onTap(segment.content)}
        title={`Tap for context: ${segment.content}`}
      >
        {segment.content}
      </span>
    )
  )
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
  return resolveMediaAssetSrc(item)
}

function countWords(text: string): number {
  const normalized = text.replace(/\[\[IMAGE:[^\]]+\]\]/g, " ")
  const matches = normalized.match(/\b[\p{L}\p{N}']+\b/gu)
  return matches?.length ?? 0
}
