import type { ReaderDisplayStyle } from "@/types/reader"

export type ReaderFontFamily = "serif" | "sans" | "mono"

const RELAXED_FONT_STACKS: Record<ReaderFontFamily, string> = {
  serif: '"Newsreader", "Merriweather", Georgia, serif',
  sans: '"Space Grotesk", "Avenir Next", "Segoe UI Variable Text", sans-serif',
  mono: '"SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace',
}

const PUBLISHED_FONT_STACKS: Record<ReaderFontFamily, string> = {
  serif: 'Georgia, "Times New Roman", Times, serif',
  sans: '"Space Grotesk", "Avenir Next", "Segoe UI Variable Text", sans-serif',
  mono: '"SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace',
}

export function resolveReaderFontStack(fontFamily: ReaderFontFamily, displayStyle: ReaderDisplayStyle): string {
  return displayStyle === "published" ? PUBLISHED_FONT_STACKS[fontFamily] : RELAXED_FONT_STACKS[fontFamily]
}
