// @vitest-environment jsdom

import { act } from "react"
import { describe, expect, it } from "vitest"

import {
  booksApiMock,
  cleanupRelationshipGraphRender,
  clickButton,
  flush,
  graphData,
  graphHandle,
  readerApiMock,
  renderGraph,
  text,
  waitForText,
} from "./relationshipGraph.test-utils"
import { RelationshipGraph } from "./RelationshipGraph"

describe("RelationshipGraph empty and failure states", () => {
  it("renders compact empty states and handles update failures", async () => {
    readerApiMock.getRelationships.mockResolvedValueOnce({ nodes: [], edges: [] })

    await renderGraph(<RelationshipGraph bookId="book-1" upToChapter={3} compact authorMode={false} />)
    await flush()
    await waitForText("No graphable relationships yet")

    expect(text()).toContain("No graphable relationships yet")
    expect(text()).toContain("Open characters")

    cleanupRelationshipGraphRender()
    readerApiMock.getRelationships.mockResolvedValueOnce(graphData)
    booksApiMock.updateRelationship.mockRejectedValueOnce(new Error("network"))

    await renderGraph(<RelationshipGraph bookId="book-1" upToChapter={3} authorMode />)
    await flush()
    await waitForText("3 characters")
    await act(async () => {
      graphHandle()?.selectEdge("rel-2")
      await Promise.resolve()
    })
    await act(async () => {
      clickButton("Save correction")
      await Promise.resolve()
      await Promise.resolve()
    })
    expect(text()).toContain("Could not save the relationship correction.")
  })
})
