import { afterEach, describe, expect, it, vi } from "vitest"

import { capture, identify } from "./posthog"

describe("PostHog analytics helpers", () => {
  afterEach(() => {
    delete window.__loreviaPosthog
  })

  it("captures safe event properties and identifies authenticated users", () => {
    const captureClient = vi.fn()
    const identifyClient = vi.fn()
    window.__loreviaPosthog = { capture: captureClient, identify: identifyClient, reset: vi.fn() }

    capture("finding_opened", { book_id: "book-1", severity: "high" })
    identify("user-1", { tier: "author" })

    expect(captureClient).toHaveBeenCalledOnce()
    expect(captureClient).toHaveBeenCalledWith("finding_opened", { book_id: "book-1", severity: "high" })
    expect(identifyClient).toHaveBeenCalledWith("user-1", { tier: "author" })
    expect(JSON.stringify(captureClient.mock.calls)).not.toContain("manuscript")
    expect(JSON.stringify(captureClient.mock.calls)).not.toContain("excerpt")
  })
})
