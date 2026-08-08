import { existsSync } from "node:fs"
import { join } from "node:path"
import { describe, expect, it } from "vitest"

import { toolsForPlacement, workspaceToolRegistry } from "./toolRegistry"

function pageCandidates(route: string) {
  const routePath = route
    .replace(/^\//, "")
    .replace(":bookId", "[bookId]")
    .replace(":chapter", "[chapterId]")
  return [
    join(process.cwd(), "src", "app", routePath, "page.tsx"),
    join(process.cwd(), "src", "app", "(dashboard)", routePath, "page.tsx"),
    join(process.cwd(), "src", "app", "(reader)", routePath, "page.tsx"),
  ]
}

describe("workspaceToolRegistry", () => {
  it("uses stable unique ids and valid routes", () => {
    const ids = workspaceToolRegistry.map((tool) => tool.id)
    expect(new Set(ids).size).toBe(ids.length)

    for (const tool of workspaceToolRegistry) {
      expect(tool.id).toMatch(/^(dashboard|book)\.[a-z0-9_]+$/)
      expect(tool.keywords.length).toBeGreaterThan(0)
      expect(pageCandidates(tool.route).some(existsSync), `${tool.id} route ${tool.route}`).toBe(true)
    }
  })

  it("keeps recovery anchors non-hideable and all tools command-searchable", () => {
    for (const id of ["dashboard.library", "dashboard.settings", "book.overview", "book.read", "book.chapters"]) {
      expect(workspaceToolRegistry.find((tool) => tool.id === id)?.nonHideable).toBe(true)
    }
    expect(toolsForPlacement("command")).toHaveLength(workspaceToolRegistry.length)
  })
})
