import { afterEach, describe, expect, it, vi } from "vitest"

const getMock = vi.hoisted(() => vi.fn())

vi.mock("./client", () => ({
  apiClient: {
    get: getMock,
  },
}))

import { charactersApi } from "./character"

describe("charactersApi", () => {
  afterEach(() => {
    getMock.mockReset()
  })

  it("fetches a character by ID", async () => {
    const character = { id: "abc-123", book_id: "book-1", name: "Alice" }
    getMock.mockResolvedValue({ data: character })

    await expect(charactersApi.get("abc-123")).resolves.toEqual(character)
    expect(getMock).toHaveBeenCalledWith("/characters/abc-123", { params: undefined })
  })

  it("fetches a character with analysis metadata include param", async () => {
    const character = { id: "abc-123", book_id: "book-1", name: "Alice", analysis_metadata: {} }
    getMock.mockResolvedValue({ data: character })

    await expect(charactersApi.get("abc-123", "analysis_metadata")).resolves.toEqual(character)
    expect(getMock).toHaveBeenCalledWith("/characters/abc-123", { params: { include: "analysis_metadata" } })
  })

  it("fetches character state at a chapter", async () => {
    const state = { trait_state: { hair: { value: "brown" } }, at_chapter: 5, arc_note: null, prompt_delta: null }
    getMock.mockResolvedValue({ data: state })

    await expect(charactersApi.getState("abc-123", 5)).resolves.toEqual(state)
    expect(getMock).toHaveBeenCalledWith("/characters/abc-123/state", { params: { chapter: 5 } })
  })

  it("fetches character state at chapter 0 (baseline)", async () => {
    const state = { trait_state: {}, at_chapter: 0 }
    getMock.mockResolvedValue({ data: state })

    await expect(charactersApi.getState("abc-123", 0)).resolves.toEqual(state)
    expect(getMock).toHaveBeenCalledWith("/characters/abc-123/state", { params: { chapter: 0 } })
  })
})
