import type { AdvisorMessage, AdvisorResponse } from "@/types/intelligence"
import { buildDailyCapEventDetail, isDailyLimitDetail } from "@/lib/limits/dailyCap"

export type AdvisorEntry = { id: number; question: string; answer: string; status: "streaming" | "complete" | "failed" | "stopped"; error?: string; evidence?: AdvisorResponse }
export type AdvisorNote = { chapterNumber: number | null; title: string | null; body: string }

export function advisorHistory(entries: AdvisorEntry[], question: string): AdvisorMessage[] {
  return [...entries.filter((entry) => entry.status === "complete").slice(-9).flatMap((entry): AdvisorMessage[] => [{ role: "user", content: entry.question.slice(0, 8000) }, { role: "assistant", content: entry.answer.slice(0, 8000) }]), { role: "user", content: question.trim() }]
}

export function advisorQuestionError(question: string) {
  return !question.trim() ? "Write a question before sending." : question.trim().length > 8000 ? "Keep your question to 8,000 characters or fewer. Your draft is kept." : null
}

export function advisorFailure(error: unknown, stopped: boolean, paid: boolean) {
  if (stopped) return "Waiting stopped. This answer is incomplete; your question is ready to edit or retry. Server processing may continue."
  const message = error instanceof Error ? error.message : ""
  if (message.includes("Your free Story Advisor turn refreshes next week.")) return "Your free Story Advisor turn refreshes next week. Review your plan for more capacity."
  if (buildDailyCapEventDetail(error) || isDailyLimitDetail(message.split(" — ").at(-1) ?? "")) return paid ? "You reached today's Story Advisor limit. Continue tomorrow or review your plan." : "You reached this week's free Story Advisor turn. Review your plan for more capacity."
  if (message.includes("429")) return "Too many Story Advisor requests right now. Your question is kept; try again in a moment."
  if (/403|404/.test(message)) return "The advisor cannot access this project right now. Check your access and plan."
  return "The answer did not finish. Your question and any partial answer are kept; you can retry."
}

export function parseAdvisorChoices(raw: string | null): { dismissed: string[]; intentional: string[] } {
  try {
    const value = JSON.parse(raw ?? "null")
    const strings = (items: unknown) => Array.isArray(items) ? [...new Set(items.filter((item): item is string => typeof item === "string" && !!item))].slice(-2000) : []
    return { dismissed: strings(value?.dismissed), intentional: strings(value?.intentional) }
  } catch { return { dismissed: [], intentional: [] } }
}
