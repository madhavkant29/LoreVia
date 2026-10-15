import { describe, expect, it } from "vitest"
import { advisorFailure, advisorHistory, advisorQuestionError, parseAdvisorChoices, type AdvisorEntry } from "./advisorPage.helpers"

describe("advisor state helpers", () => {
  it("validates empty and oversized questions without losing text", () => {
    expect(advisorQuestionError("  ")).toMatch(/Write/)
    expect(advisorQuestionError("x".repeat(8000))).toBeNull()
    expect(advisorQuestionError("x".repeat(8001))).toMatch(/8,000/)
  })
  it("bounds context to complete exchanges within the API limits", () => {
    const entries: AdvisorEntry[] = Array.from({ length: 15 }, (_, id) => ({ id, question: `Question ${id}`, answer: "x".repeat(9000), status: "complete" }))
    entries.push({ id: 16, question: "Interrupted", answer: "partial", status: "stopped" })
    const messages = advisorHistory(entries, " next ")
    expect(messages).toHaveLength(19)
    expect(messages[0].content).toBe("Question 6")
    expect(messages[1].content).toHaveLength(8000)
    expect(messages.at(-1)).toEqual({ role: "user", content: "next" })
    expect(advisorHistory([], "First")).toEqual([{ role: "user", content: "First" }])
  })
  it("recovers malformed storage and deduplicates only valid choice identifiers", () => {
    expect(parseAdvisorChoices("oops")).toEqual({ dismissed: [], intentional: [] })
    expect(parseAdvisorChoices(null)).toEqual({ dismissed: [], intentional: [] })
    expect(parseAdvisorChoices('{"dismissed":["one","one",null,2,""],"intentional":false}')).toEqual({ dismissed: ["one"], intentional: [] })
  })
  it("explains interruption, access, weekly and daily limits, and transient errors", () => {
    expect(advisorFailure(null, true, true)).toMatch(/Server processing/)
    expect(advisorFailure(new Error("403"), false, true)).toMatch(/access/)
    expect(advisorFailure(new Error("429"), false, true)).toMatch(/Too many/)
    const error = new Error("You've reached your daily limit of 60 Story Advisor turns. It refreshes tomorrow.")
    expect(advisorFailure(error, false, true)).toMatch(/today/)
    expect(advisorFailure(error, false, false)).toMatch(/week/)
    expect(advisorFailure(new Error("HTTP 429 — Your free Story Advisor turn refreshes next week. Upgrade for more capacity."), false, false)).toMatch(/next week/)
    expect(advisorFailure(null, false, true)).toMatch(/partial/)
  })
})
