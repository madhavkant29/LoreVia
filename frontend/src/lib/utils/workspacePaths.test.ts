import { describe, expect, it } from "vitest"

import {
  buildUniqueWorkspacePath,
  buildUniqueWorkspacePathFromCandidate,
  buildWorkspaceFolderTree,
  normalizeWorkspaceFolderPath,
  workspaceFolderName,
} from "./workspacePaths"

describe("workspace path utilities", () => {
  it("normalizes folder paths and resolves display names", () => {
    expect(normalizeWorkspaceFolderPath("\\Series\\ Drafts\\")).toBe("Series/ Drafts")
    expect(workspaceFolderName("Series/Book One/Notes")).toBe("Notes")
  })

  it("builds a folder tree with seeded folders and item counts", () => {
    const tree = buildWorkspaceFolderTree(
      ["Series/Book One/Outline.md", "Series/Book One/Scene 1.md", "Series/Book Two/Notes.md"],
      ["Series/Archive"]
    )

    const series = tree.folders.get("Series")
    const bookOne = series?.folders.get("Book One")
    const archive = series?.folders.get("Archive")

    expect(series?.itemCount).toBe(3)
    expect(bookOne?.itemCount).toBe(2)
    expect(archive?.itemCount).toBe(0)
  })

  it("creates unique workspace paths from existing paths and candidate filenames", () => {
    const existing = ["Scenes/Act1.md", "Scenes/Act1 2.md", "Scenes/Act 1.md", "Scenes/Act 1 2.md"]

    expect(buildUniqueWorkspacePath(existing, "Scenes", "Act:1")).toBe("Scenes/Act1 3.md")
    expect(buildUniqueWorkspacePathFromCandidate(existing, "\\Scenes\\Act 1.md")).toBe("Scenes/Act 1 3.md")
  })
})
