import { describe, expect, it, vi } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

import { LibraryAuthLoadingState, LibraryErrorState } from "./LibraryClient.states"

describe("LibraryClient states", () => {
  it("renders auth loading skeletons and load errors", () => {
    const loadingMarkup = renderToStaticMarkup(
      <LibraryAuthLoadingState isDark={false} pageBackground="page" />
    )
    const errorMarkup = renderToStaticMarkup(
      <LibraryErrorState isDark pageBackground="page" onRetry={vi.fn()} />
    )

    expect(loadingMarkup).toContain("min-h-screen")
    expect(loadingMarkup).toContain("xl:grid-cols-3")
    expect(errorMarkup).toContain("Failed to load library")
    expect(errorMarkup).toContain("Something went wrong while loading your library")
  })
})
