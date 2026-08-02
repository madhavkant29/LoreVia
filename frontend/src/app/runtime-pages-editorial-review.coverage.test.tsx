// @vitest-environment jsdom

import { describe, expect, it } from "vitest"

import {
  booksApiMock,
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
  it("drives import, review, and note-save handlers", async () => {
    await renderPage(<EditorialReviewPage />)

    expect(text()).toContain("The Lantern Gate editorial review")
    setFieldValue(
      field<HTMLTextAreaElement>("textarea"),
      "Mara unlocks the gate and finds the lantern inside.",
    )
    setFieldValue(field<HTMLInputElement>("input[type='number']"), "3")
    await click("Add to current upload")
    expect(booksApiMock.importManuscript).toHaveBeenCalledWith(
      "book-1",
      expect.objectContaining({ chapterNumber: 3 }),
    )

    await click("Run Editorial Review")
    expect(intelligenceApiMock.editorialReviewStream).toHaveBeenCalledWith(
      "book-1",
      expect.any(String),
      3,
      expect.any(Object),
    )
    expect(text()).toContain("Strong scene")
    await click("Save review note")
    expect(saveContextualVaultNoteMock).toHaveBeenCalledWith(
      expect.objectContaining({ bookId: "book-1", title: "Review note" }),
    )
  })
})
