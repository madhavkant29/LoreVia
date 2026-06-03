import type { ReaderDisplayStyle } from "@/types/reader"

export type ReaderFontFamily = "serif" | "sans" | "mono" | "italian-old-style" | "eb-garamond"

export const READER_FONT_OPTIONS: ReadonlyArray<{ value: ReaderFontFamily; label: string }> = [
  { value: "serif", label: "Serif" },
  { value: "sans", label: "Sans" },
  { value: "mono", label: "Mono" },
  { value: "italian-old-style", label: "Italian Old Style" },
  { value: "eb-garamond", label: "EB Garamond" },
]

const RELAXED_FONT_STACKS: Record<ReaderFontFamily, string> = {
  serif: '"Newsreader", "Merriweather", Georgia, serif',
  sans: '"Space Grotesk", "Avenir Next", "Segoe UI Variable Text", sans-serif',
  mono: '"SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace',
  "italian-old-style": '"Monotype Italian Old Style Pro Regular", "Monotype Italian Old Style Pro", "Italian Old Style", "Iowan Old Style", Georgia, serif',
  "eb-garamond": '"EB Garamond", Garamond, "Times New Roman", Georgia, serif',
}

const PUBLISHED_FONT_STACKS: Record<ReaderFontFamily, string> = {
  serif: 'Georgia, "Times New Roman", Times, serif',
  sans: '"Space Grotesk", "Avenir Next", "Segoe UI Variable Text", sans-serif',
  mono: '"SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace',
  "italian-old-style": '"Monotype Italian Old Style Pro Regular", "Monotype Italian Old Style Pro", "Italian Old Style", "Iowan Old Style", Georgia, serif',
  "eb-garamond": '"EB Garamond", Garamond, "Times New Roman", Georgia, serif',
}

export function isReaderFontFamily(value: string | null): value is ReaderFontFamily {
  return READER_FONT_OPTIONS.some((option) => option.value === value)
}

export function resolveReaderFontStack(fontFamily: ReaderFontFamily, displayStyle: ReaderDisplayStyle): string {
  return displayStyle === "published" ? PUBLISHED_FONT_STACKS[fontFamily] : RELAXED_FONT_STACKS[fontFamily]
}
