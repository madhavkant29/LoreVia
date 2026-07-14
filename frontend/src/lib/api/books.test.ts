import { beforeEach, describe, expect, it } from "vitest"

import {
  booksApi,
  deleteMock,
  getMock,
  invalidateQueryKeysMock,
  isAxiosErrorMock,
  patchMock,
  postMock,
  putMock,
  resetBooksApiMocks,
} from "./books.test-utils"

describe("books api", () => {
  beforeEach(() => {
    resetBooksApiMocks()
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

  it("confirms upload charge when reprocessing manuscript", async () => {
    await booksApi.reprocessManuscript("book-1")

    expect(postMock).toHaveBeenCalledWith("/books/book-1/manuscript/reprocess", {
      confirm_upload_charge: true,
    })
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:")
  })

  it("reprocesses a single chapter without upload confirmation", async () => {
    await booksApi.reprocessChapter("book-1", 3)

    expect(postMock).toHaveBeenCalledWith("/books/book-1/manuscript/chapters/3/reprocess", null)
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("reader:book-1:")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:writer-workspace")
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

  it("deletes chapters and invalidates book, reader, workspace, and version caches", async () => {
    await booksApi.deleteChapter("book-1", 2)

    expect(deleteMock).toHaveBeenCalledWith("/books/book-1/chapters/2")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("reader:book-1:")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:workspace-tree")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:revision-intelligence")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:chapter-versions:2:")
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

  it("manages structured character aliases and identity actions", async () => {
    await booksApi.getCharacterIdentityDiagnostics("book-1")
    await booksApi.listCharacterAliases("book-1", "char-1")
    await booksApi.addCharacterAlias("book-1", "char-1", {
      aliasText: "Gregor",
      aliasKind: "first_name",
      confidence: 0.9,
    })
    await booksApi.deleteCharacterAlias("book-1", "char-1", "alias-1")
    await booksApi.undoCharacterIdentityAction("book-1", "action-1")

    expect(getMock).toHaveBeenNthCalledWith(1, "/books/book-1/characters/identity-diagnostics")
    expect(getMock).toHaveBeenNthCalledWith(2, "/books/book-1/characters/char-1/aliases")
    expect(postMock).toHaveBeenNthCalledWith(1, "/books/book-1/characters/char-1/aliases", {
      alias_text: "Gregor",
      alias_kind: "first_name",
      confidence: 0.9,
    })
    expect(deleteMock).toHaveBeenCalledWith("/books/book-1/characters/char-1/aliases/alias-1")
    expect(postMock).toHaveBeenNthCalledWith(2, "/books/book-1/characters/identity-actions/action-1/undo")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("reader:book-1:")
  })

  it("loads character review with adjudication filters", async () => {
    await booksApi.getCharacterReview("book-1", {
      includeQuarantined: true,
      includePlaces: true,
      includeRejected: false,
    })

    expect(getMock).toHaveBeenCalledWith("/books/book-1/character-review", {
      params: {
        include_quarantined: true,
        include_places: true,
        include_rejected: false,
      },
    })
  })

  it("marks a character candidate as a place", async () => {
    await booksApi.markCharacterCandidatePlace("book-1", "candidate-1")

    expect(postMock).toHaveBeenCalledWith("/books/book-1/character-review/candidate-1/mark-place")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:")
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

})
