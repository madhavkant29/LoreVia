import { describe, expect, it } from "vitest"

import { formatDate, formatNumber } from "./utils"

describe("overview date formatting", () => {
  it("does not present missing or malformed timestamps as today", () => {
    expect(formatDate(null)).toBe("Unavailable")
    expect(formatDate("not-a-date")).toBe("Unavailable")
  })

  it("does not present missing numeric data as an active sync", () => {
    expect(formatNumber(null)).toBe("Unavailable")
    expect(formatNumber(Number.NaN)).toBe("Unavailable")
    expect(formatNumber(0)).toBe("0")
  })
})
