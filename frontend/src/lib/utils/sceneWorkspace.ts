import type { WorkspaceChapterNode } from "@/types/book"

const CHAPTER_FOLDER_PATTERN = /(?:^|\/)chapter[-_\s]?(\d+)(?:\/|$)/i

export function extractChapterNumberFromSceneFolder(path: string | null | undefined) {
  if (!path) return null
  const normalizedPath = path.replace(/\\/g, "/").trim()
  const match = normalizedPath.match(CHAPTER_FOLDER_PATTERN)
  if (!match) return null

  const chapterNumber = Number.parseInt(match[1] ?? "", 10)
  return Number.isFinite(chapterNumber) && chapterNumber > 0 ? chapterNumber : null
}

export function buildSceneChapterOptions(chapters: WorkspaceChapterNode[], folderPaths: string[]) {
  const chapterNumbers = new Set<number>()

  for (const chapter of chapters) {
    if (chapter.chapter_number > 0) chapterNumbers.add(chapter.chapter_number)
  }

  for (const folderPath of folderPaths) {
    const chapterNumber = extractChapterNumberFromSceneFolder(folderPath)
    if (chapterNumber) chapterNumbers.add(chapterNumber)
  }

  return [...chapterNumbers].sort((left, right) => left - right)
}
