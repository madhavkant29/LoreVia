import axios from "axios"
import { afterEach, describe, expect, it, vi } from "vitest"

import {
  buildManuscriptOutboxEntryId,
  buildQueuedManuscriptConflictOverwrite,
  enqueueManuscriptSave,
  filterManuscriptOutboxEntriesForUser,
  isOfflineSaveError,
  isSameQueuedManuscriptSave,
  listManuscriptOutbox,
  manuscriptOutboxEntryBelongsToUser,
  queuedManuscriptSaveMatchesContent,
} from "./manuscriptOutbox"

describe("manuscript offline outbox", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("recognizes offline and transport failures without treating ordinary errors as offline", () => {
    vi.stubGlobal("navigator", { onLine: false })
    expect(isOfflineSaveError(new Error("save failed"))).toBe(true)

    vi.stubGlobal("navigator", { onLine: true })
    expect(isOfflineSaveError(new axios.AxiosError("Network Error"))).toBe(true)
    expect(isOfflineSaveError(new Error("validation failed"))).toBe(false)
  })

  it("degrades safely when IndexedDB is unavailable", async () => {
    vi.stubGlobal("indexedDB", undefined)

    await expect(enqueueManuscriptSave({
      bookId: "book-1",
      chapterNumber: 2,
      title: "Chapter 2",
      text: "Local draft",
      html: "<p>Local draft</p>",
    })).resolves.toBeNull()
    await expect(listManuscriptOutbox()).resolves.toEqual([])
  })

  it("does not treat a newer draft as the entry an in-flight sync originally read", () => {
    const original = {
      id: buildManuscriptOutboxEntryId("user-a", "book-1", 2),
      userId: "user-a",
      bookId: "book-1",
      chapterNumber: 2,
      title: "Chapter 2",
      text: "Original offline draft",
      html: "<p>Original offline draft</p>",
      expectedContentVersion: 3,
      createdAt: "2026-08-11T00:00:00.000Z",
      attempts: 0,
      status: "pending" as const,
    }
    const newer = {
      ...original,
      text: "Newer offline draft",
      html: "<p>Newer offline draft</p>",
    }

    expect(isSameQueuedManuscriptSave(original, original)).toBe(true)
    expect(isSameQueuedManuscriptSave(newer, original)).toBe(false)
    expect(queuedManuscriptSaveMatchesContent(original, original)).toBe(true)
    expect(queuedManuscriptSaveMatchesContent(newer, original)).toBe(false)
  })

  it("turns a conflict into an explicit versionless overwrite without changing its content", () => {
    const conflict = {
      id: buildManuscriptOutboxEntryId("user-a", "book-1", 2),
      userId: "user-a",
      bookId: "book-1",
      chapterNumber: 2,
      title: "Chapter 2",
      text: "Recovered offline draft",
      html: "<p>Recovered offline draft</p>",
      expectedContentVersion: 3,
      createdAt: "2026-08-11T00:00:00.000Z",
      attempts: 1,
      status: "conflict" as const,
    }

    expect(buildQueuedManuscriptConflictOverwrite(conflict)).toEqual({
      ...conflict,
      expectedContentVersion: undefined,
      attempts: 2,
      status: "pending",
    })
  })

  it("accepts only entries whose owner and composite ID match the active user", () => {
    const entry = {
      id: buildManuscriptOutboxEntryId("user-a", "book-1", 2),
      userId: "user-a",
      bookId: "book-1",
      chapterNumber: 2,
    }

    expect(manuscriptOutboxEntryBelongsToUser(entry, "user-a")).toBe(true)
    expect(manuscriptOutboxEntryBelongsToUser(entry, "user-b")).toBe(false)
    expect(manuscriptOutboxEntryBelongsToUser({ ...entry, id: "book-1:2" }, "user-a")).toBe(false)
  })

  it("rejects unattributable legacy records", () => {
    const legacyEntry = {
      id: "book-1:2",
      bookId: "book-1",
      chapterNumber: 2,
    }

    expect(manuscriptOutboxEntryBelongsToUser(legacyEntry, "user-a")).toBe(false)
  })

  it("filters cross-account and legacy records before they can be rendered or synced", () => {
    const userAEntry = {
      id: buildManuscriptOutboxEntryId("user-a", "book-a", 1),
      userId: "user-a",
      bookId: "book-a",
      chapterNumber: 1,
      title: "User A secret",
      text: "A",
      html: "<p>A</p>",
      createdAt: "2026-08-11T00:00:00.000Z",
      attempts: 0,
      status: "pending" as const,
    }
    const userBEntry = {
      ...userAEntry,
      id: buildManuscriptOutboxEntryId("user-b", "book-b", 2),
      userId: "user-b",
      bookId: "book-b",
      chapterNumber: 2,
      title: "User B draft",
    }
    const legacyEntry = { ...userAEntry, id: "book-a:1", userId: "" }

    expect(filterManuscriptOutboxEntriesForUser(
      [userAEntry, userBEntry, legacyEntry],
      "user-b",
    )).toEqual([userBEntry])
    expect(filterManuscriptOutboxEntriesForUser([userAEntry], null)).toEqual([])
  })
})
