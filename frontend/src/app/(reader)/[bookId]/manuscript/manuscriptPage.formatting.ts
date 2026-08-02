import type { ManuscriptDraftFontFamily } from "@/components/reader/ManuscriptNonWriteWorkspace"
import { MANUSCRIPT_ANNOTATION_CATEGORY_LABELS } from "@/lib/utils/manuscriptAnnotations"
import { buildSceneAutosaveKey } from "@/lib/utils/manuscriptEditor"
import type { ChapterData, ChapterMedia } from "@/types/reader"
import type {
  ManuscriptAnnotationCategory,
  NovelScene,
  WritingTemplate,
} from "@/types/book"

export function escapeHtmlAttribute(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
}

export function chapterMediaSrc(item: ChapterMedia) {
  if (item.url) return item.url
  if (item.content_base64 && item.content_type) return `data:${item.content_type};base64,${item.content_base64}`
  return ""
}

export function hydrateChapterMediaHtml(chapter: ChapterData) {
  let html = chapter.html_content || textToHtml(chapter.text_content || "")
  const media = [...(chapter.media ?? [])].sort((left, right) => left.sort_order - right.sort_order)
  for (const item of media) {
    const src = chapterMediaSrc(item)
    if (!src) continue
    const imageHtml = `<img src="${escapeHtmlAttribute(src)}" alt="${escapeHtmlAttribute(item.marker)}" title="Embedded chapter image" />`
    if (html.includes(item.marker)) {
      html = html.split(item.marker).join(imageHtml)
    } else {
      html += `<p>${imageHtml}</p>`
    }
  }
  return html
}

export function resolveManuscriptDraftFontStack(fontFamily: ManuscriptDraftFontFamily): string {
  if (fontFamily === "georgia") return 'Georgia, "Times New Roman", serif'
  if (fontFamily === "sans") return '"Space Grotesk", "Avenir Next", "Segoe UI Variable Text", sans-serif'
  if (fontFamily === "italian-old-style") {
    return '"Iowan Old Style", "Palatino Linotype", "Book Antiqua", Palatino, Georgia, serif'
  }
  if (fontFamily === "eb-garamond") return '"EB Garamond", Garamond, "Times New Roman", Georgia, serif'
  return '"Times New Roman", Georgia, serif'
}

export function buildManuscriptInspectorClasses(isDark: boolean) {
  return {
    rail: isDark
      ? "min-w-0 xl:sticky xl:top-[8.25rem] xl:max-h-[calc(100vh-8.25rem)] xl:self-start xl:overflow-y-auto border-l border-white/[0.08] bg-[#0b0f11] text-slate-100"
      : "min-w-0 xl:sticky xl:top-[8.25rem] xl:max-h-[calc(100vh-8.25rem)] xl:self-start xl:overflow-y-auto border-l border-stone-200 bg-white text-stone-950",
    section: isDark
      ? "border-t border-white/[0.08] px-4 py-4 first:border-t-0"
      : "border-t border-stone-200 px-4 py-4 first:border-t-0",
    record: isDark
      ? "rounded-md border border-white/[0.08] bg-[#111517] px-3 py-3"
      : "rounded-md border border-stone-200 bg-stone-50 px-3 py-3",
    label: isDark
      ? "text-3xs font-semibold uppercase tracking-[0.22em] text-slate-400"
      : "text-3xs font-semibold uppercase tracking-[0.22em] text-stone-500",
    mutedText: isDark ? "text-slate-400" : "text-stone-500",
    bodyText: isDark ? "text-slate-200" : "text-stone-700",
    input: isDark
      ? "rounded-sm border border-white/[0.08] bg-black/70 text-slate-100"
      : "rounded-sm border border-stone-200 bg-white text-stone-900",
    secondaryButton: isDark
      ? "rounded-sm border border-white/[0.1] bg-[#111517] px-3 py-2 text-xs font-semibold text-slate-200 hover:bg-white/[0.06]"
      : "rounded-sm border border-stone-200 bg-white px-3 py-2 text-xs font-semibold text-stone-700 hover:bg-stone-50",
    primaryButton: "rounded-sm bg-[#1f615d] px-3 py-2 text-xs font-semibold text-white hover:bg-[#276f6a] disabled:opacity-40",
    dangerButton: isDark ? "text-xs font-semibold text-rose-300" : "text-xs font-semibold text-rose-700",
    chip: isDark
      ? "rounded-sm border border-white/[0.08] bg-white/[0.05] px-2 py-0.5 text-3xs font-medium text-slate-300"
      : "rounded-sm border border-stone-200 bg-white px-2 py-0.5 text-3xs font-medium text-stone-600",
  } as const
}

export function getSceneDropSlotLabel(index: number, totalScenes: number) {
  if (index <= 0) return "Drop at start"
  if (index >= totalScenes) return "Drop at end"
  return `Drop at position ${index + 1}`
}

export function buildSceneDraftStorageKey(bookId: string, scene?: NovelScene | null, chapterNumber?: number | null) {
  return buildSceneAutosaveKey(bookId, scene?.id ?? `new:${chapterNumber ?? "unassigned"}`)
}

export function buildTemplateNoteBody(template: WritingTemplate) {
  return [
    `# ${template.title}`,
    "",
    template.description.trim(),
    "",
    template.content.trim(),
  ].filter((line) => line !== undefined && line !== null).join("\n")
}

export function buildTemplateOutlineBlock(template: WritingTemplate) {
  return [
    `## Draft outline: ${template.title}`,
    "",
    template.description.trim() ? `Purpose: ${template.description.trim()}` : "",
    "",
    template.content.trim(),
  ].filter((line) => line !== undefined && line !== null).join("\n")
}

export function annotationCategoryLabel(category: string) {
  return MANUSCRIPT_ANNOTATION_CATEGORY_LABELS[category as ManuscriptAnnotationCategory] ?? category
}

export function textToHtml(text: string) {
  if (!text.trim()) return "<p></p>"
  return text
    .split(/\n{2,}/)
    .map((paragraph) => `<p>${escapeHtml(paragraph).replace(/\n/g, "<br>")}</p>`)
    .join("")
}

export function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
}

export function escapeAttribute(value: string) {
  return escapeHtml(value).replaceAll('"', "&quot;")
}
