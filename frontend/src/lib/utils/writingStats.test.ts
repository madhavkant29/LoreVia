import { describe, expect, it } from "vitest"

import { buildSecondaryStats, buildWritingCards, buildWritingHeatmap, formatWordCount, getHeatmapLevel } from "./writingStats"

describe("writing stats utilities", () => {
  it("builds writing cards in dashboard order", () => {
    const cards = buildWritingCards({
      today: { words: 1202, target_words: 1000, progress_pct: 100 },
      this_week: { words: 2565, target_words: 7000, progress_pct: 37 },
      this_month: { words: 23065 },
      this_year: { words: 60171 },
      last_24_hours: { words: 2565 },
      last_7_days: { words: 14678 },
      last_30_days: { words: 60171 },
      last_year: { words: 60171 },
      heatmap: [],
      entries_today: [],
    })

    expect(cards.map((card) => card.key)).toEqual([
      "today",
      "this_week",
      "this_month",
      "this_year",
      "last_24_hours",
      "last_7_days",
      "last_30_days",
      "last_year",
    ])
    expect(cards[0]?.showProgress).toBe(true)
    expect(cards[2]?.showProgress).toBe(false)
  })

  it("groups heatmap days into weekly columns and adds month markers", () => {
    const heatmap = buildWritingHeatmap([
      { date: "2026-04-27", words: 0 },
      { date: "2026-04-28", words: 10 },
      { date: "2026-04-29", words: 20 },
      { date: "2026-04-30", words: 30 },
      { date: "2026-05-01", words: 40 },
      { date: "2026-05-02", words: 50 },
      { date: "2026-05-03", words: 60 },
      { date: "2026-05-04", words: 70 },
      { date: "2026-05-05", words: 80 },
      { date: "2026-05-06", words: 90 },
      { date: "2026-05-07", words: 100 },
      { date: "2026-05-08", words: 110 },
      { date: "2026-05-09", words: 120 },
      { date: "2026-05-10", words: 130 },
    ])

    expect(heatmap.columns).toHaveLength(2)
    expect(heatmap.columns[0]?.days).toHaveLength(7)
    expect(heatmap.columns[1]?.days[6]?.date).toBe("2026-05-10")
    expect(heatmap.months[0]).toEqual({ label: "Apr", column: 0 })
    expect(heatmap.months[1]).toEqual({ label: "May", column: 1 })
  })

  it("maps heatmap intensity into stable levels", () => {
    expect(getHeatmapLevel(0, 120)).toBe(0)
    expect(getHeatmapLevel(10, 120)).toBe(1)
    expect(getHeatmapLevel(40, 120)).toBe(2)
    expect(getHeatmapLevel(80, 120)).toBe(3)
    expect(getHeatmapLevel(120, 120)).toBe(4)
  })

  it("formats word counts with separators", () => {
    expect(formatWordCount(23065)).toBe("23,065 words")
  })

  it("includes customer-facing AI capacity in secondary stats", () => {
    const stats = buildSecondaryStats({
      public: {
        total_books_read: 2,
        total_words_read: 12345,
      },
      private: {
        total_uploads: 5,
        total_token_consumption: 42000,
        llm_request_count: 18,
        llm_total_tokens: 9876,
        ai_interactive_available: true,
        ai_processing_available: true,
        ai_capacity_usage_percent: 34,
        ai_capacity_resets_at: "2026-09-01T00:00:00Z",
        total_chapters_tracked: 9,
        saved_quotes: 3,
        active_analyzed_words: 12345,
        active_word_limit: 2000000,
        active_words_remaining: 1987655,
        monthly_processed_words: 12345,
        monthly_processed_word_limit: 1000000,
        monthly_processed_words_remaining: 987655,
        source_storage_bytes: 1024,
        source_storage_limit_bytes: 5368709120,
        source_storage_remaining_bytes: 5368708096,
        allowances_enforced: false,
      },
      writing: {
        today: { words: 0 },
        this_week: { words: 0 },
        this_month: { words: 0 },
        this_year: { words: 0 },
        last_24_hours: { words: 0 },
        last_7_days: { words: 0 },
        last_30_days: { words: 0 },
        last_year: { words: 0 },
        heatmap: [],
        entries_today: [],
      },
    })

    expect(stats.some((item) => item.label === "LLM requests" && item.value === "18")).toBe(true)
    expect(stats.some((item) => item.label === "AI capacity" && item.value === "34% used")).toBe(true)
    expect(stats.find((item) => item.label === "AI capacity")?.note).toContain("Sep 1, 2026")
  })
})
