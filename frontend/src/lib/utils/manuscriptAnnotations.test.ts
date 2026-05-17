import { describe, expect, it } from "vitest"

import { cleanAnnotationText, resolveAnnotationRange } from "./manuscriptAnnotations"

describe("manuscript annotation utilities", () => {
  it("normalizes annotation text safely", () => {
    expect(cleanAnnotationText("  Nora   crossed \n the gate ")).toBe("Nora crossed the gate")
  })

  it("resolves ranges from exact offsets when the manuscript has not moved", () => {
    document.body.innerHTML = "<div id='editor'>Nora crossed the ember gate before dawn.</div>"
    const editor = document.getElementById("editor") as HTMLElement

    const range = resolveAnnotationRange(editor, {
      quote: "crossed the ember gate",
      anchor_context_before: "Nora",
      anchor_context_after: "before dawn",
      start_offset: 5,
      end_offset: 27,
    })

    expect(range?.toString()).toBe("crossed the ember gate")
  })

  it("falls back to context matching when offsets drift", () => {
    document.body.innerHTML = "<div id='editor'>The guard hesitated. Nora crossed the ember gate before dawn. Later, Nora crossed the ember gate again.</div>"
    const editor = document.getElementById("editor") as HTMLElement

    const range = resolveAnnotationRange(editor, {
      quote: "Nora crossed the ember gate",
      anchor_context_before: "guard hesitated",
      anchor_context_after: "before dawn",
      start_offset: 0,
      end_offset: 0,
    })

    expect(range?.toString()).toBe("Nora crossed the ember gate")
  })
})
