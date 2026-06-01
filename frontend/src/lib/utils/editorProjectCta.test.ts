import { describe, expect, it } from "vitest"
import { deriveEditorProjectCta } from "./editorProjectCta"
import type { Book } from "@/types/book"

function makeBook(overrides: Partial<Book> = {}): Book {
  return {
    id: "book-1",
    title: "Test Book",
    author: null,
    genre: null,
    format: "manual",
    work_type: "novel",
    status: "ready",
    mode: "author",
    workspace_shell: "author",
    access_class: "owner",
    can_switch_workspace_mode: true,
    total_chapters: 0,
    total_words: 0,
    created_at: new Date().toISOString(),
    is_editor_project: true,
    ...overrides,
  } as Book
}

describe("deriveEditorProjectCta", () => {
  it("returns empty label for non-editor projects", () => {
    const book = makeBook({ is_editor_project: false })
    const cta = deriveEditorProjectCta(book, false)
    expect(cta.label).toBe("")
    expect(cta.disabled).toBe(true)
    expect(cta.disabledReason).toBeNull()
  })

  it("returns empty label for null book", () => {
    const cta = deriveEditorProjectCta(null, false)
    expect(cta.label).toBe("")
    expect(cta.disabled).toBe(true)
  })

  it("blocks when no chapters or words", () => {
    const book = makeBook({ total_chapters: 0, total_words: 0 })
    const cta = deriveEditorProjectCta(book, false)
    expect(cta.disabled).toBe(true)
    expect(cta.disabledReason).toBe("Save at least one chapter before reprocessing")
  })

  it("blocks when unsaved drafts exist", () => {
    const book = makeBook({ total_chapters: 3, total_words: 500 })
    const cta = deriveEditorProjectCta(book, true)
    expect(cta.disabled).toBe(true)
    expect(cta.disabledReason).toBe("Save your changes before reprocessing")
  })

  it("allows reprocess when editor project is ready with content", () => {
    const book = makeBook({ total_chapters: 3, total_words: 500 })
    const cta = deriveEditorProjectCta(book, false)
    expect(cta.disabled).toBe(false)
    expect(cta.disabledReason).toBeNull()
    expect(cta.label).toBe("Reprocess manuscript")
  })

  it("locks save during active processing", () => {
    const book = makeBook({
      status: "processing",
      total_chapters: 3,
      total_words: 500,
      processing: { status: "processing", stage: "extraction" },
    })
    const cta = deriveEditorProjectCta(book, false)
    expect(cta.disabled).toBe(true)
    expect(cta.disabledReason).toBe("Reprocessing is already in progress")
    expect(cta.saveLocked).toBe(true)
    expect(cta.isProcessing).toBe(true)
  })

  it("shows progress in label during processing", () => {
    const book = makeBook({
      status: "processing",
      total_chapters: 5,
      total_words: 1000,
      processing: {
        status: "processing",
        stage: "extraction",
        progress_pct: 42,
        eta_seconds: 120,
      },
    })
    const cta = deriveEditorProjectCta(book, false)
    expect(cta.label).toContain("42%")
    expect(cta.label).toContain("2min left")
  })
})
