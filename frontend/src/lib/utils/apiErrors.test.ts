import { describe, expect, it } from "vitest"

import { getApiErrorDetail } from "./apiErrors"

describe("getApiErrorDetail", () => {
  it("returns the backend detail for axios errors", () => {
    const error = {
      isAxiosError: true,
      response: { data: { detail: "Passage text is required." } },
    }

    expect(getApiErrorDetail(error)).toBe("Passage text is required.")
  })

  it("returns null when the backend detail is not a string", () => {
    const error = {
      isAxiosError: true,
      response: { data: { detail: ["not", "a", "string"] } },
    }

    expect(getApiErrorDetail(error)).toBeNull()
  })

  it("returns the message from structured backend details", () => {
    const error = {
      isAxiosError: true,
      response: {
        data: {
          detail: {
            kind: "llm_tokens",
            message: "Support Assistant token limit exceeded for the 5-hour window.",
          },
        },
      },
    }

    expect(getApiErrorDetail(error)).toBe("Support Assistant token limit exceeded for the 5-hour window.")
  })

  it("returns null for non-axios errors", () => {
    expect(getApiErrorDetail(new Error("boom"))).toBeNull()
  })
})
