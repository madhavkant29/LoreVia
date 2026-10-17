import type { DragEvent as ReactDragEvent } from "react"

import {
  parseStoredSceneFolders,
  SCENE_FOLDER_STORAGE_KEY_PREFIX,
} from "@/lib/utils/sceneWorkspace"
import {
  normalizeWorkspaceFolderPath,
  sanitizeWorkspaceTitle,
  workspaceFolderFromPath,
} from "@/lib/utils/workspacePaths"
import type { SceneMetadata } from "@/types/book"

type SceneDragItem = { kind: "scene"; id: string }

export function sceneFolder(path: string) {
  return workspaceFolderFromPath(path)
}

function sceneSlug(value: string) {
  return sanitizeWorkspaceTitle(value, "untitled-scene").toLowerCase().replace(/\s+/g, "-")
}

export function buildScenePath(folderPath: string | null, title: string) {
  const normalizedFolder = normalizeWorkspaceFolderPath(folderPath)
  const filename = `${sceneSlug(title)}.md`
  return normalizedFolder ? `${normalizedFolder}/${filename}` : filename
}

export function defaultSceneFolder(chapterNumber: number | null) {
  if (typeof chapterNumber === "number" && chapterNumber > 0) {
    return `scenes/chapter-${String(chapterNumber).padStart(2, "0")}`
  }
  return "scenes/unassigned"
}

export function loadSceneFolders(bookId: string) {
  if (typeof window === "undefined") return [] as string[]
  return parseStoredSceneFolders(window.localStorage.getItem(`${SCENE_FOLDER_STORAGE_KEY_PREFIX}${bookId}`))
}

export function saveSceneFolders(bookId: string, folders: string[]) {
  if (typeof window === "undefined") return
  const normalizedFolders = [...new Set(folders.map(normalizeWorkspaceFolderPath).filter(Boolean))].sort()
  window.localStorage.setItem(`${SCENE_FOLDER_STORAGE_KEY_PREFIX}${bookId}`, JSON.stringify(normalizedFolders))
}

export function parseSceneDragItem(event: Pick<DragEvent, "dataTransfer"> | Pick<ReactDragEvent, "dataTransfer">) {
  const raw = event.dataTransfer?.getData("application/lorevia-scene-item")
  if (!raw) return null
  try {
    const value = JSON.parse(raw) as SceneDragItem
    return value.kind === "scene" && value.id ? value : null
  } catch {
    return null
  }
}

export function emptySceneMetadata(): SceneMetadata {
  return {
    pov: null,
    timeline: null,
    location: null,
    tags: [],
    mood: [],
    status_note: null,
    anchors: [],
    bookmarks: [],
  }
}

export function metadataTextToList(value: string, preserveTrailingEntry = false) {
  const values = value
    .split(",")
    .map((item) => item.trim())
  return preserveTrailingEntry ? values : values.filter(Boolean)
}

export function normalizeSceneMetadata(metadata: SceneMetadata): SceneMetadata {
  return { ...metadata, tags: metadataTextToList((metadata.tags ?? []).join(",")), mood: metadataTextToList((metadata.mood ?? []).join(",")) }
}
