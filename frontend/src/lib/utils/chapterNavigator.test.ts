import { describe, expect, it } from "vitest"
import type { Book } from "@/types/book"
import { canRemoveChapter, filterChapterList } from "./chapterNavigator"

const chapters = [
  { number: 1, title: "Ashfall", processed: true, read: true, tags: ["opening"] },
  { number: 2, title: null, processed: false, read: false },
  { number: 3, title: "River of Glass", processed: true, read: false },
]

describe("chapter navigator", () => {
  it("matches trimmed titles, numbers and tags without changing manuscript order", () => {
    expect(filterChapterList(chapters, " RIVER ", "all")).toEqual([chapters[2]])
    expect(filterChapterList(chapters, "2", "all")).toEqual([chapters[1]])
    expect(filterChapterList(chapters, "opening", "all")).toEqual([chapters[0]])
    expect(filterChapterList(chapters, "", "all")).toEqual(chapters)
  })
  it("combines status and search, including empty and untitled results", () => {
    expect(filterChapterList(chapters, "", "unread")).toEqual(chapters.slice(1))
    expect(filterChapterList(chapters, "", "queued")).toEqual([chapters[1]])
    expect(filterChapterList(chapters, "river", "read")).toEqual([])
    expect(filterChapterList([], "", "all")).toEqual([])
  })
  it("limits removal to authors and collaborators with edit access in the chapter range", () => {
    expect(canRemoveChapter(null, 1)).toBe(false)
    expect(canRemoveChapter({ mode: "reader" } as Book, 1)).toBe(false)
    expect(canRemoveChapter({ mode: "author" } as Book, 1)).toBe(true)
    const book = { mode: "author", collaboration_role: "editor", collaboration_scope: { chapter_start: 2, chapter_end: 4 } } as Book
    expect(canRemoveChapter(book, 2)).toBe(false)
    book.collaboration_permissions = { can_edit_manuscript: true } as Book["collaboration_permissions"]
    expect(canRemoveChapter(book, 1)).toBe(false)
    expect(canRemoveChapter(book, 2)).toBe(true)
    expect(canRemoveChapter(book, 4)).toBe(true)
    expect(canRemoveChapter(book, 5)).toBe(false)
  })
})
