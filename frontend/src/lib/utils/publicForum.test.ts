import { describe, expect, it } from "vitest"

import { formatReputationScore, formatWordProgress } from "./publicForum"

describe("public forum utilities", () => {
  it("formats positive reputation scores with a leading plus", () => {
    expect(formatReputationScore(7)).toBe("+7")
    expect(formatReputationScore(-3)).toBe("-3")
    expect(formatReputationScore(0)).toBe("0")
  })

  it("formats word progress using compact thousand labels", () => {
    expect(formatWordProgress(987)).toBe("987 words")
    expect(formatWordProgress(1200)).toBe("1.2k words")
    expect(formatWordProgress(20000)).toBe("20k words")
  })
})
