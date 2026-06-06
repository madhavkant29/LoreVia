import { describe, expect, it } from "vitest"

import {
  getManuscriptPreviewContentWidthMm,
  getManuscriptPreviewLayout,
  getManuscriptPreviewPageExtentPx,
  millimetersToPixels,
} from "./manuscriptPreview"

describe("manuscript preview utilities", () => {
  it("returns layout settings that mirror the standard manuscript export preset", () => {
    const layout = getManuscriptPreviewLayout("standard_manuscript")

    expect(layout.label).toBe("Standard manuscript")
    expect(layout.pageWidthMm).toBeCloseTo(215.9, 1)
    expect(layout.pageHeightMm).toBeCloseTo(279.4, 1)
    expect(layout.fontSizePt).toBe(12)
    expect(getManuscriptPreviewContentWidthMm(layout)).toBeCloseTo(165.1, 1)
  })

  it("returns paperback-specific typography and margins for trade and kdp presets", () => {
    const trade = getManuscriptPreviewLayout("trade_paperback")
    const kdp = getManuscriptPreviewLayout("kdp_paperback")

    expect(trade.label).toBe("Trade paperback")
    expect(trade.pageWidthMm).toBe(148)
    expect(trade.fontSizePt).toBe(11)

    expect(kdp.label).toBe("6×9 print paperback")
    expect(kdp.paddingLeftMm).toBeGreaterThan(kdp.paddingRightMm)
    expect(kdp.fontFamily).toContain("Garamond")
  })

  it("derives preview page extents in pixels for scroll-based page counting", () => {
    const layout = getManuscriptPreviewLayout("standard_manuscript")

    expect(millimetersToPixels(25.4)).toBeCloseTo(96, 4)
    expect(getManuscriptPreviewPageExtentPx(layout)).toBeGreaterThan(800)
  })
})
