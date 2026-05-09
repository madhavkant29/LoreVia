import { describe, expect, it } from "vitest"

import {
  getBookHref,
  getBookRouteSegment,
  normalizeBookRouteId,
  replaceBookRouteSegment,
  slugifyBookTitle,
} from "./bookRoutes"

describe("book route utils", () => {
  it("extracts the underlying uuid from a readable route segment", () => {
    expect(normalizeBookRouteId("my-project--123e4567-e89b-12d3-a456-426614174000")).toBe("123e4567-e89b-12d3-a456-426614174000")
  })

  it("leaves plain uuids untouched", () => {
    expect(normalizeBookRouteId("123e4567-e89b-12d3-a456-426614174000")).toBe("123e4567-e89b-12d3-a456-426614174000")
  })

  it("extracts non-uuid ids from readable route segments too", () => {
    expect(normalizeBookRouteId("sky-of-ash--book-1")).toBe("book-1")
  })

  it("slugifies titles into readable route segments", () => {
    expect(slugifyBookTitle("The Queen's Gate: Draft #2")).toBe("the-queen-s-gate-draft-2")
  })

  it("builds book hrefs with the readable route segment", () => {
    expect(getBookHref({
      id: "123e4567-e89b-12d3-a456-426614174000",
      title: "Sky Harbor",
    })).toBe("/sky-harbor--123e4567-e89b-12d3-a456-426614174000")
  })

  it("replaces the leading book route segment while preserving nested paths", () => {
    expect(replaceBookRouteSegment(
      "/123e4567-e89b-12d3-a456-426614174000/manuscript",
      "123e4567-e89b-12d3-a456-426614174000",
      getBookRouteSegment({
        id: "123e4567-e89b-12d3-a456-426614174000",
        title: "Sky Harbor",
      })
    )).toBe("/sky-harbor--123e4567-e89b-12d3-a456-426614174000/manuscript")
  })
})
