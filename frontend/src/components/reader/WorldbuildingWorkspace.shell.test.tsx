import { describe, expect, it } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

import { DocumentBodyLoadingState, WorldbuildingMetricsStrip, WorldbuildingStatusMessage } from "./WorldbuildingWorkspace.shell"

describe("Worldbuilding workspace shell presentation", () => {
  it("renders metrics and status messages", () => {
    const metricsMarkup = renderToStaticMarkup(
      <WorldbuildingMetricsStrip
        isDark={false}
        documentCount={3}
        totalWorldWords={12345}
        extractedElementCount={8}
        openNoteCount={2}
      />
    )
    const statusMarkup = renderToStaticMarkup(
      <WorldbuildingStatusMessage isDark message="Saved Atlas Notes." />
    )

    expect(metricsMarkup).toContain("Canon sources")
    expect(metricsMarkup).toContain("12,345")
    expect(metricsMarkup).toContain("Lore facts")
    expect(metricsMarkup).toContain("Open cleanup")
    expect(statusMarkup).toContain("Saved Atlas Notes.")
  })

  it("renders document-body loading state and omits empty status messages", () => {
    const loadingMarkup = renderToStaticMarkup(<DocumentBodyLoadingState isDark={false} />)
    const emptyStatusMarkup = renderToStaticMarkup(<WorldbuildingStatusMessage isDark={false} message={null} />)

    expect(loadingMarkup).toContain("Loading document content")
    expect(loadingMarkup).toContain("aria-busy")
    expect(emptyStatusMarkup).toBe("")
  })
})
