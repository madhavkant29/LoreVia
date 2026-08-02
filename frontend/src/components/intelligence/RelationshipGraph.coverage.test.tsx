// @vitest-environment jsdom

import { act } from "react"
import { describe, expect, it, vi } from "vitest"

import {
  booksApiMock,
  clickButton,
  container,
  flush,
  graphData,
  graphHandle,
  readerApiMock,
  renderGraph,
  setFieldValue,
  text,
  waitForText,
} from "./relationshipGraph.test-utils"
import { RelationshipGraph } from "./RelationshipGraph"
import { graphLabelKey, graphStorageKey } from "./relationshipGraphDisplay"

describe("RelationshipGraph interactions", () => {

  it("loads relationship data and supports graph filtering, selection, labels, and corrections", async () => {
    const onSelectCharacterId = vi.fn()
    const onGraphDataChange = vi.fn()

    await renderGraph(
      <RelationshipGraph
        bookId="book-1"
        upToChapter={7}
        authorMode
        theme="dark"
        onSelectCharacterId={onSelectCharacterId}
        onGraphDataChange={onGraphDataChange}
      />,
    )
    await flush()
    await waitForText("3 characters")

    expect(readerApiMock.getRelationships).toHaveBeenCalledWith("book-1", 7, {
      includeInactive: false,
      include: "nodes,edges,hidden_nodes",
    })
    expect(text()).toContain("3 characters")
    expect(text()).toContain("2 connections")
    expect(onGraphDataChange).toHaveBeenCalledWith(graphData)

    const filter = container?.querySelector('select[aria-label="Filter relationships"]') as HTMLSelectElement
    await act(async () => {
      setFieldValue(filter, "mentor")
      await Promise.resolve()
    })
    expect(text()).toContain("1 connections")

    await act(async () => {
      graphHandle()?.selectNode("mira")
      await Promise.resolve()
    })
    expect(onSelectCharacterId).toHaveBeenCalledWith("mira")
    expect(text()).toContain("Mira Vale")
    expect(text()).toContain("forced visible")
    expect(text()).toContain("A gate captain with a hidden oath.")

    const labelInput = container?.querySelector("input") as HTMLInputElement
    await act(async () => {
      setFieldValue(labelInput, "Captain Mira")
      await Promise.resolve()
    })
    expect(window.localStorage.getItem(graphLabelKey("book-1"))).toContain("Captain Mira")

    clickButton("Reset to canonical name")
    expect(window.localStorage.getItem(graphLabelKey("book-1"))).not.toContain("Captain Mira")

    clickButton("Center node")
    clickButton("Grid")
    clickButton("Zoom in")
    clickButton("Zoom out")
    clickButton("Reset zoom")
    clickButton("Fit")
    clickButton("Reset layout")
    expect(window.localStorage.getItem(graphStorageKey("book-1", 7))).toBeNull()

    await act(async () => {
      graphHandle()?.selectEdge("rel-1")
      await Promise.resolve()
    })
    expect(text()).toContain("Joren trains Mira in old gate law.")
    expect(text()).toContain("Strongly positive")
    expect(text()).toContain("Author correction")

    const note = Array.from(container?.querySelectorAll("textarea") ?? [])[0]
    await act(async () => {
      setFieldValue(note, "Mira and Joren choose trust.")
      await Promise.resolve()
    })
    await act(async () => {
      clickButton("Save correction")
      await Promise.resolve()
      await Promise.resolve()
    })
    expect(booksApiMock.updateRelationship).toHaveBeenCalledWith("book-1", "rel-1", expect.objectContaining({
      description: "Mira and Joren choose trust.",
      relType: "mentor",
    }))
    expect(onGraphDataChange).toHaveBeenCalledWith(expect.objectContaining({
      edges: expect.arrayContaining([expect.objectContaining({ type: "ally" })]),
    }))

    await act(async () => {
      graphHandle()?.clearSelection()
      await Promise.resolve()
    })
    expect(text()).toContain("Select a character or connection")
  })
})
