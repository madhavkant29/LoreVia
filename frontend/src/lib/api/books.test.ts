import { beforeEach, describe, expect, it, vi } from "vitest"

const {
  getMock,
  postMock,
  putMock,
  deleteMock,
  cachedGetMock,
  invalidateCachedGetsMock,
  isAxiosErrorMock,
} = vi.hoisted(() => ({
  getMock: vi.fn(),
  postMock: vi.fn(),
  putMock: vi.fn(),
  deleteMock: vi.fn(),
  cachedGetMock: vi.fn(),
  invalidateCachedGetsMock: vi.fn(),
  isAxiosErrorMock: vi.fn(),
}))

vi.mock("./client", () => ({
  apiClient: {
    get: getMock,
    post: postMock,
    put: putMock,
    delete: deleteMock,
  },
}))

vi.mock("./requestCache", () => ({
  cachedGet: cachedGetMock,
  invalidateCachedGets: invalidateCachedGetsMock,
}))

vi.mock("axios", () => ({
  default: {
    isAxiosError: isAxiosErrorMock,
  },
  isAxiosError: isAxiosErrorMock,
}))

import { booksApi } from "./books"

describe("books api", () => {
  beforeEach(() => {
    getMock.mockReset()
    postMock.mockReset()
    putMock.mockReset()
    deleteMock.mockReset()
    cachedGetMock.mockReset()
    invalidateCachedGetsMock.mockReset()
    isAxiosErrorMock.mockReset()

    getMock.mockResolvedValue({ data: { ok: true } })
    postMock.mockResolvedValue({ data: { ok: true } })
    putMock.mockResolvedValue({ data: { ok: true } })
    deleteMock.mockResolvedValue({ data: { ok: true } })
    cachedGetMock.mockImplementation(async (_key, _ttl, fetcher) => fetcher())
  })

  it("lists active books through the cache layer", async () => {
    await booksApi.list()

    expect(cachedGetMock.mock.calls[0][0]).toBe("books:list:active")
    expect(cachedGetMock.mock.calls[0][1]).toBe(20000)
    expect(getMock).toHaveBeenCalledWith("/books", { params: { include_hidden: false } })
  })

  it("lists all books when include hidden is true", async () => {
    await booksApi.list(true)

    expect(cachedGetMock.mock.calls[0][0]).toBe("books:list:all")
    expect(getMock).toHaveBeenCalledWith("/books", { params: { include_hidden: true } })
  })

  it("loads stats through the cache layer", async () => {
    await booksApi.getStats()

    expect(cachedGetMock.mock.calls[0][0]).toBe("books:stats")
    expect(getMock).toHaveBeenCalledWith("/books/stats")
  })

  it("loads a book detail through the cache layer", async () => {
    await booksApi.get("book-1")

    expect(cachedGetMock.mock.calls[0][0]).toBe("book:book-1:detail")
    expect(getMock).toHaveBeenCalledWith("/books/book-1")
  })

  it("creates story-scoped collaborators with backend field names", async () => {
    await booksApi.createCollaborator("book-1", {
      email: "editor@example.com",
      displayName: "Editor",
      role: "developmental_editor",
      scope: {
        chapter_start: 1,
        chapter_end: 10,
        character_bible: true,
        continuity_report: true,
        reader_confusion_report: false,
      },
    })

    expect(postMock).toHaveBeenCalledWith("/books/book-1/collaborators", {
      email: "editor@example.com",
      display_name: "Editor",
      role: "developmental_editor",
      scope: {
        chapter_start: 1,
        chapter_end: 10,
        character_bible: true,
        continuity_report: true,
        reader_confusion_report: false,
      },
    })
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("book:book-1:")
  })

  it("normalizes readable route segments before loading book detail", async () => {
    await booksApi.get("sky-harbor--123e4567-e89b-12d3-a456-426614174000")

    expect(cachedGetMock.mock.calls[0][0]).toBe("book:123e4567-e89b-12d3-a456-426614174000:detail")
    expect(getMock).toHaveBeenCalledWith("/books/123e4567-e89b-12d3-a456-426614174000")
  })

  it("loads pre-writing checks with an explicit chapter", async () => {
    await booksApi.getPreWritingCheck("book-1", 4)

    expect(cachedGetMock.mock.calls[0][0]).toBe("book:book-1:pre-writing:4")
    expect(getMock).toHaveBeenCalledWith("/books/book-1/pre-writing-check", { params: { upcoming_chapter: 4 } })
  })

  it("loads pre-writing checks without params when chapter is omitted", async () => {
    await booksApi.getPreWritingCheck("book-1")

    expect(cachedGetMock.mock.calls[0][0]).toBe("book:book-1:pre-writing:auto")
    expect(getMock).toHaveBeenCalledWith("/books/book-1/pre-writing-check", { params: undefined })
  })

  it("creates chapter snapshots and invalidates version caches", async () => {
    await booksApi.createChapterSnapshot("book-1", 7, "checkpoint")

    expect(postMock).toHaveBeenCalledWith("/books/book-1/chapters/7/snapshot", null, {
      params: { note: "checkpoint" },
    })
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("book:book-1:chapter-versions:7:")
  })

  it("restores chapter versions and invalidates book caches", async () => {
    await booksApi.restoreChapterVersion("book-1", "version-9")

    expect(postMock).toHaveBeenCalledWith("/books/book-1/chapter-versions/version-9/restore")
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("book:book-1:")
  })

  it("saves an existing scene with put and invalidates workspace caches", async () => {
    await booksApi.saveScene("book-1", { id: "scene-1", title: "Scene", body: "Body" })

    expect(putMock).toHaveBeenCalledWith("/books/book-1/scenes/scene-1", {
      id: "scene-1",
      title: "Scene",
      body: "Body",
    })
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("book:book-1:workspace-tree")
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("book:book-1:scenes:")
  })

  it("creates a new scene with post when no scene id is present", async () => {
    await booksApi.saveScene("book-1", { title: "New Scene", body: "Body" })

    expect(postMock).toHaveBeenCalledWith("/books/book-1/scenes", {
      title: "New Scene",
      body: "Body",
    })
  })

  it("deletes scenes and invalidates workspace caches", async () => {
    await booksApi.deleteScene("book-1", "scene-1")

    expect(deleteMock).toHaveBeenCalledWith("/books/book-1/scenes/scene-1")
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("book:book-1:workspace-tree")
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("book:book-1:scenes:")
  })

  it("updates writer workspace and invalidates its cache entry", async () => {
    await booksApi.updateWriterWorkspace("book-1", { publishing: { active_preset: "kdp_paperback" } } as never)

    expect(putMock).toHaveBeenCalledWith("/books/book-1/writer-workspace", {
      publishing: { active_preset: "kdp_paperback" },
    })
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("book:book-1:writer-workspace")
  })

  it("maps character update payload fields to the backend shape", async () => {
    await booksApi.updateCharacter("book-1", "char-1", {
      name: "Nora",
      aliases: ["N"],
      role: "mc",
      description: "Lead",
      arcSummary: "Arc",
      personalityTags: ["focused"],
      motivations: ["finish"],
      fears: ["failure"],
    })

    expect(putMock).toHaveBeenCalledWith("/books/book-1/characters/char-1", {
      name: "Nora",
      aliases: ["N"],
      role: "mc",
      description: "Lead",
      arc_summary: "Arc",
      personality_tags: ["focused"],
      motivations: ["finish"],
      fears: ["failure"],
    })
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("book:book-1:")
  })

  it("merges characters with backend field names", async () => {
    await booksApi.mergeCharacters("book-1", { primaryId: "a", secondaryId: "b" })

    expect(postMock).toHaveBeenCalledWith("/books/book-1/characters/merge", {
      primary_id: "a",
      secondary_id: "b",
    })
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("book:book-1:")
  })

  it("partitions characters with backend field names", async () => {
    await booksApi.partitionCharacter("book-1", "char-1", {
      partitions: [
        { name: "Mr. Samsa", aliases: ["Samsa patriarch"] },
        { name: "Mrs. Samsa" },
      ],
    })

    expect(postMock).toHaveBeenCalledWith("/books/book-1/characters/char-1/partition", {
      partitions: [
        { name: "Mr. Samsa", aliases: ["Samsa patriarch"] },
        { name: "Mrs. Samsa", aliases: [] },
      ],
    })
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("book:book-1:")
  })

  it("deletes characters and invalidates book caches", async () => {
    await booksApi.deleteCharacter("book-1", "char-1")

    expect(deleteMock).toHaveBeenCalledWith("/books/book-1/characters/char-1")
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("book:book-1:")
  })

  it("maps relationship updates to snake_case params", async () => {
    await booksApi.updateRelationship("book-1", "rel-1", {
      relType: "ally",
      sentiment: 0.9,
      description: "trusts",
      fromChapter: 1,
      toChapter: 5,
    })

    expect(putMock).toHaveBeenCalledWith("/books/book-1/relationships/rel-1", {
      rel_type: "ally",
      sentiment: 0.9,
      description: "trusts",
      from_chapter: 1,
      to_chapter: 5,
    })
  })

  it("saves obsidian notes and invalidates related caches", async () => {
    await booksApi.saveObsidianNote("book-1", { path: "Scenes/One.md", content: "# One" })

    expect(putMock).toHaveBeenCalledWith("/books/book-1/notes/obsidian", {
      path: "Scenes/One.md",
      content: "# One",
    })
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("book:book-1:obsidian-notes")
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("book:book-1:obsidian-graph")
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("book:book-1:obsidian-relations:")
  })

  it("deletes obsidian notes with encoded paths and invalidates caches", async () => {
    await booksApi.deleteObsidianNote("book-1", "Scenes/Act 1.md")

    expect(deleteMock).toHaveBeenCalledWith("/books/book-1/notes/obsidian/Scenes%2FAct%201.md")
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("book:book-1:obsidian-notes")
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
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("book:book-1:")
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("books:notes")
  })

  it("deletes book notes and invalidates note caches", async () => {
    await booksApi.deleteBookNote("book-1", "note-1")

    expect(deleteMock).toHaveBeenCalledWith("/books/book-1/notes/note-1")
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("book:book-1:")
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("books:notes")
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

  it("creates series and invalidates series caches", async () => {
    await booksApi.createSeries({ name: "Saga" })

    expect(postMock).toHaveBeenCalledWith("/books/series", { name: "Saga" })
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("books:series")
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("books:series-bible:")
  })

  it("adds books to series and invalidates book and series bible caches", async () => {
    await booksApi.addBookToSeries("series-1", "book-1", { position: 2 })

    expect(postMock).toHaveBeenCalledWith("/books/series/series-1/books/book-1", { position: 2 })
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("book:book-1:")
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("books:series-bible:")
  })

  it("removes books from series and invalidates book and series bible caches", async () => {
    await booksApi.removeBookFromSeries("series-1", "book-1")

    expect(deleteMock).toHaveBeenCalledWith("/books/series/series-1/books/book-1")
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("book:book-1:")
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("books:series-bible:")
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
      visibility: "public",
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
    expect(form.get("visibility")).toBe("public")
    expect(form.get("description")).toBe("Epic")
    expect(form.get("series_ids")).toBe("series-1")
    expect(form.get("auto_extract_cover")).toBe("false")
    expect(form.get("preserve_chapter_numbers")).toBe("true")
    expect(form.get("preserve_source_chapters")).toBe("true")
    expect(form.get("work_type")).toBe("novel")
    expect(form.get("mode")).toBe("author")
    expect(progress).toHaveBeenCalledWith(25)
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("books:list:")
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("books:stats")
  })

  it("imports manuscripts with formdata and invalidates book caches", async () => {
    const file = new File(["chapter"], "chapter.txt", { type: "text/plain" })

    await booksApi.importManuscript("book-1", {
      text: "Hello",
      html: "<p>Hello</p>",
      title: "Draft",
      chapterNumber: 4,
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
    expect(form.get("replace_existing")).toBe("true")
    expect(form.get("chunk_long_documents")).toBe("true")
    expect(form.get("split_into_chapters")).toBe("false")
    expect(form.get("work_type")).toBe("novel")
    expect(invalidateCachedGetsMock).toHaveBeenCalledWith("book:book-1:")
  })
})
