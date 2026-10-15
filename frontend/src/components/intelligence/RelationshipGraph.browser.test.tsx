// @vitest-environment jsdom
import { act } from "react"
import { expect, it, vi } from "vitest"
import { RelationshipGraphBrowser } from "./RelationshipGraph.browser"
import { clickButton, container, graphData, renderGraph, setFieldValue, text } from "./relationshipGraph.test-utils"

it("searches full names and relationship types and selects the correct graph element", async () => {
  const onSelect = vi.fn()
  const graph = {
    nodes: graphData.nodes.map(({ id, name, role, first_chapter }) => ({ id, name, role, first_chapter })),
    edges: graphData.edges.map(({ source, target, type, sentiment, description }) => ({ source, target, type, sentiment, description })),
  }
  await renderGraph(<RelationshipGraphBrowser graph={graph} onSelect={onSelect} disabled={false} />)
  clickButton("Mira Vale → Joren Ash")
  expect(onSelect).toHaveBeenCalledWith("edge", "mira-joren-mentor-0")
  const input = container?.querySelector("input") as HTMLInputElement
  await act(async () => { setFieldValue(input, "RIVAL"); await Promise.resolve() })
  expect(text()).toContain("Connections (1)")
  expect(text()).toContain("No characters match.")
  await act(async () => { setFieldValue(input, "missing"); await Promise.resolve() })
  expect(text()).toContain("No connections match.")
})

it("makes entries beyond the initial slice reachable", async () => {
  const nodes = Array.from({ length: 31 }, (_, index) => ({ id: String(index), name: `Character ${index}`, role: null, first_chapter: 1 }))
  await renderGraph(<RelationshipGraphBrowser graph={{ nodes, edges: [] }} onSelect={vi.fn()} disabled={false} />)
  expect(text()).not.toContain("Character 30")
  clickButton("Show more entries")
  expect(text()).toContain("Character 30")
})
