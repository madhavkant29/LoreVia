import { describe, expect, it } from "vitest"

import {
  buildSceneChapterOptions,
  extractChapterNumberFromSceneFolder,
  findWorkspaceStructurePath,
  moveSceneIdToIndex,
  parseStoredSceneFolders,
  reorderSceneIds,
  reorderWorkspaceSceneTree,
} from "./sceneWorkspace"

describe("scene workspace utilities", () => {
  it("extracts chapter numbers from nested scene folders", () => {
    expect(extractChapterNumberFromSceneFolder("scenes/chapter-05")).toBe(5)
    expect(extractChapterNumberFromSceneFolder("scenes/act-1/chapter_12/intro")).toBe(12)
    expect(extractChapterNumberFromSceneFolder("scenes/misc")).toBeNull()
  })

  it("builds chapter options from both manuscript chapters and custom folders", () => {
    const options = buildSceneChapterOptions(
      [
        { chapter_number: 1, scene_count: 2, structure_version: 1 },
        { chapter_number: 3, scene_count: 4, structure_version: 1 },
      ],
      [
        "scenes/chapter-02",
        "scenes/custom",
        "scenes/act-2/chapter-05",
      ]
    )

    expect(options).toEqual([1, 2, 3, 5])
  })

  it("parses stored scene folders into normalized paths", () => {
    expect(parseStoredSceneFolders('[" scenes\\\\chapter-01 ","","/scenes/custom/"]')).toEqual([
      "scenes/chapter-01",
      "scenes/custom",
    ])
  })

  it("returns an empty list for invalid stored scene folders", () => {
    expect(parseStoredSceneFolders("{bad json")).toEqual([])
    expect(parseStoredSceneFolders('{"folder":"scenes"}')).toEqual([])
  })

  it("finds the current scene path from the workspace structure by scene id", () => {
    const path = findWorkspaceStructurePath(
      [
        {
          id: "book-1",
          label: "Book",
          kind: "book",
          children: [
            {
              id: "chapter-1",
              label: "Chapter 1",
              kind: "chapter",
              chapter_number: 1,
              children: [
                {
                  id: "scene-1",
                  label: "Opening",
                  kind: "scene",
                  chapter_number: 1,
                  scene_id: "scene-1",
                  children: [],
                },
              ],
            },
          ],
        },
      ],
      "scene-1",
      "Draft title"
    )

    expect(path.map((node) => node.label)).toEqual(["Book", "Chapter 1", "Opening"])
  })

  it("finds an unsaved scene path by title when no scene id is selected", () => {
    const path = findWorkspaceStructurePath(
      [
        {
          id: "book-1",
          label: "Book",
          kind: "book",
          children: [
            {
              id: "scene-draft",
              label: "Untitled scene",
              kind: "scene",
              children: [],
            },
          ],
        },
      ],
      null,
      "Untitled scene"
    )

    expect(path.map((node) => node.id)).toEqual(["book-1", "scene-draft"])
  })

  it("returns an empty structure path when the scene is not in the hierarchy", () => {
    expect(findWorkspaceStructurePath([], "missing-scene", "Missing")).toEqual([])
  })

  it("reorders scene ids within a chapter sequence", () => {
    expect(reorderSceneIds(["scene-1", "scene-2", "scene-3"], "scene-3", "scene-2")).toEqual([
      "scene-1",
      "scene-3",
      "scene-2",
    ])
    expect(reorderSceneIds(["scene-1", "scene-2", "scene-3"], "scene-1", "scene-3")).toEqual([
      "scene-2",
      "scene-1",
      "scene-3",
    ])
    expect(reorderSceneIds(["scene-1", "scene-2", "scene-3"], "scene-1", "scene-2", "after")).toEqual([
      "scene-2",
      "scene-1",
      "scene-3",
    ])
  })

  it("keeps the original order when a drag target is invalid", () => {
    const sceneIds = ["scene-1", "scene-2"]

    expect(reorderSceneIds(sceneIds, "scene-1", "missing-scene")).toBe(sceneIds)
    expect(reorderSceneIds(sceneIds, "scene-1", "scene-1")).toBe(sceneIds)
  })

  it("moves a scene to an explicit insertion index", () => {
    expect(moveSceneIdToIndex(["scene-1", "scene-2", "scene-3"], "scene-3", 1)).toEqual([
      "scene-1",
      "scene-3",
      "scene-2",
    ])
    expect(moveSceneIdToIndex(["scene-1", "scene-2", "scene-3"], "scene-1", 3)).toEqual([
      "scene-2",
      "scene-3",
      "scene-1",
    ])
  })

  it("keeps the original order when moving to the current insertion slot", () => {
    const sceneIds = ["scene-1", "scene-2", "scene-3"]

    expect(moveSceneIdToIndex(sceneIds, "scene-2", 1)).toBe(sceneIds)
    expect(moveSceneIdToIndex(sceneIds, "scene-2", 2)).toBe(sceneIds)
    expect(moveSceneIdToIndex(sceneIds, "missing-scene", 0)).toBe(sceneIds)
  })

  it("reorders scenes inside the manuscript workspace tree", () => {
    const reordered = reorderWorkspaceSceneTree(
      {
        chapters: [{ chapter_number: 4, title: "Chapter 4", scene_count: 2, structure_version: 2 }],
        note_paths: [],
        scene_groups: [
          {
            id: "chapter-4",
            label: "Chapter 4",
            chapter_number: 4,
            structure_version: 2,
            collapsed_by_default: false,
            scenes: [
              {
                id: "scene-1",
                book_id: "book-1",
                title: "Opening",
                body: "First scene",
                path: "chapter-4/opening",
                status: "assigned",
                sort_order: 1,
                source: "manual",
                created_at: "2026-05-14T00:00:00Z",
                updated_at: "2026-05-14T00:00:00Z",
              },
              {
                id: "scene-2",
                book_id: "book-1",
                title: "Closing",
                body: "Second scene",
                path: "chapter-4/closing",
                status: "assigned",
                sort_order: 2,
                source: "manual",
                created_at: "2026-05-14T00:00:00Z",
                updated_at: "2026-05-14T00:00:00Z",
              },
            ],
          },
        ],
      },
      4,
      ["scene-2", "scene-1"],
      3
    )

    expect(reordered.scene_groups[0]?.structure_version).toBe(3)
    expect(reordered.scene_groups[0]?.scenes.map((scene) => scene.id)).toEqual(["scene-2", "scene-1"])
    expect(reordered.scene_groups[0]?.scenes.map((scene) => scene.sort_order)).toEqual([1, 2])
  })
})
