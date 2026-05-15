import { describe, expect, it } from "vitest"

import { formatPointEntryLabel, formatPointsDelta } from "./formatters"

describe("monetization formatters", () => {
  it("adds a leading plus sign for positive point deltas", () => {
    expect(formatPointsDelta(25)).toBe("+25")
    expect(formatPointsDelta(-3)).toBe("-3")
  })

  it("maps known ledger entries to readable labels", () => {
    expect(
      formatPointEntryLabel({
        id: "1",
        entry_type: "grant",
        source_type: "referral_reward",
        points_delta: 50,
        metadata_json: {},
        created_at: new Date().toISOString(),
      })
    ).toBe("Referral reward")
    expect(
      formatPointEntryLabel({
        id: "2",
        entry_type: "grant",
        source_type: "rewarded_ad",
        points_delta: 3,
        metadata_json: {},
        created_at: new Date().toISOString(),
      })
    ).toBe("Rewarded ad")
    expect(
      formatPointEntryLabel({
        id: "3",
        entry_type: "grant",
        source_type: "daily_login",
        points_delta: 1,
        metadata_json: {},
        created_at: new Date().toISOString(),
      })
    ).toBe("Daily login")
    expect(
      formatPointEntryLabel({
        id: "4",
        entry_type: "spend",
        source_type: "public_share",
        points_delta: -10,
        metadata_json: {},
        created_at: new Date().toISOString(),
      })
    ).toBe("Public sharing")
  })
})
