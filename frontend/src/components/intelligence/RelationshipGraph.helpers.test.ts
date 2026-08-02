import { describe, expect, it } from "vitest"

import {
  BASE_LAYOUT,
  buildIsolatedPositions,
  controlButtonClass,
  panelClass,
} from "./RelationshipGraph.helpers"
import type { RelationshipGraph as GraphData } from "@/types/character"

type GraphNode = GraphData["nodes"][number]

function node(id: string): GraphNode {
  return {
    id,
    name: id,
    role: null,
    first_chapter: 1,
  } as unknown as GraphNode
}

describe("RelationshipGraph helpers", () => {
  it("defines the shared force layout constants", () => {
    expect(BASE_LAYOUT.name).toBe("cose")
    expect((BASE_LAYOUT as { padding?: number }).padding).toBe(56)
    expect(typeof (BASE_LAYOUT as { nodeRepulsion?: unknown }).nodeRepulsion).toBe("function")
  })

  it("builds stable positions for isolated node layouts", () => {
    expect(buildIsolatedPositions([])).toBeNull()
    expect(buildIsolatedPositions([node("mira")])).toEqual({ mira: { x: 420, y: 280 } })

    const positions = buildIsolatedPositions([node("mira"), node("jon"), node("sefa")])
    expect(Object.keys(positions ?? {})).toEqual(["mira", "jon", "sefa"])
    expect(positions?.mira.x).toBeCloseTo(420)
    expect(positions?.mira.y).toBeLessThan(290)
    expect(positions?.jon.x).not.toBe(positions?.sefa.x)
  })

  it("returns stable graph chrome class names", () => {
    expect(controlButtonClass()).toContain("border-white/10")
    expect(controlButtonClass(true)).toContain("border-violet")
    expect(panelClass()).toContain("shadow-[0_24px_80px")
  })
})
