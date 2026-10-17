// @vitest-environment jsdom
import { describe, expect, it } from "vitest"
import { renderSeriesAnswer, seriesAnswerError, seriesQuestionError, seriesQuestionHistory, type SeriesAnswer } from "./seriesAsk.helpers"

describe("series questions", () => {
  it("renders safe answer headings, lists and paragraphs without executing supplied markup", () => {
    const result = renderSeriesAnswer("## Changes\n- **Nora** returns\n- The gate opens\n\n1. Check the oath\n2. Name the keeper\n\n<script>alert(1)</script>\nFinal line")
    expect(result).toContain("<h4>Changes</h4>")
    expect(result).toContain("<ul><li><strong>Nora</strong> returns</li><li>The gate opens</li></ul>")
    expect(result).toContain("<ol><li>Check the oath</li><li>Name the keeper</li></ol>")
    expect(result).not.toContain("<script>")
    expect(result).toContain("&lt;script&gt;")
    expect(result).toContain("<br>Final line")
    expect(renderSeriesAnswer("  ")).toBe("")
  })
  it("validates blank and boundary drafts without truncating them", () => {
    expect(seriesQuestionError("  ")).toMatch(/Write/)
    expect(seriesQuestionError("x".repeat(8000))).toBeNull()
    expect(seriesQuestionError("x".repeat(8001))).toMatch(/8,000/)
  })
  it("sends seven complete exchanges and the current question, excluding failed partial answers", () => {
    const entries: SeriesAnswer[] = Array.from({ length: 10 }, (_, id) => ({ id, question: `Q${id}`, answer: "x".repeat(9000), passages: [], status: "complete" }))
    entries.push({ id: 11, question: "failed", answer: "partial", passages: [], status: "failed" })
    const history = seriesQuestionHistory(entries, " next ")
    expect(history).toHaveLength(15)
    expect(history[0].content).toBe("Q3")
    expect(history[1].content).toHaveLength(8000)
    expect(history.at(-1)).toEqual({ role: "user", content: "next" })
    expect(seriesQuestionHistory([], "first")).toEqual([{ role: "user", content: "first" }])
  })
  it("distinguishes interruption, access, rate, and unknown failures", () => {
    expect(seriesAnswerError(null, true)).toMatch(/server may continue/)
    expect(seriesAnswerError(new Error("429"), false)).toMatch(/Too many/)
    expect(seriesAnswerError(new Error("403"), false)).toMatch(/this series/)
    expect(seriesAnswerError(new Error("429 — You've reached your daily limit of 60 Story Advisor turns. It refreshes tomorrow."), false)).toMatch(/today's question limit/)
    expect(seriesAnswerError(null, false)).toMatch(/partial text/)
  })
})
