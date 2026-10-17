import { beforeEach, describe, expect, it, vi } from "vitest"

const {
  deleteMock,
  getMock,
  patchMock,
  postMock,
  putMock,
  prefetchInfiniteQueryMock,
  prefetchQueryMock,
  invalidateQueryKeysMock,
} = vi.hoisted(() => ({
  deleteMock: vi.fn(),
  getMock: vi.fn(),
  patchMock: vi.fn(),
  postMock: vi.fn(),
  putMock: vi.fn(),
  prefetchInfiniteQueryMock: vi.fn(),
  prefetchQueryMock: vi.fn(),
  invalidateQueryKeysMock: vi.fn(),
}))

vi.mock("./client", () => ({
  apiClient: {
    delete: deleteMock,
    get: getMock,
    patch: patchMock,
    post: postMock,
    put: putMock,
  },
}))

vi.mock("@/lib/query/queryClient", () => ({
  queryClient: {
    prefetchInfiniteQuery: prefetchInfiniteQueryMock,
    prefetchQuery: prefetchQueryMock,
  },
  invalidateQueryKeys: invalidateQueryKeysMock,
}))

vi.mock("@/lib/api/notifications", () => ({
  notificationsApi: {
    list: vi.fn().mockResolvedValue([{ id: "notification-1" }]),
  },
}))

import { notificationsApi } from "@/lib/api/notifications"
import {
  NOTIFICATIONS_SIDEBAR_LIMIT,
  NOTIFICATIONS_SIDEBAR_QUERY_KEY,
  SOCIAL_CONVERSATIONS_SIDEBAR_LIMIT,
  SOCIAL_CONVERSATIONS_QUERY_KEY,
  SOCIAL_RELATIONSHIPS_QUERY_KEY,
  prefetchChatsSidebarData,
  prefetchNotificationsSidebarData,
} from "@/lib/query/sidebarPrefetch"
import { billingApi } from "./billing"
import { booksApi } from "./books"
import { socialApi } from "./social"
import { worldBuildingApi } from "./worldBuilding"

describe("runtime api wrappers", () => {
  beforeEach(() => {
    deleteMock.mockReset()
    getMock.mockReset()
    patchMock.mockReset()
    postMock.mockReset()
    putMock.mockReset()
    prefetchInfiniteQueryMock.mockReset()
    prefetchQueryMock.mockReset()
    invalidateQueryKeysMock.mockReset()

    deleteMock.mockResolvedValue({ data: { ok: true } })
    getMock.mockResolvedValue({ data: { ok: true } })
    patchMock.mockResolvedValue({ data: { ok: true } })
    postMock.mockResolvedValue({ data: { ok: true } })
    putMock.mockResolvedValue({ data: { ok: true } })
    prefetchInfiniteQueryMock.mockResolvedValue(undefined)
    prefetchQueryMock.mockResolvedValue(undefined)
    vi.mocked(notificationsApi.list).mockClear()
  })

  it("builds billing checkout, confirmation, and portal requests", async () => {
    await billingApi.checkoutPreview("author_monthly")
    await billingApi.checkout("author_monthly", true, "signed-quote")
    await billingApi.abandonCheckout("txn-1")
    await billingApi.confirmation("txn-1", "confirm-1")
    await billingApi.portal()

    expect(postMock).toHaveBeenNthCalledWith(1, "/billing/checkout/preview", { plan: "author_monthly" })
    expect(postMock).toHaveBeenNthCalledWith(2, "/billing/checkout", {
      plan: "author_monthly",
      confirmed_immediate_charge: true,
      quote_token: "signed-quote",
    })
    expect(postMock).toHaveBeenNthCalledWith(3, "/billing/checkout/abandon", {
      transaction_id: "txn-1",
    })
    expect(getMock).toHaveBeenCalledWith("/billing/confirmation", {
      params: { transaction_id: "txn-1", confirmation_token: "confirm-1" },
    })
    expect(postMock).toHaveBeenNthCalledWith(4, "/billing/portal")
  })

  it("omits optional billing confirmation tokens", async () => {
    await billingApi.confirmation("txn-2")

    expect(getMock).toHaveBeenCalledWith("/billing/confirmation", {
      params: { transaction_id: "txn-2" },
    })
  })

  it("builds social relationship and messaging endpoints", async () => {
    await socialApi.searchUsers("mira")
    await socialApi.sendFriendRequest("user-2")
    await socialApi.acceptFriendRequest("request-1")
    await socialApi.declineFriendRequest("request-2")
    await socialApi.cancelFriendRequest("request-3")
    await socialApi.openDirectConversation("user-3")
    await socialApi.listMessages("conversation-1", 25)
    await socialApi.listConversationsPage(30, "next-conversations")
    await socialApi.listMessagesPage("conversation-1", 25, "next-messages")
    await socialApi.sendMessage("conversation-1", "Hello")
    await socialApi.markConversationRead("conversation-1")

    expect(getMock).toHaveBeenCalledWith("/social/users/search", { params: { q: "mira" } })
    expect(postMock).toHaveBeenCalledWith("/social/friend-requests", { target_user_id: "user-2" })
    expect(postMock).toHaveBeenCalledWith("/social/friend-requests/request-1/accept")
    expect(postMock).toHaveBeenCalledWith("/social/friend-requests/request-2/decline")
    expect(postMock).toHaveBeenCalledWith("/social/friend-requests/request-3/cancel")
    expect(postMock).toHaveBeenCalledWith("/social/conversations/direct", { target_user_id: "user-3" })
    expect(getMock).toHaveBeenCalledWith("/social/conversations/conversation-1/messages", { params: { limit: 25 } })
    expect(getMock).toHaveBeenCalledWith("/social/conversations/page", {
      params: { limit: 30, cursor: "next-conversations" },
    })
    expect(getMock).toHaveBeenCalledWith("/social/conversations/conversation-1/messages/page", {
      params: { limit: 25, cursor: "next-messages" },
    })
    expect(postMock).toHaveBeenCalledWith("/social/conversations/conversation-1/messages", { body: "Hello" })
    expect(postMock).toHaveBeenCalledWith("/social/conversations/conversation-1/read")
  })

  it("builds world-building document requests with normalized book routes", async () => {
    const file = new File(["Lore text"], "lore.txt", { type: "text/plain" })

    await worldBuildingApi.getBootstrap("book-1", { documentId: "doc-1", focus: "gap" })
    await worldBuildingApi.listDocuments("book-1", true)
    await worldBuildingApi.uploadDocuments("book-1", {
      title: "Canon",
      text: "Plain",
      html: "<p>Plain</p>",
      replaceExisting: true,
      files: [file],
    })
    await worldBuildingApi.getDocument("book-1", "doc-1")
    await worldBuildingApi.updateDocument("book-1", "doc-1", { title: "Updated", text: "Text" })
    await worldBuildingApi.deleteDocument("book-1", "doc-1")

    expect(getMock).toHaveBeenCalledWith("/intelligence/book-1/world-building/bootstrap", {
      params: { document_id: "doc-1", focus: "gap" },
    })
    expect(getMock).toHaveBeenCalledWith("/intelligence/book-1/world-building/documents", {
      params: { include_inactive: true },
    })
    const form = postMock.mock.calls[0]?.[1] as FormData
    expect(Array.from(form.entries())).toEqual([
      ["title", "Canon"],
      ["text", "Plain"],
      ["html", "<p>Plain</p>"],
      ["replace_existing", "true"],
      ["files", file],
    ])
    expect(postMock).toHaveBeenCalledWith(
      "/intelligence/book-1/world-building/documents",
      form,
      { headers: { "Content-Type": "multipart/form-data" } },
    )
    expect(getMock).toHaveBeenCalledWith("/intelligence/book-1/world-building/documents/doc-1")
    expect(patchMock).toHaveBeenCalledWith("/intelligence/book-1/world-building/documents/doc-1", {
      title: "Updated",
      text: "Text",
    })
    expect(deleteMock).toHaveBeenCalledWith("/intelligence/book-1/world-building/documents/doc-1")
  })

  it("builds world-building analysis, wiki, note, and canon endpoints", async () => {
    await worldBuildingApi.analyze("book-1", { mode: "gap", query: "storms", auto_create_notes: true })
    await worldBuildingApi.getGaps("book-1")
    await worldBuildingApi.getIntegration("book-1")
    await worldBuildingApi.listElements("book-1")
    await worldBuildingApi.query("book-1", { query: "What is canon?", mode: null })
    await worldBuildingApi.listWiki("book-1")
    await worldBuildingApi.generateWiki("book-1")
    await worldBuildingApi.getSeriesAnalysis("series-1")
    await worldBuildingApi.acceptSuggestion("element-1", { suggestion_id: "suggestion-1", mark_implemented: true })
    await worldBuildingApi.listNotes("book-1")
    await worldBuildingApi.getNotesByChapter("book-1", 4)
    await worldBuildingApi.createNote("book-1", { title: "Fix", body: "Anchor this." })
    await worldBuildingApi.updateNoteStatus("book-1", "note-1", "resolved")
    await worldBuildingApi.deleteNote("book-1", "note-1")
    await worldBuildingApi.listCanonOverrides("book-1")
    await worldBuildingApi.saveCanonOverride("book-1", { canonical_name: "Moon Court", aliases: ["Court"] })

    expect(postMock).toHaveBeenCalledWith("/intelligence/book-1/world-building/analyze", {
      mode: "gap",
      query: "storms",
      auto_create_notes: true,
    })
    expect(getMock).toHaveBeenCalledWith("/intelligence/book-1/world-building/gaps")
    expect(getMock).toHaveBeenCalledWith("/intelligence/book-1/world-building/integration")
    expect(getMock).toHaveBeenCalledWith("/intelligence/book-1/world-building/elements")
    expect(postMock).toHaveBeenCalledWith("/intelligence/book-1/world-building/query", {
      query: "What is canon?",
      mode: null,
    })
    expect(getMock).toHaveBeenCalledWith("/intelligence/book-1/world-building/wiki")
    expect(postMock).toHaveBeenCalledWith("/intelligence/book-1/world-building/wiki/generate")
    expect(getMock).toHaveBeenCalledWith("/intelligence/series/series-1/world-building/series-analysis")
    expect(postMock).toHaveBeenCalledWith("/intelligence/element-1/world-building/accept-suggestion", {
      suggestion_id: "suggestion-1",
      mark_implemented: true,
    })
    expect(getMock).toHaveBeenCalledWith("/intelligence/book-1/world-building/notes")
    expect(getMock).toHaveBeenCalledWith("/intelligence/book-1/world-building/notes/by-chapter/4")
    expect(postMock).toHaveBeenCalledWith("/intelligence/book-1/world-building/notes", {
      title: "Fix",
      body: "Anchor this.",
    })
    expect(patchMock).toHaveBeenCalledWith("/intelligence/book-1/world-building/notes/note-1/status", {
      status: "resolved",
    })
    expect(deleteMock).toHaveBeenCalledWith("/intelligence/book-1/world-building/notes/note-1")
    expect(getMock).toHaveBeenCalledWith("/intelligence/book-1/world-building/canon-overrides")
    expect(postMock).toHaveBeenCalledWith("/intelligence/book-1/world-building/canon-overrides", {
      canonical_name: "Moon Court",
      aliases: ["Court"],
    })
  })

  it("prefetches sidebar data through stable query keys", async () => {
    await prefetchNotificationsSidebarData()
    await prefetchChatsSidebarData()

    expect(prefetchInfiniteQueryMock).toHaveBeenCalledWith({
      queryKey: NOTIFICATIONS_SIDEBAR_QUERY_KEY,
      initialPageParam: null,
      queryFn: expect.any(Function),
      getNextPageParam: expect.any(Function),
    })
    await prefetchInfiniteQueryMock.mock.calls[0]?.[0].queryFn({ pageParam: null })
    expect(notificationsApi.list).toHaveBeenCalledWith(NOTIFICATIONS_SIDEBAR_LIMIT, { cursor: null })
    expect(prefetchQueryMock).toHaveBeenCalledWith({
      queryKey: SOCIAL_CONVERSATIONS_QUERY_KEY,
      queryFn: expect.any(Function),
    })
    await prefetchQueryMock.mock.calls[0]?.[0].queryFn()
    expect(getMock).toHaveBeenCalledWith("/social/conversations/page", {
      params: { limit: SOCIAL_CONVERSATIONS_SIDEBAR_LIMIT },
    })
    expect(prefetchQueryMock).toHaveBeenCalledWith({
      queryKey: SOCIAL_RELATIONSHIPS_QUERY_KEY,
      queryFn: socialApi.listRelationships,
    })
  })

  it("builds complete upload, manuscript import, preview, and cover forms", async () => {
    const manuscript = new File(["Chapter One"], "draft.docx", { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" })
    const cover = new File(["cover"], "cover.jpg", { type: "image/jpeg" })
    const progress = vi.fn()

    await booksApi.upload(manuscript, "Gate Draft", "Fantasy", "Mira", {
      visibility: "private",
      description: "A gate story",
      seriesIds: ["series-1", "", "series-2"],
      autoExtractCover: false,
      preserveChapterNumbers: true,
      preserveSourceChapters: true,
      forceSingleManuscript: true,
      workType: "novel",
      coverFile: cover,
      mode: "author",
      onProgress: progress,
    })
    const uploadForm = postMock.mock.calls[0]?.[1] as FormData
    expect(Array.from(uploadForm.entries())).toEqual(expect.arrayContaining([
      ["file", manuscript], ["title", "Gate Draft"], ["genre", "Fantasy"], ["author", "Mira"],
      ["visibility", "private"], ["description", "A gate story"], ["series_ids", "series-1"],
      ["series_ids", "series-2"], ["work_type", "novel"], ["mode", "author"],
      ["auto_extract_cover", "false"], ["preserve_chapter_numbers", "true"],
      ["preserve_source_chapters", "true"], ["force_single_manuscript", "true"], ["cover_file", cover],
    ]))
    const uploadConfig = postMock.mock.calls[0]?.[2] as { onUploadProgress: (event: { loaded: number; total?: number }) => void }
    uploadConfig.onUploadProgress({ loaded: 150, total: 100 })
    uploadConfig.onUploadProgress({ loaded: 1 })
    expect(progress).toHaveBeenCalledWith(100)

    postMock.mockClear()
    await booksApi.importManuscript("book 1", {
      text: "Plain text",
      html: "<p>Plain text</p>",
      title: "Imported",
      chapterNumber: 4,
      expectedContentVersion: 7,
      replaceExisting: true,
      chunkLongDocuments: true,
      splitIntoChapters: false,
      workType: "novel",
      files: [manuscript],
    })
    const importForm = postMock.mock.calls[0]?.[1] as FormData
    expect(Array.from(importForm.entries())).toEqual(expect.arrayContaining([
      ["text", "Plain text"], ["html", "<p>Plain text</p>"], ["title", "Imported"],
      ["chapter_number", "4"], ["expected_content_version", "7"], ["replace_existing", "true"],
      ["chunk_long_documents", "true"], ["split_into_chapters", "false"], ["work_type", "novel"], ["files", manuscript],
    ]))

    await booksApi.previewUpload(manuscript, "novel")
    await booksApi.updateCover("book-1", cover)
    await booksApi.deleteCover("book-1")
    expect(putMock).toHaveBeenCalledWith("/books/book-1/cover", expect.any(FormData))
    expect(deleteMock).toHaveBeenCalledWith("/books/book-1/cover")
  })

  it("handles archive, hide fallback, permanent deletion, and publishing mutations", async () => {
    await booksApi.archive("book-1", false)
    await booksApi.hide("book-1", false)
    await booksApi.deletePermanently("book-1", "DELETE Gate Draft")
    await booksApi.publishPublicly("book-1", { publicSlug: "gate-draft", rightsConfirmation: true })
    await booksApi.unpublishPublicly("book-1")

    expect(putMock).toHaveBeenCalledWith("/books/book-1/archive", null, { params: { archived: false } })
    expect(putMock).toHaveBeenCalledWith("/books/book-1/hide", null, { params: { hidden: false } })
    expect(deleteMock).toHaveBeenCalledWith("/books/book-1/permanent", { data: { confirmation_text: "DELETE Gate Draft" } })
    expect(postMock).toHaveBeenCalledWith("/books/book-1/publish", expect.objectContaining({ public_slug: "gate-draft", description: null }))

    putMock.mockRejectedValueOnce({ isAxiosError: true, response: { status: 404 } })
    await booksApi.hide("book-2", true)
    expect(deleteMock).toHaveBeenCalledWith("/books/book-2")

    const forbidden = { isAxiosError: true, response: { status: 403 } }
    putMock.mockRejectedValueOnce(forbidden)
    await expect(booksApi.hide("book-3", true)).rejects.toBe(forbidden)
  })

  it("creates and updates scenes while invalidating workspace and reader caches", async () => {
    await booksApi.saveScene("book-1", { title: "New scene", body: "Draft" })
    await booksApi.saveScene("book-1", { id: "scene-1", title: "Updated scene", body: "Revision" })
    await booksApi.deleteScene("book-1", "scene-1")
    await booksApi.reorderChapterScenes("book-1", 3, { sceneIds: ["scene-2", "scene-1"], expectedStructureVersion: 9 })
    await booksApi.getSceneInsertion("book-1", "scene-2", 3, "start", false)

    expect(postMock).toHaveBeenCalledWith("/books/book-1/scenes", expect.objectContaining({ title: "New scene" }))
    expect(putMock).toHaveBeenCalledWith("/books/book-1/scenes/scene-1", expect.objectContaining({ title: "Updated scene" }))
    expect(patchMock).toHaveBeenCalledWith("/books/book-1/chapters/3/scenes/order", {
      scene_ids: ["scene-2", "scene-1"],
      expected_structure_version: 9,
    })
    expect(postMock).toHaveBeenCalledWith("/books/book-1/scenes/scene-2/insert", null, {
      params: { chapter_number: 3, position: "start", include_metadata: false },
    })
    expect(invalidateQueryKeysMock).toHaveBeenCalled()
  })
})
