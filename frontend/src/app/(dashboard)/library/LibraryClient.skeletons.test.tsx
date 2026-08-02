import { describe, expect, it } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

import { ProjectSkeletons } from "./LibraryClient.skeletons"

describe("LibraryClient skeletons", () => {
  it("renders status regions for grid and list loading states", () => {
    const gridMarkup = renderToStaticMarkup(
      <ProjectSkeletons isDark viewMode="grid" label="Loading grid projects" />
    )
    const listMarkup = renderToStaticMarkup(
      <ProjectSkeletons isDark={false} viewMode="list" label="Loading list projects" />
    )

    expect(gridMarkup).toContain("Loading grid projects")
    expect(gridMarkup).toContain("xl:grid-cols-3")
    expect(listMarkup).toContain("Loading list projects")
    expect(listMarkup).toContain("space-y-3")
  })
})
