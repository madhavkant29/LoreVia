import type { GroundedCitation } from "@/types/intelligence"
import { buildDailyCapEventDetail, isDailyLimitDetail } from "@/lib/limits/dailyCap"

export interface AskEntry {
  question: string
  answer: string
  citations: GroundedCitation[]
  chapter?: number
  status?: "streaming" | "complete" | "failed" | "stopped"
  error?: string
}

export function getAskFailureMessage(error: unknown, stopped: boolean) {
  if (stopped) return "Answer stopped. Any text below is incomplete; your question is ready to edit or retry."
  const message = error instanceof Error ? error.message : ""
  if (buildDailyCapEventDetail(error) || isDailyLimitDetail(message.split(" — ").at(-1) ?? "")) return "You reached today's question limit. Continue tomorrow or review your plan."
  if (message.includes("429")) return "Too many questions right now. Your question is kept; try again in a moment."
  if (/403|404/.test(message)) return "This account cannot ask about this manuscript right now. Check your access and plan."
  return "The answer did not finish. Your question and any partial text are kept; you can retry."
}

export function parseRecentQuestions(raw: string | null) {
  try {
    const values: unknown = raw ? JSON.parse(raw) : []
    return Array.isArray(values) ? [...new Set(values.filter((value): value is string => typeof value === "string" && !!value.trim()).map((value) => value.trim()))].slice(0, 6) : []
  } catch { return [] }
}

export function isAskChapter(value: number | undefined) {
  return typeof value === "number" && Number.isInteger(value) && value > 0
}

export function isAskCitationInScope(citation: GroundedCitation, chapter: number) {
  return isAskChapter(citation.chapter_num) && citation.chapter_num <= chapter
}

export function getAskLoreViaScopeLabel(mode: "author" | "reader" | undefined, currentChapter: number) {
  return mode === "author"
    ? `All processed chapters through Chapter ${currentChapter}`
    : `Up to Chapter ${currentChapter}`
}

export function getAskLoreViaDescription(mode: "author" | "reader" | undefined, currentChapter: number) {
  return mode === "author"
    ? `Ask plain-English questions about your story and get a short grounded answer with chapter citations. LoreVia uses all processed chapters through Chapter ${currentChapter}.`
    : `Ask about the story using material from chapters 1-${currentChapter}. Answers may also draw on earlier books in the same series. Check the cited sources alongside the answer.`
}

export function getAskLoreViaHelperText(mode: "author" | "reader" | undefined, currentChapter: number) {
  return mode === "author"
    ? `Enter to ask · Shift+Enter for new line · Answers grounded through Chapter ${currentChapter}`
    : `Enter to ask · Shift+Enter for new line · Answers grounded in Chapters 1-${currentChapter}`
}

export function getAskLoreViaAnswerLabel(mode: "author" | "reader" | undefined, currentChapter: number) {
  return mode === "author"
    ? `Answer · Processed through Chapter ${currentChapter}`
    : `Answer · Chapters 1-${currentChapter}`
}
