export type PublishedBlockType =
  | "paragraph"
  | "chapter_title"
  | "scene_break"
  | "quote"
  | "letter"
  | "broadcast"
  | "poem"
  | "artifact"

export interface PublishedTextBlock {
  type: PublishedBlockType
  content: string
}

const SCENE_BREAK_PATTERN = /^(?:(?:\*\s*){3,}|#{1,3}|[-–—]{3,}|[~]{3,})$/
const QUOTE_PREFIX_PATTERN = /^(?:>\s*)+/
const BROADCAST_PATTERN = /^(?:radio|tv|television|news|broadcast|announcer|reporter)\s*[:\-]/i
const ARTIFACT_PATTERN = /^(?:system|terminal|log|record|transcript|artifact)\s*[:\-]/i
const DOCUMENT_PATTERN = /^(?:document|excerpt|file|report|memo)\s*[:\-]/i
const LETTER_START_PATTERN = /^(?:dear\b|to\s+.+[,;:]?$)/i
const LETTER_END_PATTERN = /^(?:sincerely|yours|regards|respectfully|love|signed)[,;:]?/i

export function parsePublishedTextBlocks(text: string): PublishedTextBlock[] {
  return splitIntoRawBlocks(text).map((block) => ({
    type: detectPublishedBlockType(block),
    content: normalizeBlockContent(block),
  }))
}

export function detectPublishedBlockType(block: string): PublishedBlockType {
  const rawLines = block.replace(/\r\n?/g, "\n").split("\n").map((line) => line.trim()).filter(Boolean)
  const normalized = normalizeBlockContent(block)
  const firstLine = normalized.split("\n")[0]?.trim() ?? ""
  const lines = normalized.split("\n").map((line) => line.trim()).filter(Boolean)

  if (!normalized) return "paragraph"
  if (SCENE_BREAK_PATTERN.test(normalized.replace(/\s+/g, " ").trim())) return "scene_break"
  if (rawLines.length > 0 && rawLines.every((line) => QUOTE_PREFIX_PATTERN.test(line))) return "quote"
  if (BROADCAST_PATTERN.test(firstLine)) return "broadcast"
  if (ARTIFACT_PATTERN.test(firstLine)) return "artifact"
  if (DOCUMENT_PATTERN.test(firstLine)) return "quote"
  if (looksLikeLetter(lines)) return "letter"
  if (looksLikePoem(lines)) return "poem"

  return "paragraph"
}

function splitIntoRawBlocks(text: string): string[] {
  return text
    .replace(/\r\n?/g, "\n")
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean)
}

function normalizeBlockContent(block: string): string {
  return block
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map((line) => line.replace(QUOTE_PREFIX_PATTERN, "").trimEnd())
    .join("\n")
    .trim()
}

function looksLikeLetter(lines: string[]): boolean {
  if (lines.length < 2) return false
  const firstLine = lines[0] ?? ""
  const lastTwoLines = lines.slice(-2)
  return LETTER_START_PATTERN.test(firstLine) || lastTwoLines.some((line) => LETTER_END_PATTERN.test(line))
}

function looksLikePoem(lines: string[]): boolean {
  if (lines.length < 3) return false
  const shortLineCount = lines.filter((line) => line.length <= 52).length
  const sentenceEndCount = lines.filter((line) => /[.!?]["')\]]?$/.test(line)).length
  return shortLineCount === lines.length && sentenceEndCount <= Math.ceil(lines.length / 3)
}
