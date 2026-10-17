import { describe, expect, it } from "vitest"

import {
  getAskLoreViaAnswerLabel,
  getAskLoreViaDescription,
  getAskLoreViaHelperText,
  getAskLoreViaScopeLabel,
  parseRecentQuestions,
  isAskChapter,
  isAskCitationInScope,
  getAskFailureMessage,
} from "./askLoreVia"

describe("ask lorevia scope copy", () => {
  it("distinguishes stopped, daily-cap, rate-limit, access, and interrupted answers", () => {
    expect(getAskFailureMessage(null, true)).toContain("Answer stopped")
    expect(getAskFailureMessage(new Error("403: Advisor stream failed — Your daily limit refreshes tomorrow. Want higher limits now? Upgrade."), false)).toContain("today's question limit")
    expect(getAskFailureMessage(new Error("429: temporary rate limit"), false)).toContain("Too many questions")
    expect(getAskFailureMessage(new Error("404: unavailable"), false)).toContain("Check your access")
    expect(getAskFailureMessage(null, false)).toContain("partial text are kept")
  })
  it("loads only unique, nonempty questions within the saved limit", () => {
    expect(parseRecentQuestions("invalid")).toEqual([])
    expect(parseRecentQuestions(null)).toEqual([])
    expect(parseRecentQuestions(JSON.stringify({ question: "wrong shape" }))).toEqual([])
    expect(parseRecentQuestions(JSON.stringify([null, 4, " ", " One ", "One", ...Array.from({ length: 9 }, (_, index) => `Question ${index}`)]))).toEqual(["One", "Question 0", "Question 1", "Question 2", "Question 3", "Question 4"])
  })
  it("accepts only positive whole chapter scopes and citations within them", () => {
    for (const value of [undefined, 0, -1, 1.5, NaN]) expect(isAskChapter(value)).toBe(false)
    expect(isAskChapter(2)).toBe(true)
    const citation = { chapter_num: 2, chapter_title: null, excerpt: "The gate.", source_type: "passage" as const }
    expect(isAskCitationInScope(citation, 2)).toBe(true)
    expect(isAskCitationInScope(citation, 1)).toBe(false)
    expect(isAskCitationInScope({ ...citation, chapter_num: 0 }, 3)).toBe(false)
  })
  it("builds author-facing scope label and helper copy", () => {
    expect(getAskLoreViaScopeLabel("author", 3)).toBe("All processed chapters through Chapter 3")
    expect(getAskLoreViaDescription("author", 3)).toContain("all processed chapters through Chapter 3")
    expect(getAskLoreViaHelperText("author", 3)).toBe("Enter to ask · Shift+Enter for new line · Answers grounded through Chapter 3")
    expect(getAskLoreViaAnswerLabel("author", 3)).toBe("Answer · Processed through Chapter 3")
  })

  it("builds reader-facing scope label and helper copy", () => {
    expect(getAskLoreViaScopeLabel("reader", 5)).toBe("Up to Chapter 5")
    expect(getAskLoreViaDescription("reader", 5)).toContain("chapters 1-5")
    expect(getAskLoreViaHelperText("reader", 5)).toBe("Enter to ask · Shift+Enter for new line · Answers grounded in Chapters 1-5")
    expect(getAskLoreViaAnswerLabel("reader", 5)).toBe("Answer · Chapters 1-5")
  })
})
