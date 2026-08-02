import { beforeEach, describe, expect, it } from "vitest"

import {
  booksApi,
  getMock,
  invalidateQueryKeysMock,
  postMock,
  putMock,
  resetBooksApiMocks,
} from "./books.test-utils"

describe("books api basic contracts", () => {
  beforeEach(() => {
    resetBooksApiMocks()
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

  it("loads the reader bootstrap payload", async () => {
    await booksApi.getReaderBootstrap("book-1")

    expect(getMock).toHaveBeenCalledWith("/books/book-1/reader-bootstrap")
  })

  it("loads the reader bootstrap payload with a profile", async () => {
    await booksApi.getReaderBootstrap("book-1", { profile: "critical" })

    expect(getMock).toHaveBeenCalledWith("/books/book-1/reader-bootstrap", {
      params: { profile: "critical" },
    })
  })

  it("loads the manuscript bootstrap payload with optional chapter params", async () => {
    await booksApi.getManuscriptBootstrap("book-1", {
      activeChapterNumber: 3,
      annotationChapterNumber: 2,
      profile: "critical",
    })

    expect(getMock).toHaveBeenCalledWith("/books/book-1/manuscript-bootstrap", {
      params: {
        active_chapter_number: 3,
        annotation_chapter_number: 2,
        profile: "critical",
      },
    })
  })

  it("loads manuscript annotations", async () => {
    await booksApi.getManuscriptAnnotations("book-1", 2)

    expect(getMock).toHaveBeenCalledWith("/books/book-1/annotations", { params: { chapter_number: 2 } })
  })

  it("exports a manuscript with optional table of contents", async () => {
    await booksApi.exportManuscript("book-1", "pdf", "trade_paperback", false, "eb-garamond", true)

    expect(getMock).toHaveBeenCalledWith("/books/book-1/manuscript/export", {
      params: {
        format: "pdf",
        preset: "trade_paperback",
        include_scene_metadata: false,
        font_family: "eb-garamond",
        include_toc: true,
      },
      responseType: "blob",
    })
  })

  it("exports a reader-ready novel with preset and image options", async () => {
    await booksApi.exportNovel("book-1", "epub", "large_print", true, "eb-garamond", {
      imagePlacement: "inline",
      includeImageCaptions: false,
      previewChapters: 2,
    })

    expect(getMock).toHaveBeenCalledWith("/books/book-1/novel/export", {
      params: {
        format: "epub",
        preset: "large_print",
        include_images: true,
        image_placement: "inline",
        include_image_captions: false,
        preview_chapters: 2,
        font_family: "eb-garamond",
      },
      responseType: "blob",
    })
  })

  it("saves a novel preface and invalidates the writer workspace cache", async () => {
    await booksApi.saveNovelPreface("book-1", "Before the voyage")

    expect(putMock).toHaveBeenCalledWith("/books/book-1/novel/preface", {
      preface: "Before the voyage",
    })
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:writer-workspace")
  })

  it("saves novel export settings and invalidates the writer workspace cache", async () => {
    await booksApi.saveNovelSettings("book-1", {
      preface: "Before the voyage",
      front_matter: {
        dedication: "For readers",
        acknowledgements: "Thanks",
        copyright_page: "Copyright 2026",
        about_author: "M. Author",
        series_book_list: "Book 1",
      },
      epub_metadata: {
        publisher: "LoreVia Press",
        language: "en",
        isbn: "9780000000000",
        description: "A blurb",
        series_name: "Atlas",
        series_number: "1",
      },
    })

    expect(putMock).toHaveBeenCalledWith("/books/book-1/novel/settings", {
      preface: "Before the voyage",
      front_matter: {
        dedication: "For readers",
        acknowledgements: "Thanks",
        copyright_page: "Copyright 2026",
        about_author: "M. Author",
        series_book_list: "Book 1",
      },
      epub_metadata: {
        publisher: "LoreVia Press",
        language: "en",
        isbn: "9780000000000",
        description: "A blurb",
        series_name: "Atlas",
        series_number: "1",
      },
    })
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:writer-workspace")
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
})
