const OLD_FAVORITES_KEY = "obsidian-note-favorites:v1"
const OLD_FOLDERS_PREFIX = "obsidian-note-folders:v1:"
const NEW_FAVORITES_KEY = "vault-note-favorites:v1"
const NEW_FOLDERS_PREFIX = "vault-note-folders:v1:"
const MIGRATION_DONE_KEY = "vault-storage-migrated:v1"

export function migrateVaultStorage(bookId: string): void {
  if (typeof window === "undefined") return

  if (localStorage.getItem(MIGRATION_DONE_KEY) !== "true") {
    const oldFavorites = localStorage.getItem(OLD_FAVORITES_KEY)
    if (oldFavorites !== null && localStorage.getItem(NEW_FAVORITES_KEY) === null) {
      localStorage.setItem(NEW_FAVORITES_KEY, oldFavorites)
    }
    localStorage.removeItem(OLD_FAVORITES_KEY)
    localStorage.setItem(MIGRATION_DONE_KEY, "true")
  }

  const oldFoldersKey = `${OLD_FOLDERS_PREFIX}${bookId}`
  const oldFolders = localStorage.getItem(oldFoldersKey)
  if (oldFolders !== null) {
    const newFoldersKey = `${NEW_FOLDERS_PREFIX}${bookId}`
    if (localStorage.getItem(newFoldersKey) === null) {
      localStorage.setItem(newFoldersKey, oldFolders)
    }
    localStorage.removeItem(oldFoldersKey)
  }
}
