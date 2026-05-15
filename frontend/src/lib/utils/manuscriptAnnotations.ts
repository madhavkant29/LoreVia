import type { ManuscriptAnnotation, ManuscriptAnnotationCategory } from "@/types/book"

export const MANUSCRIPT_ANNOTATION_CATEGORIES: ManuscriptAnnotationCategory[] = [
  "general",
  "continuity",
  "character",
  "worldbuilding",
  "pacing",
  "line_edit",
  "theme",
]

export const MANUSCRIPT_ANNOTATION_CATEGORY_LABELS: Record<ManuscriptAnnotationCategory, string> = {
  general: "General",
  continuity: "Continuity",
  character: "Character",
  worldbuilding: "Worldbuilding",
  pacing: "Pacing",
  line_edit: "Line Edit",
  theme: "Theme",
}

const CONTEXT_WINDOW = 48
const HIGHLIGHT_NAMES = [
  "lorevia-annotation-open",
  "lorevia-annotation-resolved",
  "lorevia-annotation-active",
] as const

export interface ManuscriptSelectionAnchor {
  quote: string
  anchorContextBefore: string | null
  anchorContextAfter: string | null
  startOffset: number
  endOffset: number
}

type HighlightRegistryLike = {
  delete: (name: string) => void
  set: (name: string, value: unknown) => void
}

type HighlightConstructor = new (...ranges: Range[]) => unknown

export function buildAnnotationSelectionAnchor(editor: HTMLElement): ManuscriptSelectionAnchor | null {
  const selection = window.getSelection()
  if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return null

  const range = selection.getRangeAt(0)
  const anchorNode = range.commonAncestorContainer
  if (!editor.contains(anchorNode)) return null

  const rawQuote = range.toString()
  const quote = cleanAnnotationText(rawQuote)
  if (!quote) return null

  const beforeRange = range.cloneRange()
  beforeRange.selectNodeContents(editor)
  beforeRange.setEnd(range.startContainer, range.startOffset)

  const afterRange = range.cloneRange()
  afterRange.selectNodeContents(editor)
  afterRange.setStart(range.endContainer, range.endOffset)

  const startOffset = beforeRange.toString().length
  const endOffset = startOffset + rawQuote.length

  return {
    quote,
    anchorContextBefore: cleanAnnotationText(beforeRange.toString().slice(-CONTEXT_WINDOW)) || null,
    anchorContextAfter: cleanAnnotationText(afterRange.toString().slice(0, CONTEXT_WINDOW)) || null,
    startOffset,
    endOffset,
  }
}

export function applyAnnotationHighlights(
  editor: HTMLElement | null,
  annotations: ManuscriptAnnotation[],
  activeAnnotationId: string | null
) {
  const registry = getHighlightRegistry()
  clearAnnotationHighlights(registry)

  const rangesById = new Map<string, Range>()
  if (!editor || !registry) return rangesById

  const openRanges: Range[] = []
  const resolvedRanges: Range[] = []
  let activeRange: Range | null = null

  for (const annotation of annotations) {
    const range = resolveAnnotationRange(editor, annotation)
    if (!range) continue
    rangesById.set(annotation.id, range)
    if (annotation.id === activeAnnotationId) {
      activeRange = range
    }
    if (annotation.status === "resolved") {
      resolvedRanges.push(range)
      continue
    }
    openRanges.push(range)
  }

  const HighlightCtor = getHighlightConstructor()
  if (!HighlightCtor) return rangesById

  if (openRanges.length > 0) {
    registry.set("lorevia-annotation-open", new HighlightCtor(...openRanges))
  }
  if (resolvedRanges.length > 0) {
    registry.set("lorevia-annotation-resolved", new HighlightCtor(...resolvedRanges))
  }
  if (activeRange) {
    registry.set("lorevia-annotation-active", new HighlightCtor(activeRange))
  }

  return rangesById
}

export function clearAnnotationHighlights(registry = getHighlightRegistry()) {
  if (!registry) return
  for (const name of HIGHLIGHT_NAMES) {
    registry.delete(name)
  }
}

export function resolveAnnotationRange(editor: HTMLElement, annotation: Pick<ManuscriptAnnotation, "quote" | "anchor_context_before" | "anchor_context_after" | "start_offset" | "end_offset">) {
  const fullText = editor.textContent ?? ""
  const quote = cleanAnnotationText(annotation.quote)
  if (!fullText || !quote) return null

  const exactOffsets = resolveExactOffsets(fullText, annotation, quote)
  const match = exactOffsets ?? resolveBestTextMatch(fullText, annotation, quote)
  if (!match) return null

  return rangeFromOffsets(editor, match.start, match.end)
}

export function scrollAnnotationRangeIntoView(range: Range) {
  const rect = range.getBoundingClientRect()
  if (!rect.width && !rect.height) return
  window.scrollTo({
    top: Math.max(0, rect.top + window.scrollY - 160),
    behavior: "smooth",
  })
}

export function cleanAnnotationText(value: string | null | undefined) {
  return String(value ?? "").replace(/\s+/g, " ").trim()
}

function resolveExactOffsets(
  fullText: string,
  annotation: Pick<ManuscriptAnnotation, "quote" | "start_offset" | "end_offset">,
  cleanedQuote: string
) {
  const startOffset = annotation.start_offset
  const endOffset = annotation.end_offset
  if (typeof startOffset !== "number" || typeof endOffset !== "number") return null
  if (startOffset < 0 || endOffset <= startOffset || endOffset > fullText.length) return null

  const candidate = cleanAnnotationText(fullText.slice(startOffset, endOffset))
  if (candidate !== cleanedQuote) return null
  return { start: startOffset, end: endOffset }
}

function resolveBestTextMatch(
  fullText: string,
  annotation: Pick<ManuscriptAnnotation, "quote" | "anchor_context_before" | "anchor_context_after" | "start_offset">,
  cleanedQuote: string
) {
  const regex = new RegExp(escapeRegExp(cleanedQuote).replace(/\s+/g, "\\s+"), "gi")
  const matches: Array<{ start: number; end: number; score: number }> = []

  for (const match of fullText.matchAll(regex)) {
    const rawMatch = match[0]
    const start = match.index ?? 0
    const end = start + rawMatch.length
    const beforeText = cleanAnnotationText(fullText.slice(Math.max(0, start - CONTEXT_WINDOW), start))
    const afterText = cleanAnnotationText(fullText.slice(end, end + CONTEXT_WINDOW))
    let score = 0

    if (annotation.anchor_context_before && beforeText.endsWith(cleanAnnotationText(annotation.anchor_context_before))) {
      score += 30
    }
    if (annotation.anchor_context_after && afterText.startsWith(cleanAnnotationText(annotation.anchor_context_after))) {
      score += 30
    }
    if (typeof annotation.start_offset === "number") {
      score -= Math.min(20, Math.abs(annotation.start_offset - start))
    }

    matches.push({ start, end, score })
  }

  if (matches.length === 0) return null
  matches.sort((a, b) => b.score - a.score || a.start - b.start)
  return { start: matches[0].start, end: matches[0].end }
}

function rangeFromOffsets(root: HTMLElement, startOffset: number, endOffset: number) {
  const range = document.createRange()
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  let currentNode = walker.nextNode()
  let consumed = 0
  let startSet = false

  while (currentNode) {
    const textLength = currentNode.textContent?.length ?? 0
    const nextConsumed = consumed + textLength

    if (!startSet && startOffset <= nextConsumed) {
      range.setStart(currentNode, Math.max(0, startOffset - consumed))
      startSet = true
    }
    if (startSet && endOffset <= nextConsumed) {
      range.setEnd(currentNode, Math.max(0, endOffset - consumed))
      return range
    }

    consumed = nextConsumed
    currentNode = walker.nextNode()
  }

  return null
}

function getHighlightRegistry() {
  return (globalThis.CSS as typeof CSS & { highlights?: HighlightRegistryLike }).highlights
}

function getHighlightConstructor() {
  return (globalThis as typeof globalThis & { Highlight?: HighlightConstructor }).Highlight
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
}
