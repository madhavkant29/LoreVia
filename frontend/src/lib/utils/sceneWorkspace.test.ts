import { describe, expect, it } from "vitest"

import { buildSceneChapterOptions, extractChapterNumberFromSceneFolder } from "./sceneWorkspace"

describe("scene workspace utilities", () => {
  it("extracts chapter numbers from nested scene folders", () => {
    expect(extractChapterNumberFromSceneFolder("scenes/chapter-05")).toBe(5)
    expect(extractChapterNumberFromSceneFolder("scenes/act-1/chapter_12/intro")).toBe(12)
    expect(extractChapterNumberFromSceneFolder("scenes/misc")).toBeNull()
  })

  it("builds chapter options from both manuscript chapters and custom folders", () => {
    const options = buildSceneChapterOptions(
      [
        { chapter_number: 1, scene_count: 2 },
        { chapter_number: 3, scene_count: 4 },
      ],
      [
        "scenes/chapter-02",
        "scenes/custom",
        "scenes/act-2/chapter-05",
      ]
    )

    expect(options).toEqual([1, 2, 3, 5])
  })
})
