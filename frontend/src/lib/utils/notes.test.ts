import { beforeEach, describe, expect, it, vi } from "vitest"

const { listObsidianNotes, saveObsidianNote } = vi.hoisted(() => ({
  listObsidianNotes: vi.fn(),
  saveObsidianNote: vi.fn(),
}))

vi.mock("@/lib/api/books", () => ({
  booksApi: {
    listObsidianNotes,
    saveObsidianNote,
  },
}))

import {
  buildContextualNoteFolder,
  buildContextualNotePath,
  joinNoteFolderSegments,
  sanitizeNotePathSegment,
  saveContextualVaultNote,
} from "./notes"

describe("notes utilities", () => {
  beforeEach(() => {
    listObsidianNotes.mockReset()
    saveObsidianNote.mockReset()
  })

  it("sanitizes note path segments and joins folder paths safely", () => {
    expect(sanitizeNotePathSegment('  Plot:Threads/Act*1?  ')).toBe("PlotThreads Act1")
    expect(joinNoteFolderSegments("Characters/Main Cast", "  Lead<>  ")).toBe("Characters/Main Cast/Lead")
  })

  it("builds contextual note paths with repo-specific root folders", () => {
    expect(buildContextualNoteFolder("plot_threads", { folderSegments: ["Book One", "Act 1"] })).toBe(
      "Plot Threads/Book One/Act 1"
    )
    expect(buildContextualNotePath('  Nora:Lead?  ', "characters")).toBe("Characters/NoraLead.md")
  })

  it("deduplicates saved note paths and normalizes markdown heading content", async () => {
    listObsidianNotes.mockResolvedValue([
      { path: "Characters/NoraLead.md" },
      { path: "Characters/NoraLead 2.md" },
    ])
    saveObsidianNote.mockResolvedValue({ path: "Characters/NoraLead 3.md" })

    await saveContextualVaultNote({
      bookId: "book-123",
      title: "Nora:Lead",
      content: "First line\r\nSecond line",
      context: "characters",
    })

    expect(saveObsidianNote).toHaveBeenCalledWith("book-123", {
      path: "Characters/NoraLead 3.md",
      content: "# NoraLead\n\nFirst line\nSecond line",
    })
  })
})
