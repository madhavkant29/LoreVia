import type { AdvisorMessage, AdvisorPassage } from "@/types/intelligence"
import { buildDailyCapEventDetail, isDailyLimitDetail } from "@/lib/limits/dailyCap"
import { renderMarkdownHtml } from "@/lib/utils/richText"

export interface SeriesAnswer {
  id: number
  question: string
  answer: string
  status: "streaming" | "complete" | "failed" | "stopped"
  error?: string
  passages: AdvisorPassage[]
}

export function seriesQuestionError(question: string) {
  if (!question.trim()) return "Write a question before asking."
  if (question.trim().length > 8000) return "Keep your question to 8,000 characters or fewer. Your draft is kept."
  return null
}

export function seriesQuestionHistory(entries: SeriesAnswer[], question: string): AdvisorMessage[] {
  return [...entries.filter((entry) => entry.status === "complete").slice(-7).flatMap((entry): AdvisorMessage[] => [
    { role: "user", content: entry.question.slice(0, 8000) },
    { role: "assistant", content: entry.answer.slice(0, 8000) },
  ]), { role: "user", content: question.trim() }]
}

export function seriesAnswerError(error: unknown, stopped: boolean) {
  if (stopped) return "Waiting stopped. Any text below is incomplete. Your question is ready to edit or retry. The server may continue processing."
  const message = error instanceof Error ? error.message : ""
  if (buildDailyCapEventDetail(error) || isDailyLimitDetail(message.split(" — ").at(-1) ?? "")) return "You reached today's question limit. Continue tomorrow or review your plan."
  if (message.includes("429")) return "Too many questions right now. Your question is kept; try again in a moment."
  if (/403|404/.test(message)) return "This account cannot ask about this series right now. Check your access and plan."
  return "The answer did not finish. Your question and any partial text are kept; you can retry."
}

export function renderSeriesAnswer(value: string) {
  const blocks: string[] = []
  let lines: string[] = []
  let kind: "paragraph" | "ul" | "ol" = "paragraph"
  const inline = (text: string) => renderMarkdownHtml(text).replace(/^<p>|<\/p>$/g, "")
  const flush = () => {
    if (!lines.length) return
    blocks.push(kind === "paragraph" ? renderMarkdownHtml(lines.join("\n")) : `<${kind}>${lines.map((line) => `<li>${inline(line)}</li>`).join("")}</${kind}>`)
    lines = []
  }
  for (const line of value.split(/\r?\n/)) {
    const heading = line.match(/^\s{0,3}#{1,6}\s+(.+)$/)
    const unordered = line.match(/^\s*[-*+]\s+(.+)$/)
    const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/)
    if (!line.trim()) { flush(); continue }
    if (heading) { flush(); blocks.push(`<h4>${inline(heading[1])}</h4>`); continue }
    const nextKind = unordered ? "ul" : ordered ? "ol" : "paragraph"
    if (nextKind !== kind) flush()
    kind = nextKind
    lines.push(unordered?.[1] ?? ordered?.[1] ?? line)
  }
  flush()
  return blocks.join("")
}
