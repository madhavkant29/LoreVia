import { beforeEach, describe, expect, it } from "vitest"

import {
  booksApi,
  deleteMock,
  getMock,
  invalidateQueryKeysMock,
  postMock,
  putMock,
  resetBooksApiMocks,
} from "./books.test-utils"

describe("books api misc contracts", () => {
  beforeEach(() => {
    resetBooksApiMocks()
  })

  it("covers remaining read-only book, revision, workspace, and analytics endpoints", async () => {
    getMock.mockResolvedValue({ data: { items: [{ id: "assignment-1" }] } })

    await booksApi.listQuotes()
    await booksApi.listNotes()
    await booksApi.listCollaborators("book-1")
    expect(await booksApi.listBetaReadAssignments("book-1")).toEqual([{ id: "assignment-1" }])
    await booksApi.getBookNotes("book-1")
    await booksApi.getChapterReports("book-1", 5)
    await booksApi.getStoryHealth("book-1")
    await booksApi.getRevisionIntelligence("book-1")
    await booksApi.getChapterVersions("book-1", 3, 4)
    await booksApi.getChapterVersionDetail("book-1", "version-1")
    await booksApi.getRestoreStatus("book-1", "version-1")
    await booksApi.getSceneVersions("book-1", "scene-1", 6)
    await booksApi.getSceneVersionDetail("book-1", "scene-version-1")
    await booksApi.getWorkspaceTree("book-1")
    await booksApi.listScenes("book-1", { chapterNumber: 2, status: "draft", query: "gate" })
    await booksApi.getWriterWorkspace("book-1")
    await booksApi.getEmotionalArc("book-1")
    await booksApi.getEvents("book-1")
    await booksApi.getReaderEvents("book-1", 7)
    await booksApi.getCharacters("book-1")

    expect(getMock).toHaveBeenCalledWith("/books/book-1/chapter-reports", { params: { limit: 5 } })
    expect(getMock).toHaveBeenCalledWith("/books/book-1/chapter-versions", {
      params: { chapter_number: 3, limit: 4 },
    })
    expect(getMock).toHaveBeenCalledWith("/books/book-1/scenes", {
      params: { chapter_number: 2, status: "draft", query: "gate" },
    })
    expect(getMock).toHaveBeenCalledWith("/books/book-1/events/reader", { params: { chapter: 7 } })
  })

  it("covers remaining book mutations and workspace payload mapping", async () => {
    await booksApi.retryProcessing("book-1")
    await booksApi.continueProcessing("book-1")
    await booksApi.updateCollaborator("book-1", "collab-1", {
      displayName: "Editor",
      role: "editor",
      inviteStatus: "revoked",
    } as never)
    await booksApi.deleteCollaborator("book-1", "collab-1")
    await booksApi.revokeBetaReadAssignment("book-1", "assignment-1")
    await booksApi.updateRevisionTags("book-1", {
      entityType: "chapter",
      chapterNumber: 2,
      tags: ["rewrite"],
    } as never)
    await booksApi.createSceneSnapshot("book-1", "scene-1", "checkpoint")
    await booksApi.restoreSceneVersion("book-1", "version-1")
    await booksApi.searchWorkspace("book-1", { query: "Nora" })
    await booksApi.getReadability("book-1", "A short sentence.")

    expect(postMock).toHaveBeenCalledWith("/books/book-1/processing/retry")
    expect(postMock).toHaveBeenCalledWith("/books/book-1/processing/continue")
    expect(putMock).toHaveBeenCalledWith(
      "/books/book-1/collaborators/collab-1",
      expect.objectContaining({
        display_name: "Editor",
        invite_status: "revoked",
      }),
    )
    expect(postMock).toHaveBeenCalledWith("/books/book-1/workspace/search", {
      query: "Nora",
      scopes: ["manuscript", "scenes", "notes"],
      case_sensitive: false,
      whole_word: false,
      regex: false,
      filters: {},
    })
    expect(postMock).toHaveBeenCalledWith("/books/book-1/manuscript/readability", { text: "A short sentence." })
  })

  it("covers character adjudication, relationship, export, and vault endpoints", async () => {
    await booksApi.demoteCharacter("book-1", "character-1")
    await booksApi.approveCharacter("book-1", "character-1")
    await booksApi.rejectCharacter("book-1", "character-1")
    await booksApi.repairRelationships("book-1")
    await booksApi.promoteCharacterCandidate("book-1", "candidate-1")
    await booksApi.attachCharacterCandidate("book-1", "candidate-1", "character-1")
    await booksApi.rejectCharacterCandidate("book-1", "candidate-1")
    await booksApi.attachRelationshipCandidateB("book-1", "candidate-1", "character-2")
    await booksApi.acceptDuplicateSuggestion("book-1", "duplicate-1")
    await booksApi.dismissDuplicateSuggestion("book-1", "duplicate-1")
    await booksApi.previewCharacterReprocess("book-1", { allowMergeSafePairs: false })
    await booksApi.applyCharacterReprocess("book-1", { allowDemoteObviousNoise: false })
    await booksApi.createRelationship("book-1", {
      characterAId: "a",
      characterBId: "b",
      relType: "ally",
      fromChapter: 1,
    })
    await booksApi.deleteRelationship("book-1", "relationship-1")
    await booksApi.shareCharacter("book-1", "character-1")
    await booksApi.exportCharacterCard("book-1", "character-1", "docx")
    await booksApi.exportCharacterBible("book-1", "pdf", "serif")
    await booksApi.previewCharacterBibleVault("book-1")
    await booksApi.listCharacterBibleVaultNotes("book-1")
    await booksApi.saveCharacterBibleVaultNote("book-1", { path: "Characters/Nora.md", content: "Lead" })
    await booksApi.listVaultNotes("book-1")
    await booksApi.getVaultGraph("book-1")
    await booksApi.getVaultNoteRelations("book-1", "Characters/Nora.md")
    await booksApi.importVaultNotes("book-1", new File(["note"], "notes.zip"))
    await booksApi.exportVaultNotes("book-1")

    expect(postMock).toHaveBeenCalledWith("/books/book-1/character-review/candidate-1/attach", {
      character_id: "character-1",
    })
    expect(postMock).toHaveBeenCalledWith(
      "/books/book-1/relationships",
      expect.objectContaining({
        character_a_id: "a",
        character_b_id: "b",
        rel_type: "ally",
      }),
    )
    expect(getMock).toHaveBeenCalledWith("/books/book-1/characters/character-1/export", {
      params: { format: "docx" },
      responseType: "blob",
    })
    expect(getMock).toHaveBeenCalledWith("/books/book-1/notes/vault/relations", {
      params: { path: "Characters/Nora.md" },
    })
  })

  it("covers series, mode, deletion, and empty-project contracts", async () => {
    await booksApi.listSeries({ limit: 10, offset: 20 })
    await booksApi.getSeriesBible("series-1")
    await booksApi.setSeries("book-1", { series_name: "Atlas", series_order: 2 })
    await booksApi.setSeriesBookStatus("series-1", "book-1", false)
    await booksApi.setMode("book-1", "author")
    await booksApi.delete("book-1")
    await booksApi.createEmptyProject({ title: "Untitled", genre: "Fantasy" })

    expect(getMock).toHaveBeenCalledWith("/books/series", { params: { limit: 10, offset: 20 } })
    expect(putMock).toHaveBeenCalledWith("/books/series/series-1/books/book-1/status", {
      marked_complete: false,
    })
    expect(putMock).toHaveBeenCalledWith("/books/book-1/mode", { mode: "author" })
    expect(deleteMock).toHaveBeenCalledWith("/books/book-1")
    expect(postMock).toHaveBeenCalledWith("/books/empty-project", { title: "Untitled", genre: "Fantasy" })
  })
})
