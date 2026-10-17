import type { ChapterListItem } from "@/types/reader"

export function graphChapterChoices(chapters: ChapterListItem[], authorMode: boolean) {
  return chapters.filter((chapter) => Number.isInteger(chapter.number) && chapter.number > 0 && chapter.intelligence_available !== false && (authorMode || chapter.read)).sort((a, b) => a.number - b.number)
}
