import { describe, expect, it } from "vitest"

import {
  currentFrontendReleaseSha,
  normalizeReleaseSha,
  UNKNOWN_RELEASE_SHA,
} from "./release"

describe("release identity", () => {
  it("normalizes valid revisions and rejects unsafe values", () => {
    expect(normalizeReleaseSha(" ABCDEF1234567 ")).toBe("abcdef1234567")
    expect(normalizeReleaseSha("abc123\r\nX-Injected: true")).toBe(UNKNOWN_RELEASE_SHA)
    expect(normalizeReleaseSha(undefined)).toBe(UNKNOWN_RELEASE_SHA)
  })

  it("prefers Vercel's source revision over the Docker release revision", () => {
    expect(
      currentFrontendReleaseSha({
        VERCEL_GIT_COMMIT_SHA: "a".repeat(40),
        RELEASE_SHA: "b".repeat(40),
      }),
    ).toBe("a".repeat(40))
  })
})
