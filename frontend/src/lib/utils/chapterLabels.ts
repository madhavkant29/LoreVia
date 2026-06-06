import type { ChapterKind } from "@/types/reader"

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
): string {
  if (!chapterKind || chapterKind === "chapter") {
    if (typeof number === "number") {
      return `${unitLabel} ${number}`
    }
    return unitLabel
  }
  return CHAPTER_KIND_LABELS[chapterKind] ?? chapterKind.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}

export function chapterKindShortLabel(
  chapterKind: ChapterKind | undefined | null,
  number: number | undefined | null,
  unitShortLabel = "Ch.",
): string {
  if (!chapterKind || chapterKind === "chapter") {
    if (typeof number === "number") {
      return `${unitShortLabel} ${number}`
    }
    return unitShortLabel
  }
  return CHAPTER_KIND_LABELS[chapterKind] ?? chapterKind.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}
