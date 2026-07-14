import { describe, expect, it, vi } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

import { WorldbuildingOpportunitiesCard } from "./WorldbuildingWorkspace.opportunities"
import type { WorldIntegrationResult } from "@/types/world-building"

function opportunity(overrides: Partial<WorldIntegrationResult["integration_opportunities"][number]> = {}): WorldIntegrationResult["integration_opportunities"][number] {
  return {
    id: "opportunity-1",
    element_name: "Moon Gates",
    element_type: "magic_system",
    description: "Use the moon gates to raise stakes in the late-book chase.",
    suggestions: ["Foreshadow the ritual cost.", "Tie the gate to the old city."],
    target_chapter: 8,
    target_chapter_title: "The Chase",
    priority: 7,
    world_document_id: "doc-1",
    world_document_title: "Atlas Notes",
    ...overrides,
  }
}

function integration(opportunities: WorldIntegrationResult["integration_opportunities"]): WorldIntegrationResult {
  return {
    mode: "story_integration",
    generated_at: "2026-06-01T00:00:00Z",
    integration_opportunities: opportunities,
    consistency_flags: [],
    world_elements: [],
    world_documents: [],
    dependency_graph: [],
  }
}

describe("Worldbuilding opportunities card", () => {
  it("renders opportunity cards and show-all controls", () => {
    const item = opportunity()
    const markup = renderToStaticMarkup(
      <WorldbuildingOpportunitiesCard
        isDark={false}
        documentsAvailable
        integration={integration([item, opportunity({ id: "opportunity-2", element_name: "River Oath" })])}
        visibleOpportunities={[item]}
        showAllOpportunities={false}
        loadingIntegration={false}
        noteSavingId={null}
        initialOpportunityCount={1}
        onRunIntegration={vi.fn()}
        onSaveIntegrationAsNote={vi.fn()}
        onToggleShowAllOpportunities={vi.fn()}
      />
    )

    expect(markup).toContain("Underused canon and story opportunities")
    expect(markup).toContain("Moon Gates")
    expect(markup).toContain("Chapter 8")
    expect(markup).toContain("Foreshadow the ritual cost.")
    expect(markup).toContain("Save as note")
    expect(markup).toContain("Show all 2 opportunities")
  })

  it("renders empty and no-scan states", () => {
    const emptyLoadedMarkup = renderToStaticMarkup(
      <WorldbuildingOpportunitiesCard
        isDark
        documentsAvailable
        integration={integration([])}
        visibleOpportunities={[]}
        showAllOpportunities={false}
        loadingIntegration={false}
        noteSavingId={null}
        initialOpportunityCount={4}
        onRunIntegration={vi.fn()}
        onSaveIntegrationAsNote={vi.fn()}
        onToggleShowAllOpportunities={vi.fn()}
      />
    )
    const noScanMarkup = renderToStaticMarkup(
      <WorldbuildingOpportunitiesCard
        isDark={false}
        documentsAvailable={false}
        integration={null}
        visibleOpportunities={[]}
        showAllOpportunities={false}
        loadingIntegration
        noteSavingId={null}
        initialOpportunityCount={4}
        onRunIntegration={vi.fn()}
        onSaveIntegrationAsNote={vi.fn()}
        onToggleShowAllOpportunities={vi.fn()}
      />
    )

    expect(emptyLoadedMarkup).toContain("Opportunity mapping has not run")
    expect(noScanMarkup).toContain("No opportunity scan is loaded yet")
    expect(noScanMarkup).toContain("Mapping...")
  })

  it("renders saving state for the active opportunity", () => {
    const item = opportunity()
    const markup = renderToStaticMarkup(
      <WorldbuildingOpportunitiesCard
        isDark={false}
        documentsAvailable
        integration={integration([item])}
        visibleOpportunities={[item]}
        showAllOpportunities
        loadingIntegration={false}
        noteSavingId={item.id}
        initialOpportunityCount={4}
        onRunIntegration={vi.fn()}
        onSaveIntegrationAsNote={vi.fn()}
        onToggleShowAllOpportunities={vi.fn()}
      />
    )

    expect(markup).toContain("Saving...")
  })
})
