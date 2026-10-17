import { beforeEach, describe, expect, it, vi } from "vitest"
import { booksApi } from "@/lib/api/books"
import { loadAllSeries, loadSeriesProjects, positiveNumberError, seriesVolumeLabel, worldContextItems } from "./seriesPage.helpers"
vi.mock("@/lib/api/books", () => ({ booksApi: { listSeries: vi.fn(), listPage: vi.fn() } }))

describe("series workspace helpers", () => {
  beforeEach(() => vi.mocked(booksApi.listSeries).mockReset())
  it("loads project choices beyond the selector limit and rejects partial cursor pages", async () => {
    vi.mocked(booksApi.listPage).mockResolvedValueOnce({ items: [{ id: "b1" }], has_more: true, next_cursor: "second" } as never).mockResolvedValueOnce({ items: [{ id: "b2" }], next_cursor: null } as never)
    expect(await loadSeriesProjects()).toEqual([{ id: "b1" }, { id: "b2" }])
    expect(booksApi.listPage).toHaveBeenLastCalledWith(false, "second", 100)
    vi.mocked(booksApi.listPage).mockResolvedValue({ items: [], has_more: true, next_cursor: null } as never)
    await expect(loadSeriesProjects()).rejects.toThrow("incomplete")
    vi.mocked(booksApi.listPage).mockResolvedValue({ items: [], has_more: true, next_cursor: "loop" } as never)
    await expect(loadSeriesProjects()).rejects.toThrow("did not advance")
  })
  it("loads every offset page and deduplicates overlapping series", async () => {
    vi.mocked(booksApi.listSeries).mockResolvedValueOnce({ items: [{ id: "s1" }], has_more: true, limit: 100 } as never).mockResolvedValueOnce({ items: [{ id: "s1" }, { id: "s2" }], has_more: false } as never)
    expect(await loadAllSeries()).toEqual([{ id: "s1" }, { id: "s2" }])
    expect(booksApi.listSeries).toHaveBeenLastCalledWith({ limit: 100, offset: 100 })
  })
  it("fails explicitly when a series page is malformed or stops advancing", async () => {
    vi.mocked(booksApi.listSeries).mockResolvedValue({ items: [{ id: "s1" }], has_more: true, limit: 100 } as never)
    await expect(loadAllSeries()).rejects.toThrow("did not advance")
    vi.mocked(booksApi.listSeries).mockResolvedValue({ items: null } as never)
    await expect(loadAllSeries()).rejects.toThrow("incomplete")
  })
  it("validates optional positions without silently rewriting malformed numbers", () => {
    for (const value of ["", "  ", "1", "2147483647"]) expect(positiveNumberError(value, "Position")).toBeNull()
    for (const value of ["0", "-1", "1.5", "2e3", "2147483648", "abc"]) expect(positiveNumberError(value, "Position")).toContain("whole number")
    expect(seriesVolumeLabel("screenplay", 2)).toBe("Episode 2")
    expect(seriesVolumeLabel("novel", null)).toBe("Unordered")
  })
  it("preserves full text world context and legacy structured context", () => {
    expect(worldContextItems({ world_context: "Gate law\n\nThe entire world context." })).toEqual(["Gate law\n\nThe entire world context."])
    expect(worldContextItems({ world_context: [{ name: "Gate", description: "Opens at dusk." }, "Road"] })).toEqual(["Gate — Opens at dusk.", "Road"])
    expect(worldContextItems({})).toEqual([])
    expect(worldContextItems({ world_context: " " })).toEqual([])
  })
})
