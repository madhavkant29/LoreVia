import axios from "axios"

import { booksApi } from "@/lib/api/books"
import { useAuthStore } from "@/lib/stores/authStore"

export type ManuscriptOutboxEntry = {
  id: string
  userId: string
  bookId: string
  chapterNumber: number
  title: string
  text: string
  html: string
  expectedContentVersion?: number
  createdAt: string
  attempts: number
  status: "pending" | "conflict"
}

const DATABASE_NAME = "lorevia-offline"
const DATABASE_VERSION = 2
const STORE_NAME = "manuscript-saves"
const USER_ID_INDEX = "user-id"
export const MANUSCRIPT_OUTBOX_EVENT = "lorevia:manuscript-outbox"

type ManuscriptSyncResult = { synced: number; conflicts: number; pending: number }

const activeSyncByUser = new Map<string, Promise<ManuscriptSyncResult>>()

function getActiveUserId() {
  return useAuthStore.getState().user?.id ?? null
}

export function buildManuscriptOutboxEntryId(userId: string, bookId: string, chapterNumber: number) {
  return `${userId}:${bookId}:${chapterNumber}`
}

export function manuscriptOutboxEntryBelongsToUser(
  entry: Partial<Pick<ManuscriptOutboxEntry, "id" | "userId" | "bookId" | "chapterNumber">> | null | undefined,
  userId: string,
) {
  return Boolean(
    entry
    && entry.userId === userId
    && typeof entry.bookId === "string"
    && typeof entry.chapterNumber === "number"
    && entry.id === buildManuscriptOutboxEntryId(userId, entry.bookId, entry.chapterNumber)
  )
}

export function filterManuscriptOutboxEntriesForUser(
  entries: ManuscriptOutboxEntry[],
  userId: string | null,
) {
  if (!userId) return []
  return entries.filter((entry) => manuscriptOutboxEntryBelongsToUser(entry, userId))
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION)
    request.onupgradeneeded = () => {
      let store: IDBObjectStore
      if (!request.result.objectStoreNames.contains(STORE_NAME)) {
        store = request.result.createObjectStore(STORE_NAME, { keyPath: "id" })
      } else {
        store = request.transaction!.objectStore(STORE_NAME)
      }
      if (!store.indexNames.contains(USER_ID_INDEX)) {
        store.createIndex(USER_ID_INDEX, "userId", { unique: false })
      }

      const cursorRequest = store.openCursor()
      cursorRequest.onsuccess = () => {
        const cursor = cursorRequest.result
        if (!cursor) return
        const entry = cursor.value as Partial<ManuscriptOutboxEntry>
        const ownerId = typeof entry.userId === "string" ? entry.userId : ""
        if (!ownerId || !manuscriptOutboxEntryBelongsToUser(entry, ownerId)) {
          cursor.delete()
        }
        cursor.continue()
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

function notifyOutbox() {
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent(MANUSCRIPT_OUTBOX_EVENT))
}

async function transact<T>(mode: IDBTransactionMode, action: (store: IDBObjectStore) => IDBRequest<T>) {
  const database = await openDatabase()
  return new Promise<T>((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, mode)
    const request = action(transaction.objectStore(STORE_NAME))
    let result: T
    let settled = false
    const rejectOnce = (error: DOMException | null) => {
      if (settled) return
      settled = true
      database.close()
      reject(error ?? new DOMException("IndexedDB transaction failed."))
    }
    request.onsuccess = () => { result = request.result }
    request.onerror = () => rejectOnce(request.error)
    transaction.onerror = () => rejectOnce(transaction.error)
    transaction.onabort = () => rejectOnce(transaction.error)
    transaction.oncomplete = () => {
      if (settled) return
      settled = true
      database.close()
      resolve(result)
    }
  })
}

export function isOfflineSaveError(error: unknown) {
  if (typeof navigator !== "undefined" && !navigator.onLine) return true
  return axios.isAxiosError(error) && !error.response
}

export async function enqueueManuscriptSave(
  input: Omit<ManuscriptOutboxEntry, "id" | "userId" | "createdAt" | "attempts" | "status">,
) {
  if (typeof indexedDB === "undefined") return null
  const userId = getActiveUserId()
  if (!userId) return null
  const entry: ManuscriptOutboxEntry = {
    ...input,
    id: buildManuscriptOutboxEntryId(userId, input.bookId, input.chapterNumber),
    userId,
    createdAt: new Date().toISOString(),
    attempts: 0,
    status: "pending",
  }
  await transact("readwrite", (store) => store.put(entry))
  notifyOutbox()
  return entry
}

export async function listManuscriptOutbox(): Promise<ManuscriptOutboxEntry[]> {
  if (typeof indexedDB === "undefined") return []
  const userId = getActiveUserId()
  if (!userId) return []
  return listManuscriptOutboxForUser(userId)
}

async function listManuscriptOutboxForUser(userId: string): Promise<ManuscriptOutboxEntry[]> {
  const items = await transact("readonly", (store) => store.index(USER_ID_INDEX).getAll(userId))
  return filterManuscriptOutboxEntriesForUser(items, userId)
    .sort((left, right) => left.createdAt.localeCompare(right.createdAt))
}

export function isSameQueuedManuscriptSave(
  left: ManuscriptOutboxEntry | undefined,
  right: ManuscriptOutboxEntry,
) {
  return Boolean(
    left
    && left.id === right.id
    && left.userId === right.userId
    && left.createdAt === right.createdAt
    && left.title === right.title
    && left.text === right.text
    && left.html === right.html
    && left.expectedContentVersion === right.expectedContentVersion
  )
}

export function queuedManuscriptSaveMatchesContent(
  entry: ManuscriptOutboxEntry,
  saved: Pick<ManuscriptOutboxEntry, "title" | "text" | "html" | "expectedContentVersion">,
) {
  return entry.title === saved.title
    && entry.text === saved.text
    && entry.html === saved.html
    && entry.expectedContentVersion === saved.expectedContentVersion
}

export function buildQueuedManuscriptConflictOverwrite(
  entry: ManuscriptOutboxEntry,
): ManuscriptOutboxEntry {
  return {
    ...entry,
    expectedContentVersion: undefined,
    attempts: entry.attempts + 1,
    status: "pending",
  }
}

async function replaceEntryIfUnchanged(
  userId: string,
  expected: ManuscriptOutboxEntry,
  replacement: ManuscriptOutboxEntry | null,
) {
  if (!manuscriptOutboxEntryBelongsToUser(expected, userId)) return false
  if (replacement && !manuscriptOutboxEntryBelongsToUser(replacement, userId)) return false
  const database = await openDatabase()
  return new Promise<boolean>((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, "readwrite")
    const store = transaction.objectStore(STORE_NAME)
    const request = store.get(expected.id)
    let changed = false
    let settled = false
    const rejectOnce = (error: DOMException | null) => {
      if (settled) return
      settled = true
      database.close()
      reject(error ?? new DOMException("IndexedDB transaction failed."))
    }
    request.onsuccess = () => {
      const current = request.result as ManuscriptOutboxEntry | undefined
      if (!manuscriptOutboxEntryBelongsToUser(current, userId)) return
      if (!isSameQueuedManuscriptSave(current, expected)) return
      changed = true
      if (replacement) store.put(replacement)
      else store.delete(expected.id)
    }
    request.onerror = () => rejectOnce(request.error)
    transaction.onerror = () => rejectOnce(transaction.error)
    transaction.onabort = () => rejectOnce(transaction.error)
    transaction.oncomplete = () => {
      if (settled) return
      settled = true
      database.close()
      resolve(changed)
    }
  })
}

export async function clearQueuedManuscriptSave(
  bookId: string,
  chapterNumber: number,
  saved: Pick<ManuscriptOutboxEntry, "title" | "text" | "html" | "expectedContentVersion">,
) {
  if (typeof indexedDB === "undefined") return
  const userId = getActiveUserId()
  if (!userId) return
  const entry = await transact<ManuscriptOutboxEntry | undefined>(
    "readonly",
    (store) => store.get(buildManuscriptOutboxEntryId(userId, bookId, chapterNumber)),
  )
  if (!manuscriptOutboxEntryBelongsToUser(entry, userId)) return
  if (!entry || !queuedManuscriptSaveMatchesContent(entry, saved)) return
  if (await replaceEntryIfUnchanged(userId, entry, null)) notifyOutbox()
}

export async function discardQueuedManuscriptSave(entry: ManuscriptOutboxEntry) {
  if (typeof indexedDB === "undefined") return false
  const userId = getActiveUserId()
  if (!userId || !manuscriptOutboxEntryBelongsToUser(entry, userId)) return false
  const removed = await replaceEntryIfUnchanged(userId, entry, null)
  if (removed) notifyOutbox()
  return removed
}

export async function queueManuscriptConflictOverwrite(entry: ManuscriptOutboxEntry) {
  if (typeof indexedDB === "undefined") return false
  const userId = getActiveUserId()
  if (!userId || !manuscriptOutboxEntryBelongsToUser(entry, userId)) return false
  const queued = await replaceEntryIfUnchanged(
    userId,
    entry,
    buildQueuedManuscriptConflictOverwrite(entry),
  )
  if (queued) notifyOutbox()
  return queued
}

async function performManuscriptOutboxSync(userId: string): Promise<ManuscriptSyncResult> {
  if (typeof navigator !== "undefined" && !navigator.onLine) {
    const entries = await listManuscriptOutboxForUser(userId)
    return {
      synced: 0,
      conflicts: entries.filter((entry) => entry.status === "conflict").length,
      pending: entries.length,
    }
  }
  let synced = 0
  const entries = await listManuscriptOutboxForUser(userId)
  for (const entry of entries) {
    if (getActiveUserId() !== userId) break
    if (entry.status === "conflict") continue
    try {
      await booksApi.importManuscript(entry.bookId, {
        text: entry.text,
        html: entry.html,
        title: entry.title,
        chapterNumber: entry.chapterNumber,
        expectedContentVersion: entry.expectedContentVersion,
        replaceExisting: true,
      })
      if (await replaceEntryIfUnchanged(userId, entry, null)) synced += 1
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 409) {
        await replaceEntryIfUnchanged(
          userId,
          entry,
          { ...entry, attempts: entry.attempts + 1, status: "conflict" },
        )
        continue
      }
      await replaceEntryIfUnchanged(
        userId,
        entry,
        { ...entry, attempts: entry.attempts + 1 },
      )
      break
    }
  }
  const remaining = await listManuscriptOutboxForUser(userId)
  notifyOutbox()
  return {
    synced,
    conflicts: remaining.filter((entry) => entry.status === "conflict").length,
    pending: remaining.length,
  }
}

export function syncManuscriptOutbox(): Promise<ManuscriptSyncResult> {
  const userId = getActiveUserId()
  if (!userId || typeof indexedDB === "undefined") {
    return Promise.resolve({ synced: 0, conflicts: 0, pending: 0 })
  }
  const activeSync = activeSyncByUser.get(userId)
  if (activeSync) return activeSync
  const sync = performManuscriptOutboxSync(userId).finally(() => {
    if (activeSyncByUser.get(userId) === sync) activeSyncByUser.delete(userId)
  })
  activeSyncByUser.set(userId, sync)
  return sync
}
