import { afterEach, describe, expect, it, vi } from "vitest"

import { GET } from "./route"

describe("frontend release endpoint", () => {
  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it("returns Vercel's commit without allowing intermediary caching", async () => {
    vi.stubEnv("VERCEL_GIT_COMMIT_SHA", "A".repeat(40))

    const response = GET()

    expect(response.headers.get("cache-control")).toBe("no-store, max-age=0")
    await expect(response.json()).resolves.toEqual({
      app: "LoreVia frontend",
      release_sha: "a".repeat(40),
    })
  })
})
