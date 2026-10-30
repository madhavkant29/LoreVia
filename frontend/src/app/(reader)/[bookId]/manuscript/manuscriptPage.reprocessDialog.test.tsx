// @vitest-environment jsdom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"

import { booksApi } from "@/lib/api/books"

import { ManuscriptReprocessDialog } from "./manuscriptPage.reprocessDialog"

const readyPreflight = {
  book_id: "book-1",
  ready: true,
  chapters_total: 3,
  processed_words_to_reserve: 31_500,
  protected_characters: 2,
  replaceable_characters: 5,
  missing_source_chapters: [],
  blockers: [],
  preview_fingerprint: "a".repeat(64),
  limitation: "The new cast cannot be predicted until extraction runs.",
}

afterEach(() => vi.restoreAllMocks())

describe("ManuscriptReprocessDialog", () => {
  it("shows the stored-source preflight and requires its fingerprint before reserving words", async () => {
    vi.spyOn(booksApi, "previewManuscriptReprocess").mockResolvedValue(readyPreflight)
    const onConfirm = vi.fn()
    const container = document.createElement("div")
    document.body.appendChild(container)
    const root = createRoot(container)

    await act(async () => {
      root.render(
        <ManuscriptReprocessDialog
          bookId="book-1"
          isDark={false}
          reprocessing={false}
          onCancel={() => undefined}
          onConfirm={onConfirm}
        />
      )
    })

    const dialog = document.body.querySelector('[role="dialog"]')
    expect(dialog?.textContent).toContain("full word count is reserved first")
    expect(dialog?.textContent).toContain("only chapters that finish successfully are charged")
    expect(dialog?.textContent).toContain("2 protected characters will be kept")
    expect(dialog?.textContent).toContain("5 generated character records may be replaced")
    expect(dialog?.textContent).toContain("new cast cannot be predicted")
    const confirm = Array.from(dialog?.querySelectorAll("button") ?? []).find((button) => button.textContent?.includes("Reserve words"))
    expect(confirm?.disabled).toBe(false)
    await act(async () => confirm?.click())
    expect(onConfirm).toHaveBeenCalledWith(readyPreflight.preview_fingerprint)

    await act(async () => root.unmount())
    container.remove()
  })

  it("disables reprocess when stored source is missing", async () => {
    vi.spyOn(booksApi, "previewManuscriptReprocess").mockResolvedValue({
      ...readyPreflight,
      ready: false,
      missing_source_chapters: [2],
      blockers: ["Stored source text is unavailable for one or more chapters."],
      preview_fingerprint: null,
    })
    const onConfirm = vi.fn()
    const container = document.createElement("div")
    document.body.appendChild(container)
    const root = createRoot(container)

    await act(async () => {
      root.render(<ManuscriptReprocessDialog bookId="book-1" isDark={false} reprocessing={false} onCancel={() => undefined} onConfirm={onConfirm} />)
    })

    const dialog = document.body.querySelector('[role="dialog"]')
    expect(dialog?.textContent).toContain("Stored source missing for chapters 2")
    const confirm = Array.from(dialog?.querySelectorAll("button") ?? []).find((button) => button.textContent?.includes("Reserve words"))
    expect(confirm?.disabled).toBe(true)
    await act(async () => confirm?.click())
    expect(onConfirm).not.toHaveBeenCalled()

    await act(async () => root.unmount())
    container.remove()
  })
})
