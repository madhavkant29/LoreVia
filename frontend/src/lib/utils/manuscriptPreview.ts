import type { PublishingPreset } from "@/types/book"

const MILLIMETERS_PER_INCH = 25.4
const PIXELS_PER_INCH = 96

export interface ManuscriptPreviewLayout {
  label: string
  pageWidthMm: number
  pageHeightMm: number
  paddingTopMm: number
  paddingRightMm: number
  paddingBottomMm: number
  paddingLeftMm: number
  pageGapPx: number
  fontFamily: string
  fontSizePt: number
}

export function getManuscriptPreviewLayout(
  preset: PublishingPreset["active_preset"] | null | undefined
): ManuscriptPreviewLayout {
  switch (preset) {
    case "trade_paperback":
      return {
        label: "Trade paperback",
        pageWidthMm: 148,
        pageHeightMm: 210,
        paddingTopMm: 19.05,
        paddingRightMm: 20.32,
        paddingBottomMm: 19.05,
        paddingLeftMm: 20.32,
        pageGapPx: 28,
        fontFamily: '"Garamond", "Times New Roman", Georgia, serif',
        fontSizePt: 11,
      }
    case "kdp_paperback":
      return {
        label: "6×9 print paperback",
        pageWidthMm: 215.9,
        pageHeightMm: 279.4,
        paddingTopMm: 20.32,
        paddingRightMm: 19.05,
        paddingBottomMm: 20.32,
        paddingLeftMm: 22.35,
        pageGapPx: 28,
        fontFamily: '"Garamond", "Times New Roman", Georgia, serif',
        fontSizePt: 11,
      }
    default:
      return {
        label: "Standard manuscript",
        pageWidthMm: 215.9,
        pageHeightMm: 279.4,
        paddingTopMm: 25.4,
        paddingRightMm: 25.4,
        paddingBottomMm: 25.4,
        paddingLeftMm: 25.4,
        pageGapPx: 28,
        fontFamily: '"Times New Roman", Georgia, serif',
        fontSizePt: 12,
      }
  }
}

export function getManuscriptPreviewContentWidthMm(layout: ManuscriptPreviewLayout) {
  return Math.max(1, layout.pageWidthMm - layout.paddingLeftMm - layout.paddingRightMm)
}

export function millimetersToPixels(millimeters: number) {
  return (millimeters / MILLIMETERS_PER_INCH) * PIXELS_PER_INCH
}

export function getManuscriptPreviewPageExtentPx(layout: ManuscriptPreviewLayout) {
  return millimetersToPixels(layout.pageWidthMm) + layout.pageGapPx
}
