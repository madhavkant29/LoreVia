// @vitest-environment jsdom

import { describe, expect, it } from "vitest"

import {
  click,
  field,
  intelligenceApiMock,
  renderPage,
  saveContextualVaultNoteMock,
  setFieldValue,
  text,
} from "./runtime-pages-expanded.test-utils"

import EditorialReviewPage from "@/app/(reader)/[bookId]/editorial-review/page"

describe("editorial review runtime page coverage", () => {
  it("drives passage review, session history, and note-save handlers", async () => {
    await renderPage(<EditorialReviewPage />)

    expect(text()).toContain("Editorial review")
    setFieldValue(
      field<HTMLTextAreaElement>("textarea"),
      "Mara unlocks the gate and finds the lantern inside.",
    )
    setFieldValue(field<HTMLInputElement>("input[type='number']"), "3")
    await click("Run review")
    expect(intelligenceApiMock.editorialReviewStream).toHaveBeenCalledWith(
      "book-1",
      expect.any(String),
      3,
      expect.any(Object),
    )
    expect(text()).toContain("Strong scene")
    expect(text()).toContain("Runs this session")
    expect(text()).toContain("Chapter 3")
    await click("Save review note")
    expect(saveContextualVaultNoteMock).toHaveBeenCalledWith(
      expect.objectContaining({ bookId: "book-1", title: "Review note" }),
    )
  })

  it("blocks empty, oversized, and invalid chapter input without truncating the passage", async () => {
    await renderPage(<EditorialReviewPage />)
    const passage = field<HTMLTextAreaElement>("textarea")
    const chapter = field<HTMLInputElement>("input[type='number']")
    await click("Run review")
    expect(intelligenceApiMock.editorialReviewStream).not.toHaveBeenCalled()
    setFieldValue(passage, "x".repeat(12001))
    expect(passage.value).toHaveLength(12001)
    await click("Run review")
    expect(intelligenceApiMock.editorialReviewStream).not.toHaveBeenCalled()
    setFieldValue(passage, "A complete passage.")
    for (const invalid of ["0", "-1", "1.5"]) {
      setFieldValue(chapter, invalid)
      await click("Run review")
      expect(intelligenceApiMock.editorialReviewStream).not.toHaveBeenCalled()
    }
    setFieldValue(chapter, "")
    await click("Run review")
    expect(intelligenceApiMock.editorialReviewStream).toHaveBeenCalledWith("book-1", "A complete passage.", undefined, expect.any(Object))
  })

  it("selects previous results without overwriting new passage edits", async () => {
    await renderPage(<EditorialReviewPage />)
    const passage = field<HTMLTextAreaElement>("textarea")
    setFieldValue(passage, "First reviewed passage.")
    await click("Run review")
    setFieldValue(passage, "Second reviewed passage.")
    await click("Run review")
    setFieldValue(passage, "New unsent draft.")
    await click("Passage 1")
    expect(passage.value).toBe("New unsent draft.")
    expect(text()).toContain("First reviewed passage.")
    expect(text()).toContain("this review still refers to its original passage")
  })

  it("retains the passage after a failed review and allows retry", async () => {
    await renderPage(<EditorialReviewPage />)
    intelligenceApiMock.editorialReviewStream.mockRejectedValueOnce(new Error("Offline"))
    const passage = field<HTMLTextAreaElement>("textarea")
    setFieldValue(passage, "Keep this passage.")
    await click("Run review")
    expect(text()).toContain("Review failed")
    expect(passage.value).toBe("Keep this passage.")
    await click("Run review")
    expect(text()).toContain("Passage 1")
    expect(text()).not.toContain("Review failed")
  })

  it.each([["429: Advisor stream failed", "Review limit reached"], ["403: Advisor stream failed", "Review access is unavailable"]])("explains review restrictions for %s", async (error, message) => {
    await renderPage(<EditorialReviewPage />)
    intelligenceApiMock.editorialReviewStream.mockRejectedValueOnce(new Error(error))
    setFieldValue(field<HTMLTextAreaElement>("textarea"), "Preserve this passage.")
    await click("Run review")
    expect(text()).toContain(message)
    expect(field<HTMLTextAreaElement>("textarea").value).toBe("Preserve this passage.")
  })
})
