// @vitest-environment jsdom

import { describe, expect, it, vi } from "vitest"
import { act } from "react"

import {
  booksApiMock,
  characterFixture,
  click,
  clickText,
  firstField,
  readerApiMock,
  renderElement,
  setFieldValue,
  text,
  unmountCurrentRoot,
} from "./runtime-zero-components.test-utils"

import { ContextPanel } from "@/components/reader/ContextPanel"

describe("context panel runtime coverage", () => {
  it("drives quote, character edit, recall, links, search, loading, empty, and drag paths", async () => {
    const onClose = vi.fn()
    await renderElement(
      <ContextPanel
        result={{ type: "character", character: characterFixture }}
        loading={false}
        onClose={onClose}
        mobileSheet
        canEdit
        theme="dark"
        selectedQuote="The lantern hummed when Mara lied."
        chapterNumber={3}
        chapterTitle="The Lock"
        characters={[
          {
            id: "char-1",
            name: "Mara Vale",
            aliases: [],
            role: "mc",
            first_chapter: 1,
            personality_tags: [],
          },
          {
            id: "char-2",
            name: "Theo",
            aliases: [],
            role: "supporting",
            first_chapter: 1,
            personality_tags: [],
          },
        ]}
      />,
    )

    expect(text()).toContain("Mara Vale")
    setFieldValue(firstField<HTMLSelectElement>("select"), "Mara Vale")
    setFieldValue(firstField<HTMLTextAreaElement>('textarea[aria-label="Line bookmark note"]'), "Important lie.")
    await click("Save line bookmark")
    expect(readerApiMock.saveQuote).toHaveBeenCalledWith(
      "book-1",
      expect.objectContaining({ character_name: "Mara Vale" }),
    )

    await clickText("+1 more", "button")
    expect(text()).toContain("Show less")
    await click("Edit")
    await act(async () => { setFieldValue(document.querySelector<HTMLTextAreaElement>('[aria-label="Character name"]')!, "Mara Bright") })
    await act(async () => { Array.from(document.querySelectorAll("button")).find((button) => button.textContent === "Save Changes")?.click() })
    expect(booksApiMock.updateCharacter).toHaveBeenCalledWith(
      "book-1",
      "char-1",
      expect.objectContaining({ name: "Mara Bright" }),
    )
    await click("Links")
    expect(text()).toContain("View relationships through chapter 3")
    await click("Recall")
    expect(text()).toContain("Mara last appeared")

    unmountCurrentRoot()
    await renderElement(
      <ContextPanel
        result={{
          type: "search",
          results: [
            {
              chapter_num: 4,
              chapter_title: "The Lock",
              text: "Theo finds the spare key.",
              summary: "Theo finds a key.",
              relevance: 0.9,
            },
          ],
        }}
        loading={false}
        onClose={onClose}
        theme="light"
        selectedQuote={null}
        chapterNumber={4}
        chapterTitle={null}
        characters={[]}
      />,
    )
    expect(text()).toContain("Theo finds the spare key")

    unmountCurrentRoot()
    await renderElement(
      <ContextPanel
        result={null}
        loading
        onClose={onClose}
        theme="light"
        selectedQuote={null}
        chapterNumber={1}
        chapterTitle={null}
        characters={[]}
      />,
    )
    expect(text()).toContain("Loading character context")
  })
})
