import type { ChapterKind } from "@/types/reader"

export function formatIndex(n: number, fmt: string = "arabic"): string {
  if (fmt === "arabic") return String(n)
  if (fmt === "roman-upper" || fmt === "roman-lower") {
    const val = toRoman(n)
    return fmt === "roman-lower" ? val.toLowerCase() : val
  }
  if (fmt === "alpha-upper" || fmt === "alpha-lower") {
    const val = toAlpha(n)
    return fmt === "alpha-upper" ? val.toUpperCase() : val
  }
  return String(n)
}

function toRoman(n: number): string {
  if (n < 1 || n > 3999) return String(n)
  const map: [number, string][] = [
    [1000, "M"], [900, "CM"], [500, "D"], [400, "CD"],
    [100, "C"], [90, "XC"], [50, "L"], [40, "XL"],
    [10, "X"], [9, "IX"], [5, "V"], [4, "IV"], [1, "I"],
  ]
  let remaining = n
  let result = ""
  for (const [value, numeral] of map) {
    while (remaining >= value) {
      result += numeral
      remaining -= value
    }
  }
  return result
}

function toAlpha(n: number): string {
  if (n < 1) return String(n)
  let remaining = n
  let result = ""
  while (remaining > 0) {
    remaining--
    result = String.fromCharCode(97 + (remaining % 26)) + result
    remaining = Math.floor(remaining / 26)
  }
  return result
}

const CHAPTER_KIND_LABELS: Record<ChapterKind, string> = {
  chapter: "",
  preface: "Preface",
  introduction: "Introduction",
  foreword: "Foreword",
  prologue: "Prologue",
  epilogue: "Epilogue",
  appendix: "Appendix",
  acknowledgments: "Acknowledgments",
  afterword: "Afterword",
  dedication: "Dedication",
  toc: "Table of Contents",
  index: "Index",
  title_page: "Title Page",
  copyright: "Copyright",
}

export function chapterKindLabel(
  chapterKind: ChapterKind | undefined | null,
  number: number | undefined | null,
  unitLabel = "Chapter",
  indexFormat = "arabic",
): string {
  if (!chapterKind || chapterKind === "chapter") {
    if (typeof number === "number") {
      return `${unitLabel} ${formatIndex(number, indexFormat)}`
    }
    return unitLabel
  }
  return CHAPTER_KIND_LABELS[chapterKind] ?? chapterKind.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}

export function chapterKindShortLabel(
  chapterKind: ChapterKind | undefined | null,
  number: number | undefined | null,
  unitShortLabel = "Ch.",
  indexFormat = "arabic",
): string {
  if (!chapterKind || chapterKind === "chapter") {
    if (typeof number === "number") {
      return `${unitShortLabel} ${formatIndex(number, indexFormat)}`
    }
    return unitShortLabel
  }
  return CHAPTER_KIND_LABELS[chapterKind] ?? chapterKind.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}
