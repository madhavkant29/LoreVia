import { describe, expect, it, vi } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

import { FirstManuscriptHero, MetricStrip, NextActionPanel, SectionHeading } from "./LibraryClient.panels"
import { FolderIcon } from "./LibraryClient.icons"

describe("LibraryClient panels", () => {
  it("renders next actions, metrics, and section headings", () => {
    const nextActionMarkup = renderToStaticMarkup(
      <NextActionPanel
        isDark
        actions={[{ id: "create", label: "Create project", description: "Start now", onSelect: vi.fn() }]}
      />
    )
    const metricsMarkup = renderToStaticMarkup(
      <MetricStrip isDark={false} loading={false} totalProjects={12} activeDrafts={5} processing={2} />
    )
    const headingMarkup = renderToStaticMarkup(
      <SectionHeading isDark={false} icon={<FolderIcon />} title="Pinned" helperText="Your shortcuts" />
    )
    const firstReadMarkup = renderToStaticMarkup(
      <FirstManuscriptHero isDark={false} onUpload={vi.fn()} />
    )

    expect(nextActionMarkup).toContain("Create project")
    expect(nextActionMarkup).toContain("Start now")
    expect(metricsMarkup).toContain("Total projects")
    expect(metricsMarkup).toContain("12")
    expect(headingMarkup).toContain("Pinned")
    expect(headingMarkup).toContain("Your shortcuts")
    expect(firstReadMarkup).toContain("Upload your manuscript for a first read")
    expect(firstReadMarkup).toContain("what is working")
    expect(firstReadMarkup).toContain("evidence-backed revision opportunities")
  })
})
