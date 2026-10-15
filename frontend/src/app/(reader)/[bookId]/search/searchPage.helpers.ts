import axios from "axios"
import { buildDailyCapEventDetail } from "@/lib/limits/dailyCap"
import type { SearchResult, ThematicSearchResult } from "@/types/reader"

export type SearchMode = "semantic" | "thematic"
export type SearchMatch = { chapter: number; title: string | null; summary: string | null; text?: string }
export type SearchSnapshot = { query: string; chapter?: number; matches: SearchMatch[]; building: boolean }

export function parseSearchChapter(value: string): number | undefined | null {
  if (!value.trim()) return undefined
  const chapter = Number(value)
  return /^\d+$/.test(value.trim()) && Number.isSafeInteger(chapter) && chapter > 0 ? chapter : null
}

export function searchMatches(results: SearchResult[] | ThematicSearchResult[], mode: SearchMode, chapter?: number): SearchMatch[] {
  return results.map((result) => {
    if (mode === "semantic") {
      const passage = result as SearchResult
      return { chapter: passage.chapter_num, title: passage.chapter_title, summary: passage.summary, text: passage.text }
    }
    const theme = result as ThematicSearchResult
    return { chapter: theme.chapter_number, title: theme.chapter_title, summary: theme.summary }
  }).filter((result) => chapter === undefined || (Number.isInteger(result.chapter) && result.chapter > 0 && result.chapter <= chapter))
}

export function searchFailureMessage(error: unknown): string {
  if (buildDailyCapEventDetail(error)) return "You reached today's search limit. Continue when your daily allowance resets, or review your plan."
  if (axios.isAxiosError(error)) {
    if (error.response?.status === 429) return "Search is temporarily rate limited. Wait a moment, then retry."
    if ([403, 404].includes(error.response?.status ?? 0)) return "Search is unavailable for this book or chapter scope. Check your access or choose another scope."
  }
  return "Search failed. Please try again."
}
