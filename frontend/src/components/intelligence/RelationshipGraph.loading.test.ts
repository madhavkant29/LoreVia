import { beforeEach, expect, it, vi } from "vitest"
import { loadRelationshipGraph } from "./RelationshipGraph.loading"
import { readerApi } from "@/lib/api/reader"
vi.mock("@/lib/api/reader", () => ({ readerApi: { getRelationships: vi.fn() } }))
beforeEach(() => vi.clearAllMocks())

it("keeps nodes and hidden nodes while loading every edge page", async () => {
  vi.mocked(readerApi.getRelationships).mockResolvedValueOnce({ nodes: [{ id: "a", name: "Nora", role: null, first_chapter: 1 }], edges: [], hidden_nodes: [], has_more: true, next_offset: 100 }).mockResolvedValueOnce({ nodes: [], edges: [{ id: "r", source: "a", target: "b", type: "friend", description: null, sentiment: null }], has_more: false })
  const graph = await loadRelationshipGraph("book", 4, false)
  expect(graph.nodes).toHaveLength(1)
  expect(graph.edges).toHaveLength(1)
  expect(readerApi.getRelationships).toHaveBeenLastCalledWith("book", 4, { includeInactive: false, include: "edges", offset: 100 })
})
it("rejects failed or non-advancing pages instead of claiming the graph is complete", async () => {
  vi.mocked(readerApi.getRelationships).mockResolvedValueOnce({ nodes: [], edges: [], has_more: true, next_offset: 0 })
  await expect(loadRelationshipGraph("book", 4, false)).rejects.toThrow("did not advance")
  vi.mocked(readerApi.getRelationships).mockResolvedValueOnce({ nodes: [], edges: [], has_more: true, next_offset: 100 }).mockRejectedValueOnce(new Error("network"))
  await expect(loadRelationshipGraph("book", 4, false)).rejects.toThrow("network")
})
