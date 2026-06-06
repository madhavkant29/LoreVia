import { describe, it, expect, beforeEach, vi } from "vitest"
import { migrateVaultStorage } from "./vaultStorageMigration"

const OLD_FAVORITES = "obsidian-note-favorites:v1"
const OLD_FOLDERS = (bookId: string) => `obsidian-note-folders:v1:${bookId}`
const NEW_FAVORITES = "vault-note-favorites:v1"
const NEW_FOLDERS = (bookId: string) => `vault-note-folders:v1:${bookId}`
const MIGRATION_DONE = "vault-storage-migrated:v1"

const store: Record<string, string> = {}

const storageApi = {
  getItem: (key: string) => store[key] ?? null,
  setItem: (key: string, value: string) => {
    store[key] = value
  },
  removeItem: (key: string) => {
    delete store[key]
  },
  clear: () => {
    Object.keys(store).forEach((key) => delete store[key])
  },
  get length() {
    return Object.keys(store).length
  },
  key: (index: number) => Object.keys(store)[index] ?? null,
}

vi.stubGlobal("localStorage", storageApi)

beforeEach(() => {
  storageApi.clear()
})

describe("migrateVaultStorage", () => {
  it("migrates favorites from old key to new key", () => {
    localStorage.setItem(OLD_FAVORITES, JSON.stringify({ foo: true }))
    migrateVaultStorage("book-1")

    expect(localStorage.getItem(NEW_FAVORITES)).toBe(JSON.stringify({ foo: true }))
    expect(localStorage.getItem(OLD_FAVORITES)).toBeNull()
    expect(localStorage.getItem(MIGRATION_DONE)).toBe("true")
  })

  it("migrates book folder preferences from old key to new key", () => {
    localStorage.setItem(OLD_FOLDERS("book-1"), JSON.stringify(["folder-a", "folder-b"]))
    migrateVaultStorage("book-1")

    expect(localStorage.getItem(NEW_FOLDERS("book-1"))).toBe(JSON.stringify(["folder-a", "folder-b"]))
    expect(localStorage.getItem(OLD_FOLDERS("book-1"))).toBeNull()
  })

  it("does not overwrite new favorites if they already exist", () => {
    localStorage.setItem(OLD_FAVORITES, JSON.stringify({ old: true }))
    localStorage.setItem(NEW_FAVORITES, JSON.stringify({ new: true }))
    migrateVaultStorage("book-1")

    expect(localStorage.getItem(NEW_FAVORITES)).toBe(JSON.stringify({ new: true }))
    expect(localStorage.getItem(OLD_FAVORITES)).toBeNull()
  })

  it("does not overwrite new folder prefs if they already exist", () => {
    localStorage.setItem(OLD_FOLDERS("book-1"), JSON.stringify(["old-folder"]))
    localStorage.setItem(NEW_FOLDERS("book-1"), JSON.stringify(["new-folder"]))
    migrateVaultStorage("book-1")

    expect(localStorage.getItem(NEW_FOLDERS("book-1"))).toBe(JSON.stringify(["new-folder"]))
    expect(localStorage.getItem(OLD_FOLDERS("book-1"))).toBeNull()
  })

  it("cleans up old keys after migration", () => {
    localStorage.setItem(OLD_FAVORITES, "data")
    localStorage.setItem(OLD_FOLDERS("book-1"), "folders")
    migrateVaultStorage("book-1")

    expect(localStorage.getItem(OLD_FAVORITES)).toBeNull()
    expect(localStorage.getItem(OLD_FOLDERS("book-1"))).toBeNull()
  })

  it("is idempotent — running twice does not cause errors", () => {
    localStorage.setItem(OLD_FAVORITES, JSON.stringify({ a: 1 }))
    migrateVaultStorage("book-1")

    const afterFirst = { ...store }

    migrateVaultStorage("book-1")
    const afterSecond = { ...store }

    expect(afterSecond).toEqual(afterFirst)
  })

  it("skips favorites migration if already done on a previous book mount", () => {
    localStorage.setItem(OLD_FAVORITES, JSON.stringify({ shared: true }))
    migrateVaultStorage("book-1")

    localStorage.setItem(OLD_FAVORITES, JSON.stringify({ stale: true }))
    migrateVaultStorage("book-2")

    expect(localStorage.getItem(NEW_FAVORITES)).toBe(JSON.stringify({ shared: true }))
  })

  it("migrates folder prefs independently per book", () => {
    localStorage.setItem(OLD_FOLDERS("book-1"), JSON.stringify(["a"]))
    localStorage.setItem(OLD_FOLDERS("book-2"), JSON.stringify(["b"]))
    migrateVaultStorage("book-1")

    expect(localStorage.getItem(NEW_FOLDERS("book-1"))).toBe(JSON.stringify(["a"]))
    expect(localStorage.getItem(OLD_FOLDERS("book-1"))).toBeNull()

    expect(localStorage.getItem(OLD_FOLDERS("book-2"))).toBe(JSON.stringify(["b"]))

    migrateVaultStorage("book-2")
    expect(localStorage.getItem(NEW_FOLDERS("book-2"))).toBe(JSON.stringify(["b"]))
    expect(localStorage.getItem(OLD_FOLDERS("book-2"))).toBeNull()
  })

  it("is a no-op when no old keys exist", () => {
    const before = { ...store }
    migrateVaultStorage("book-1")
    const after = { ...store }

    expect(after[MIGRATION_DONE]).toBe("true")
    delete after[MIGRATION_DONE]
    delete before[MIGRATION_DONE]

    expect(after).toEqual(before)
  })
})
