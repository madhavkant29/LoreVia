import { beforeEach, describe, expect, it, vi } from "vitest"

const {
  getMock,
  postMock,
  putMock,
  patchMock,
  deleteMock,
  invalidateQueryKeysMock,
  isAxiosErrorMock,
} = vi.hoisted(() => ({
  getMock: vi.fn(),
  postMock: vi.fn(),
  putMock: vi.fn(),
  patchMock: vi.fn(),
  deleteMock: vi.fn(),
  invalidateQueryKeysMock: vi.fn(),
  isAxiosErrorMock: vi.fn(),
}))

vi.mock("./client", () => ({
  apiClient: {
    get: getMock,
    post: postMock,
    put: putMock,
    patch: patchMock,
    delete: deleteMock,
  },
}))

vi.mock("@/lib/query/queryClient", () => ({
  invalidateQueryKeys: invalidateQueryKeysMock,
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
    patchMock.mockReset()
    deleteMock.mockReset()
    invalidateQueryKeysMock.mockReset()
    isAxiosErrorMock.mockReset()

    getMock.mockResolvedValue({ data: { ok: true } })
    postMock.mockResolvedValue({ data: { ok: true } })
    putMock.mockResolvedValue({ data: { ok: true } })
    patchMock.mockResolvedValue({ data: { ok: true } })
    deleteMock.mockResolvedValue({ data: { ok: true } })
  })

  it("lists active books", async () => {
    await booksApi.list()

    expect(getMock).toHaveBeenCalledWith("/books", { params: { include_hidden: false } })
  })

  it("lists all books when include hidden is true", async () => {
    await booksApi.list(true)

    expect(getMock).toHaveBeenCalledWith("/books", { params: { include_hidden: true } })
  })

  it("loads stats", async () => {
    await booksApi.getStats()

    expect(getMock).toHaveBeenCalledWith("/books/stats")
  })

  it("loads a book detail", async () => {
    await booksApi.get("book-1")

    expect(getMock).toHaveBeenCalledWith("/books/book-1")
  })

  it("loads the aggregated reader overview payload", async () => {
    await booksApi.getOverview("book-1")

    expect(getMock).toHaveBeenCalledWith("/books/book-1/overview")
  })

  it("loads manuscript annotations", async () => {
    await booksApi.getManuscriptAnnotations("book-1", 2)

    expect(getMock).toHaveBeenCalledWith("/books/book-1/annotations", { params: { chapter_number: 2 } })
  })

  it("loads collaborator activity", async () => {
    await booksApi.getCollaboratorActivity("book-1", "collab-7")

    expect(getMock).toHaveBeenCalledWith("/books/book-1/collaborators/collab-7/activity")
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
      permissions: {
        can_edit_manuscript: true,
        can_view_story_bible: true,
        can_run_ai_scans: true,
        can_export: true,
        can_comment: true,
        can_view_selected_chapters_only: false,
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
      permissions: {
        can_edit_manuscript: true,
        can_view_story_bible: true,
        can_run_ai_scans: true,
        can_export: true,
        can_comment: true,
        can_view_selected_chapters_only: false,
      },
    })
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:")
  })

  it("creates beta read assignments with backend field names", async () => {
    await booksApi.createBetaReadAssignment("book-1", {
      readerEmail: "beta@example.com",
      taskLabel: "Review Chapter 12",
      scopeKind: "chapter_range",
      chapterStart: 12,
      chapterEnd: 12,
      windowDays: 5,
      requiredProgressPct: 100,
      requiredCommentCount: 3,
      requiredFeedbackItemCount: 2,
      requireFinalFeedback: true,
      startsAt: "2026-05-14T12:00:00Z",
      authorQuestions: ["What confused you?", "Which scene landed best?"],
    })

    expect(postMock).toHaveBeenCalledWith("/books/book-1/beta-reads", {
      reader_email: "beta@example.com",
      task_label: "Review Chapter 12",
      scope_kind: "chapter_range",
      section_label: undefined,
      chapter_start: 12,
      chapter_end: 12,
      window_days: 5,
      required_progress_pct: 100,
      required_comment_count: 3,
      required_feedback_item_count: 2,
      require_final_feedback: true,
      starts_at: "2026-05-14T12:00:00Z",
      author_questions: ["What confused you?", "Which scene landed best?"],
    })
  })

  it("normalizes readable route segments before loading book detail", async () => {
    await booksApi.get("sky-harbor--123e4567-e89b-12d3-a456-426614174000")

    expect(getMock).toHaveBeenCalledWith("/books/123e4567-e89b-12d3-a456-426614174000")
  })

  it("loads pre-writing checks with an explicit chapter", async () => {
    await booksApi.getPreWritingCheck("book-1", 4)

    expect(getMock).toHaveBeenCalledWith("/books/book-1/pre-writing-check", { params: { upcoming_chapter: 4 } })
  })

  it("loads pre-writing checks without params when chapter is omitted", async () => {
    await booksApi.getPreWritingCheck("book-1")

    expect(getMock).toHaveBeenCalledWith("/books/book-1/pre-writing-check", { params: undefined })
  })

  it("creates chapter snapshots and invalidates version caches", async () => {
    await booksApi.createChapterSnapshot("book-1", 7, "checkpoint")

    expect(postMock).toHaveBeenCalledWith("/books/book-1/chapters/7/snapshot", null, {
      params: { note: "checkpoint" },
    })
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:chapter-versions:7:")
  })

  it("restores chapter versions and invalidates book and reader caches", async () => {
    await booksApi.restoreChapterVersion("book-1", "version-9")

    expect(postMock).toHaveBeenCalledWith("/books/book-1/chapter-versions/version-9/restore")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("reader:book-1:")
  })

  it("saves an existing scene with put and invalidates workspace caches", async () => {
    await booksApi.saveScene("book-1", { id: "scene-1", title: "Scene", body: "Body" })

    expect(putMock).toHaveBeenCalledWith("/books/book-1/scenes/scene-1", {
      id: "scene-1",
      title: "Scene",
      body: "Body",
    })
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:workspace-tree")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:scenes:")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:revision-intelligence")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("reader:book-1:")
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
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:workspace-tree")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:scenes:")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:revision-intelligence")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("reader:book-1:")
  })

  it("reorders chapter scenes with version-aware payloads", async () => {
    await booksApi.reorderChapterScenes("book-1", 2, {
      sceneIds: ["scene-3", "scene-1", "scene-2"],
      expectedStructureVersion: 4,
    })

    expect(patchMock).toHaveBeenCalledWith("/books/book-1/chapters/2/scenes/order", {
      scene_ids: ["scene-3", "scene-1", "scene-2"],
      expected_structure_version: 4,
    })
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:workspace-tree")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:scenes:")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:revision-intelligence")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("reader:book-1:")
  })

  it("updates writer workspace and invalidates its cache entry", async () => {
    await booksApi.updateWriterWorkspace("book-1", { publishing: { active_preset: "kdp_paperback" } } as never)

    expect(putMock).toHaveBeenCalledWith("/books/book-1/writer-workspace", {
      publishing: { active_preset: "kdp_paperback" },
    })
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:writer-workspace")
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
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:")
  })

  it("maps repair-protection updates onto the character payload", async () => {
    await booksApi.updateCharacter("book-1", "char-1", {
      protectedFromRepair: true,
    })

    expect(putMock).toHaveBeenCalledWith("/books/book-1/characters/char-1", {
      name: undefined,
      aliases: undefined,
      role: undefined,
      description: undefined,
      goal: undefined,
      lie_they_believe: undefined,
      backstory_wound: undefined,
      arc_type: undefined,
      arc_summary: undefined,
      personality_tags: undefined,
      motivations: undefined,
      fears: undefined,
      graph_visibility: undefined,
      protected_from_repair: true,
    })
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("reader:book-1:")
  })

  it("attaches the left side of a relationship review candidate", async () => {
    await booksApi.attachRelationshipCandidateA("book-1", "rel-1", "char-1")

    expect(postMock).toHaveBeenCalledWith("/books/book-1/relationship-review/rel-1/attach-a", {
      character_id: "char-1",
    })
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:")
  })

  it("accepts a relationship review candidate with backend field names", async () => {
    await booksApi.acceptRelationshipCandidate("book-1", "rel-1", {
      characterAId: "char-a",
      characterBId: "char-b",
      relType: "family",
      sentiment: -0.5,
      description: "Household strain",
      fromChapter: 3,
      toChapter: 5,
    })

    expect(postMock).toHaveBeenCalledWith("/books/book-1/relationship-review/rel-1/accept", {
      character_a_id: "char-a",
      character_b_id: "char-b",
      rel_type: "family",
      sentiment: -0.5,
      description: "Household strain",
      from_chapter: 3,
      to_chapter: 5,
    })
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("reader:book-1:")
  })

  it("resolves and rejects relationship review candidates", async () => {
    await booksApi.resolveRelationshipCandidate("book-1", "rel-1")
    await booksApi.rejectRelationshipCandidate("book-1", "rel-2")

    expect(postMock).toHaveBeenNthCalledWith(1, "/books/book-1/relationship-review/rel-1/resolve")
    expect(postMock).toHaveBeenNthCalledWith(2, "/books/book-1/relationship-review/rel-2/reject")
  })

  it("saves manuscript annotations with anchor metadata", async () => {
    await booksApi.saveManuscriptAnnotation("book-1", {
      chapterNumber: 2,
      category: "continuity",
      visibility: "private",
      status: "open",
      quote: "The bell cracked at dawn.",
      comment: "Watch the bell detail here.",
      anchorContextBefore: "Nora waited.",
      anchorContextAfter: "The gate opened.",
      startOffset: 12,
      endOffset: 36,
    })

    expect(postMock).toHaveBeenCalledWith("/books/book-1/annotations", {
      annotation_id: undefined,
      chapter_number: 2,
      category: "continuity",
      status: "open",
      visibility: "private",
      quote: "The bell cracked at dawn.",
      comment: "Watch the bell detail here.",
      anchor_context_before: "Nora waited.",
      anchor_context_after: "The gate opened.",
      start_offset: 12,
      end_offset: 36,
    })
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:annotations:")
  })

  it("deletes manuscript annotations and invalidates their cache", async () => {
    await booksApi.deleteManuscriptAnnotation("book-1", "annotation-1")

    expect(deleteMock).toHaveBeenCalledWith("/books/book-1/annotations/annotation-1")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:annotations:")
  })

  it("maps character create payload fields to the backend shape", async () => {
    await booksApi.createCharacter("book-1", {
      name: "Aunt May",
      firstChapter: 2,
      aliases: ["May"],
      role: "sc",
      description: "Watchful",
      arcSummary: "Protects the family",
      personalityTags: ["sharp"],
      motivations: ["Keep everyone safe"],
      fears: ["Failure"],
    })

    expect(postMock).toHaveBeenCalledWith("/books/book-1/characters", {
      name: "Aunt May",
      first_chapter: 2,
      aliases: ["May"],
      role: "sc",
      description: "Watchful",
      arc_summary: "Protects the family",
      personality_tags: ["sharp"],
      motivations: ["Keep everyone safe"],
      fears: ["Failure"],
    })
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:")
  })

  it("merges characters with backend field names", async () => {
    await booksApi.mergeCharacters("book-1", { primaryId: "a", secondaryId: "b" })

    expect(postMock).toHaveBeenCalledWith("/books/book-1/characters/merge", {
      primary_id: "a",
      secondary_id: "b",
    })
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:")
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
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:")
  })

  it("deletes characters and invalidates book caches", async () => {
    await booksApi.deleteCharacter("book-1", "char-1")

    expect(deleteMock).toHaveBeenCalledWith("/books/book-1/characters/char-1")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:")
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
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:obsidian-notes")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:obsidian-graph")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:obsidian-relations:")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:workspace-tree")
  })

  it("deletes obsidian notes with encoded paths and invalidates caches", async () => {
    await booksApi.deleteObsidianNote("book-1", "Scenes/Act 1.md")

    expect(deleteMock).toHaveBeenCalledWith("/books/book-1/notes/obsidian/Scenes%2FAct%201.md")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:obsidian-notes")
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
})
