import { describe, expect, it, vi } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

import { CanonOverrideCard } from "./WorldbuildingWorkspace.canon"
import type { CanonOverride } from "@/types/world-building"

function override(overrides: Partial<CanonOverride> = {}): CanonOverride {
  return {
    id: "canon-1",
    canonical_name: "Aurelian Empire",
    aliases: ["The Empire", "Aurel"],
    entity_type: "faction",
    notes: null,
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-02T00:00:00Z",
    ...overrides,
  }
}

describe("Worldbuilding canon override card", () => {
  it("renders inputs, refresh, save, and existing aliases", () => {
    const markup = renderToStaticMarkup(
      <CanonOverrideCard
        isDark={false}
        canonName="Aurelian Empire"
        canonAliases="The Empire, Aurel"
        canonOverrides={[override()]}
        savingCanon={false}
        onCanonNameChange={vi.fn()}
        onCanonAliasesChange={vi.fn()}
        onSaveCanonOverride={vi.fn()}
        onRefreshCanonOverrides={vi.fn()}
      />
    )

    expect(markup).toContain("Canon Overrides / Aliases")
    expect(markup).toContain("Canonical name")
    expect(markup).toContain("Aliases")
    expect(markup).toContain("Refresh")
    expect(markup).toContain("Save override")
    expect(markup).toContain("Aurelian Empire: The Empire, Aurel")
  })

  it("renders empty and saving states", () => {
    const markup = renderToStaticMarkup(
      <CanonOverrideCard
        isDark
        canonName="Aurelian Empire"
        canonAliases=""
        canonOverrides={[]}
        savingCanon
        onCanonNameChange={vi.fn()}
        onCanonAliasesChange={vi.fn()}
        onSaveCanonOverride={vi.fn()}
        onRefreshCanonOverrides={vi.fn()}
      />
    )

    expect(markup).toContain("Saving...")
    expect(markup).toContain("No alias overrides yet.")
  })
})
