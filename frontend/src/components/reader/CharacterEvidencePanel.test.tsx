import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it } from "vitest"

import { CharacterEvidencePanel } from "./CharacterEvidencePanel"

let container: HTMLDivElement | null = null
let root: Root | null = null

describe("CharacterEvidencePanel", () => {
  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

  afterEach(() => {
    act(() => root?.unmount())
    container?.remove()
    container = null
    root = null
  })

  it("renders grounded passage and relationship evidence", () => {
    const view = renderPanel()
    expect(view.textContent).toContain("Chapter 4")
    expect(view.textContent).toContain("A grounded identity clue")
    expect(view.textContent).toContain("Mira to Kael")
    expect(view.textContent).toContain("ally / positive")
  })
})

function renderPanel() {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => {
    root?.render(
      <CharacterEvidencePanel
        characterId="character-1"
        characterName="Mira"
        error={null}
        evidence={[{ chapter_num: 4, chapter_title: "The Ridge", relevance: 0.9, summary: "A grounded identity clue", text: "Mira studies the ridgeline." }]}
        formatRelationshipType={(type) => type || "connection"}
        isDark={false}
        loading={false}
        relationships={[{ counterpartName: "Kael", description: "They move together.", sentiment: 0.8, type: "ally", from_chapter: 2 }]}
        sentimentLabel={() => "positive"}
      />
    )
  })
  return container
}
