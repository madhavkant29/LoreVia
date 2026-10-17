import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { SectionMeta } from "@/types/book"

import { ImportStructureEditor } from "./ImportStructureEditor"

const sections: SectionMeta[] = [
  { id: "first", type: "chapter", title: "Chapter 1", number: 1, start_page: 1, end_page: 2, confidence: 1, include_in_analysis: true, start_block: 0, end_block: 2, word_count: 20, source_location: "page 1" },
  { id: "second", type: "chapter", title: "Chapter 2", number: 2, start_page: 3, end_page: 4, confidence: 1, include_in_analysis: true, start_block: 2, end_block: 4, word_count: 20, source_location: "page 3" },
]

let container: HTMLDivElement
let root: Root

afterEach(() => {
  act(() => root?.unmount())
  container?.remove()
})

describe("ImportStructureEditor", () => {
  it("moves an adjacent boundary without deleting or reordering a source block", () => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    container = document.createElement("div")
    root = createRoot(container)
    const onSave = vi.fn()
    act(() => root.render(<ImportStructureEditor sections={sections} blockWordCounts={[4, 6, 8, 10]} blockOpenings={["first", "second", "third", "fourth"]} blockClosings={["first end", "second end", "third end", "fourth end"]} blockLocations={["page 1", "page 2", "page 3", "page 4"]} onSave={onSave} onCancel={() => {}} />))

    expect(container.textContent).not.toContain("Delete")
    const move = Array.from(container.querySelectorAll("button")).find((button) => button.textContent?.includes("Move next block into this section"))
    expect(move).toBeTruthy()
    act(() => move?.click())
    const save = Array.from(container.querySelectorAll("button")).find((button) => button.textContent === "Save changes")
    act(() => save?.click())

    const accepted = onSave.mock.calls[0][0] as SectionMeta[]
    expect(accepted.map((section) => [section.id, section.start_block, section.end_block])).toEqual([
      ["first", 0, 3], ["second", 3, 4],
    ])
    expect(accepted.map((section) => section.word_count)).toEqual([18, 10])
    expect(accepted[0].closing_excerpt).toBe("third end")
    expect(accepted[1].opening_excerpt).toBe("fourth")
  })
})
