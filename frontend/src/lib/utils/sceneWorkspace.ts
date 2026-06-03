import type { ManuscriptWorkspaceTree, WorkspaceChapterNode } from "@/types/book"
import { normalizeWorkspaceFolderPath } from "./workspacePaths"

const CHAPTER_FOLDER_PATTERN = /(?:^|\/)chapter[-_\s]?(\d+)(?:\/|$)/i
export const SCENE_FOLDER_STORAGE_KEY_PREFIX = "scene-workspace-folders:v1:"
export type SceneDropPlacement = "before" | "after"

export function extractChapterNumberFromSceneFolder(path: string | null | undefined) {
  if (!path) return null
  const normalizedPath = path.replace(/\\/g, "/").trim()
  const match = normalizedPath.match(CHAPTER_FOLDER_PATTERN)
  if (!match) return null

  const chapterNumber = Number.parseInt(match[1] ?? "", 10)
  return Number.isFinite(chapterNumber) && chapterNumber > 0 ? chapterNumber : null
}

export function buildSceneChapterOptions(chapters: WorkspaceChapterNode[], folderPaths: string[]) {
  const chapterNumbers = new Set<number>()

  for (const chapter of chapters) {
    if (chapter.chapter_number > 0) chapterNumbers.add(chapter.chapter_number)
  }

  for (const folderPath of folderPaths) {
    const chapterNumber = extractChapterNumberFromSceneFolder(folderPath)
    if (chapterNumber) chapterNumbers.add(chapterNumber)
  }

  return [...chapterNumbers].sort((left, right) => left - right)
}

export function moveSceneIdToIndex(sceneIds: string[], sourceId: string, destinationIndex: number) {
  const sourceIndex = sceneIds.indexOf(sourceId)
  if (sourceIndex === -1) return sceneIds

  const normalizedDestinationIndex = Math.max(0, Math.min(destinationIndex, sceneIds.length))
  if (sourceIndex === normalizedDestinationIndex || sourceIndex + 1 === normalizedDestinationIndex) {
    return sceneIds
  }

  const nextSceneIds = [...sceneIds]
  const [movedSceneId] = nextSceneIds.splice(sourceIndex, 1)
  const adjustedDestinationIndex = sourceIndex < normalizedDestinationIndex
    ? normalizedDestinationIndex - 1
    : normalizedDestinationIndex

  nextSceneIds.splice(adjustedDestinationIndex, 0, movedSceneId)
  return nextSceneIds
}

export function reorderSceneIds(
  sceneIds: string[],
  sourceId: string,
  targetId: string,
  placement: SceneDropPlacement = "before"
) {
  const sourceIndex = sceneIds.indexOf(sourceId)
  const targetIndex = sceneIds.indexOf(targetId)

  if (sourceIndex === -1 || targetIndex === -1 || sourceIndex === targetIndex) {
    return sceneIds
  }

  return moveSceneIdToIndex(sceneIds, sourceId, placement === "before" ? targetIndex : targetIndex + 1)
}

export function reorderWorkspaceSceneTree(
  tree: ManuscriptWorkspaceTree,
  chapterNumber: number,
  sceneIds: string[],
  structureVersion?: number
) {
  const orderedSceneIds = new Set(sceneIds)

  return {
    ...tree,
    chapters: tree.chapters.map((chapter) =>
      chapter.chapter_number === chapterNumber
        ? { ...chapter, structure_version: structureVersion ?? chapter.structure_version }
        : chapter
    ),
    scene_groups: tree.scene_groups.map((group) => {
      if (group.chapter_number !== chapterNumber) return group

      const scenesById = new Map(group.scenes.map((scene) => [scene.id, scene]))
      const reorderedScenes = sceneIds
        .map((sceneId) => scenesById.get(sceneId))
        .filter((scene): scene is NonNullable<typeof scene> => scene !== null)
      const trailingScenes = group.scenes.filter((scene) => !orderedSceneIds.has(scene.id))
      const orderedScenes = [...reorderedScenes, ...trailingScenes].map((scene, index) => ({
        ...scene,
        sort_order: index + 1,
      }))

      return {
        ...group,
        structure_version: structureVersion ?? group.structure_version ?? null,
        scenes: orderedScenes,
      }
    }),
  }
}

export function parseStoredSceneFolders(raw: string | null | undefined) {
  try {
    const parsed = raw && typeof raw === "string" ? JSON.parse(raw) : []
    if (!Array.isArray(parsed)) return []

    return parsed.map((value) => normalizeWorkspaceFolderPath(String(value))).filter(Boolean)
  } catch {
    return []
  }
}
