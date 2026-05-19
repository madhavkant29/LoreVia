import { parsePublishedTextBlocks } from "./publishedLayout"

export interface EditorSceneOutlineItem {
  index: number
  title: string
  excerpt: string
  wordCount: number
  readingTimeMinutes: number
}

export interface ManuscriptAutosaveDraft {
  title: string
  text: string
  html: string
  updatedAt: string
}

export interface SceneAutosaveDraft {
  title: string
  description: string
  body: string
  chapterNumber: number | null
  updatedAt: string
}

export const COMMENT_NOTE_PREFIX = "Comment:"

export function countWords(text: string) {
  return text.trim() ? text.trim().split(/\s+/).length : 0
}

export function estimateReadingTimeMinutes(wordCount: number, wordsPerMinute = 250) {
  if (wordCount <= 0) return 0
  return Math.max(1, Math.ceil(wordCount / wordsPerMinute))
}

export function formatReadingTimeLabel(minutes: number) {
  if (minutes <= 0) return "0 min read"
  if (minutes < 60) return `${minutes} min read`

  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  return remainingMinutes > 0
    ? `${hours} hr ${remainingMinutes} min read`
    : `${hours} hr read`
}

export function buildSceneOutline(text: string): EditorSceneOutlineItem[] {
  const blocks = parsePublishedTextBlocks(text)
  if (!blocks.length) return []

  const scenes: EditorSceneOutlineItem[] = []
  let currentBlocks: string[] = []

  const flushScene = () => {
    const joined = currentBlocks.join("\n\n").trim()
    currentBlocks = []
    if (!joined) return

    const lines = joined
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
    const excerpt = (lines[0] ?? joined).replace(/\s+/g, " ").trim()
    const wordCount = countWords(joined)
    const index = scenes.length + 1

    scenes.push({
      index,
      title: `Scene ${index}`,
      excerpt: excerpt.length > 84 ? `${excerpt.slice(0, 81).trimEnd()}...` : excerpt,
      wordCount,
      readingTimeMinutes: estimateReadingTimeMinutes(wordCount),
    })
  }

  for (const block of blocks) {
    if (block.type === "scene_break") {
      flushScene()
      continue
    }
    currentBlocks.push(block.content)
  }

  flushScene()
  return scenes
}

export function buildManuscriptAutosaveKey(bookId: string, chapterNumber: number) {
  return `lorevia:manuscript-autosave:${bookId}:chapter:${chapterNumber}`
}

export function buildSceneAutosaveKey(bookId: string, sceneKey: string) {
  return `lorevia:scene-autosave:${bookId}:scene:${sceneKey}`
}

export function serializeAutosaveDraft(draft: ManuscriptAutosaveDraft) {
  return JSON.stringify(draft)
}

export function parseAutosaveDraft(raw: string | null): ManuscriptAutosaveDraft | null {
  if (!raw) return null

  try {
    const parsed = JSON.parse(raw) as Partial<ManuscriptAutosaveDraft>
    if (
      typeof parsed.title !== "string"
      || typeof parsed.text !== "string"
      || typeof parsed.html !== "string"
      || typeof parsed.updatedAt !== "string"
    ) {
      return null
    }
    return parsed as ManuscriptAutosaveDraft
  } catch {
    return null
  }
}

export function serializeSceneAutosaveDraft(draft: SceneAutosaveDraft) {
  return JSON.stringify(draft)
}

export function parseSceneAutosaveDraft(raw: string | null): SceneAutosaveDraft | null {
  if (!raw) return null

  try {
    const parsed = JSON.parse(raw) as Partial<SceneAutosaveDraft>
    if (
      typeof parsed.title !== "string"
      || typeof parsed.description !== "string"
      || typeof parsed.body !== "string"
      || typeof parsed.updatedAt !== "string"
      || (parsed.chapterNumber !== null && typeof parsed.chapterNumber !== "number")
    ) {
      return null
    }
    return parsed as SceneAutosaveDraft
  } catch {
    return null
  }
}

export function isCommentNoteTitle(title: string | null | undefined) {
  return (title ?? "").trim().toLowerCase().startsWith(COMMENT_NOTE_PREFIX.toLowerCase())
}

export function buildCommentNoteTitle(selection: string) {
  const cleaned = selection.replace(/\s+/g, " ").trim()
  const excerpt = cleaned.length > 54 ? `${cleaned.slice(0, 51).trimEnd()}...` : cleaned
  return `${COMMENT_NOTE_PREFIX} ${excerpt || "Selected passage"}`
}

export function buildCommentNoteBody(selection: string, comment: string) {
  const cleanedSelection = selection.replace(/\s+/g, " ").trim()
  const cleanedComment = comment.trim()
  return [
    "<p><strong>Manuscript comment</strong></p>",
    `<blockquote>${escapeHtml(cleanedSelection)}</blockquote>`,
    `<p>${escapeHtml(cleanedComment).replace(/\n/g, "<br>")}</p>`,
  ].join("")
}

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
}
