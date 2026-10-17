import { readerApi } from "@/lib/api/reader"

export async function loadRelationshipGraph(bookId: string, chapter: number, includeInactive: boolean) {
  const first = await readerApi.getRelationships(bookId, chapter, { includeInactive, include: "nodes,edges,hidden_nodes" })
  if (!first.has_more) return first
  let page = first
  let offset = 0
  const edges = [...first.edges]
  while (page.has_more) {
    const next = page.next_offset
    if (typeof next !== "number" || !Number.isInteger(next) || next <= offset) throw new Error("Relationship pagination did not advance")
    offset = next
    page = await readerApi.getRelationships(bookId, chapter, { includeInactive, include: "edges", offset })
    edges.push(...page.edges)
  }
  return { ...first, edges, has_more: false, next_offset: null }
}
