import { beforeEach, describe, expect, it, vi } from "vitest"

import {
  booksApi,
  deleteMock,
  getMock,
  invalidateQueryKeysMock,
  isAxiosErrorMock,
  postMock,
  putMock,
  resetBooksApiMocks,
} from "./books.test-utils"

describe("books api lifecycle contracts", () => {
  beforeEach(() => {
    resetBooksApiMocks()
  })

  it("saves vault notes and invalidates related caches", async () => {
    await booksApi.saveVaultNote("book-1", { path: "Scenes/One.md", content: "# One" })

    expect(putMock).toHaveBeenCalledWith("/books/book-1/notes/vault", {
      path: "Scenes/One.md",
      content: "# One",
    })
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:vault-notes")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:vault-graph")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:vault-relations:")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:workspace-tree")
  })

  it("deletes vault notes with encoded paths and invalidates caches", async () => {
    await booksApi.deleteVaultNote("book-1", "Scenes/Act 1.md")

    expect(deleteMock).toHaveBeenCalledWith("/books/book-1/notes/vault/Scenes%2FAct%201.md")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:vault-notes")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:workspace-tree")
  })

  it("saves book notes and invalidates note caches", async () => {
    await booksApi.saveBookNote("book-1", {
      noteId: "note-1",
      chapterNumber: 3,
      title: "Thread",
      body: "Remember this",
    })

    expect(postMock).toHaveBeenCalledWith("/books/book-1/notes", {
      note_id: "note-1",
      chapter_number: 3,
      title: "Thread",
      body: "Remember this",
    })
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("books:notes")
  })

  it("deletes book notes and invalidates note caches", async () => {
    await booksApi.deleteBookNote("book-1", "note-1")

    expect(deleteMock).toHaveBeenCalledWith("/books/book-1/notes/note-1")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("books:notes")
  })

  it("archives books with the archived query param", async () => {
    await booksApi.archive("book-1", true)

    expect(putMock).toHaveBeenCalledWith("/books/book-1/archive", null, { params: { archived: true } })
  })

  it("hides books through the hide endpoint when supported", async () => {
    await booksApi.hide("book-1", true)

    expect(putMock).toHaveBeenCalledWith("/books/book-1/hide", null, { params: { hidden: true } })
  })

  it("falls back to delete when hide is unsupported for hidden books", async () => {
    putMock.mockRejectedValue({ response: { status: 404 } })
    isAxiosErrorMock.mockReturnValue(true)

    await booksApi.hide("book-1", true)

    expect(deleteMock).toHaveBeenCalledWith("/books/book-1")
  })

  it("rethrows hide failures that are not unsupported endpoints", async () => {
    const error = { response: { status: 401 } }
    putMock.mockRejectedValue(error)
    isAxiosErrorMock.mockReturnValue(true)

    await expect(booksApi.hide("book-1", true)).rejects.toBe(error)
    expect(deleteMock).not.toHaveBeenCalled()
  })

  it("permanently deletes books with explicit confirmation", async () => {
    await booksApi.deletePermanently("book-1", "DELETE BOOK")

    expect(deleteMock).toHaveBeenCalledWith("/books/book-1/permanent", {
      data: { confirmation_text: "DELETE BOOK" },
    })
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:")
  })

  it("updates book forum metadata", async () => {
    await booksApi.updateForumMetadata("book-1", {
      title: "Sky of Ash",
      genre: "Epic Fantasy",
      description: "An ash-storm fantasy about vows, gates, and the cost of holding a city together.",
    })

    expect(putMock).toHaveBeenCalledWith("/books/book-1/forum-metadata", {
      title: "Sky of Ash",
      genre: "Epic Fantasy",
      description: "An ash-storm fantasy about vows, gates, and the cost of holding a city together.",
    })
  })

  it("creates series and invalidates series caches", async () => {
    await booksApi.createSeries({ name: "Saga" })

    expect(postMock).toHaveBeenCalledWith("/books/series", { name: "Saga" })
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("books:series")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("books:series-bible:")
  })

  it("adds books to series and invalidates book and series bible caches", async () => {
    await booksApi.addBookToSeries("series-1", "book-1", { position: 2 })

    expect(postMock).toHaveBeenCalledWith("/books/series/series-1/books/book-1", { position: 2 })
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("books:series-bible:")
  })

  it("removes books from series and invalidates book and series bible caches", async () => {
    await booksApi.removeBookFromSeries("series-1", "book-1")

    expect(deleteMock).toHaveBeenCalledWith("/books/series/series-1/books/book-1")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("books:series-bible:")
  })

  it("uploads books with formdata and reports progress percentages", async () => {
    const file = new File(["hello"], "story.txt", { type: "text/plain" })
    const coverFile = new File(["cover"], "cover.png", { type: "image/png" })
    const progress = vi.fn()
    postMock.mockImplementation((_url, _form, config) => {
      config?.onUploadProgress?.({ loaded: 25, total: 100 })
      return Promise.resolve({ data: { id: "book-1" } })
    })

    await booksApi.upload(file, "Story", "Fantasy", "Author", {
      visibility: "private",
      description: "Epic",
      seriesIds: ["series-1"],
      autoExtractCover: false,
      preserveChapterNumbers: true,
      preserveSourceChapters: true,
      workType: "novel",
      coverFile,
      mode: "author",
      onProgress: progress,
    })

    const form = postMock.mock.calls[0][1] as FormData
    expect(form.get("title")).toBe("Story")
    expect(form.get("genre")).toBe("Fantasy")
    expect(form.get("author")).toBe("Author")
    expect(form.get("visibility")).toBe("private")
    expect(form.get("description")).toBe("Epic")
    expect(form.get("series_ids")).toBe("series-1")
    expect(form.get("auto_extract_cover")).toBe("false")
    expect(form.get("preserve_chapter_numbers")).toBe("true")
    expect(form.get("preserve_source_chapters")).toBe("true")
    expect(form.get("work_type")).toBe("novel")
    expect(form.get("mode")).toBe("author")
    expect(progress).toHaveBeenCalledWith(25)
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("books:list:")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("books:page:active")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("books:page:all")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("books:selector:active")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("books:selector:all")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("books:stats")
  })

  it("imports manuscripts with formdata and invalidates book and reader caches", async () => {
    const file = new File(["chapter"], "chapter.txt", { type: "text/plain" })

    await booksApi.importManuscript("book-1", {
      text: "Hello",
      html: "<p>Hello</p>",
      title: "Draft",
      chapterNumber: 4,
      expectedContentVersion: 7,
      replaceExisting: true,
      chunkLongDocuments: true,
      splitIntoChapters: false,
      workType: "novel",
      files: [file],
    })

    const form = postMock.mock.calls[0][1] as FormData
    expect(form.get("text")).toBe("Hello")
    expect(form.get("html")).toBe("<p>Hello</p>")
    expect(form.get("title")).toBe("Draft")
    expect(form.get("chapter_number")).toBe("4")
    expect(form.get("expected_content_version")).toBe("7")
    expect(form.get("replace_existing")).toBe("true")
    expect(form.get("chunk_long_documents")).toBe("true")
    expect(form.get("split_into_chapters")).toBe("false")
    expect(form.get("work_type")).toBe("novel")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("reader:book-1:")
  })

  it("polls durable manuscript import jobs until the result is ready", async () => {
    vi.useFakeTimers()
    const result = {
      book_id: "book-1",
      imported_chapters: [2, 3],
      chapter_content_versions: { 2: 1, 3: 1 },
      total_chapters: 3,
      mode: "author" as const,
      source_kind: "batch_upload",
      chapter_reports: [],
    }
    postMock.mockResolvedValueOnce({
      data: {
        id: "job-1",
        book_id: "book-1",
        status: "queued",
        progress_completed: 0,
        progress_total: 1,
        cancel_requested: false,
        result: null,
        error: null,
        created_at: "2026-09-10T08:00:00Z",
        updated_at: "2026-09-10T08:00:00Z",
      },
    })
    getMock.mockResolvedValueOnce({
      data: {
        id: "job-1",
        book_id: "book-1",
        status: "completed",
        progress_completed: 1,
        progress_total: 1,
        cancel_requested: false,
        result,
        error: null,
        created_at: "2026-09-10T08:00:00Z",
        updated_at: "2026-09-10T08:00:01Z",
      },
    })

    try {
      const pending = booksApi.importManuscript("book-1", {
        files: [new File(["chapter"], "chapter.txt", { type: "text/plain" })],
      })
      await Promise.resolve()
      await vi.advanceTimersByTimeAsync(1_000)

      await expect(pending).resolves.toEqual(result)
      expect(getMock).toHaveBeenCalledWith("/books/book-1/manuscript/import/job-1")
    } finally {
      vi.useRealTimers()
    }
  })
})
