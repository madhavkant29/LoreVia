import { describe, expect, it } from "vitest"

import {
  WHATS_THE_WORD_MIN_DESCRIPTION_WORDS,
  canSubmitWhatsTheWordDescription,
  countWhatsTheWordDescriptionWords,
} from "./whatsTheWord"

describe("whatsTheWord helpers", () => {
  it("counts plain words in a description", () => {
    expect(countWhatsTheWordDescriptionWords("A dry, exhausted laugh after a loss")).toBe(7)
  })

  it("requires at least the minimum number of words", () => {
    expect(canSubmitWhatsTheWordDescription("Quiet grief after betrayal")).toBe(false)
    expect(
      canSubmitWhatsTheWordDescription(
        "Quiet grief after betrayal that still stings"
      )
    ).toBe(true)
    expect(WHATS_THE_WORD_MIN_DESCRIPTION_WORDS).toBe(5)
  })
})
