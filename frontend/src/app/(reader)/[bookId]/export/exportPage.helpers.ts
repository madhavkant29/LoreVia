import type { NovelEpubMetadata, NovelFrontMatter, WriterWorkspace } from "@/types/book"

export type NovelSettings = { preface: string; front_matter: NovelFrontMatter; epub_metadata: NovelEpubMetadata }
export const FRONT_MATTER_FIELDS = [
  ["dedication", "Dedication"], ["copyright_page", "Copyright page"], ["acknowledgements", "Acknowledgements"],
  ["about_author", "About the author"], ["series_book_list", "Series / book list"],
] as const
export const EPUB_FIELDS = [
  ["publisher", "Publisher", 500], ["language", "Language", 24], ["isbn", "ISBN", 64],
  ["series_name", "Series", 500], ["series_number", "Series number", 64], ["description", "Description / blurb", 20000],
] as const

export function novelSettingsFromWorkspace(workspace?: WriterWorkspace | null): NovelSettings {
  return {
    preface: workspace?.novel_preface ?? "",
    front_matter: { dedication: "", acknowledgements: "", copyright_page: "", about_author: "", series_book_list: "", ...workspace?.novel_front_matter },
    epub_metadata: { publisher: "", language: "en", isbn: "", description: "", series_name: "", series_number: "", ...workspace?.novel_epub_metadata },
  }
}

export function novelSettingsError(settings: NovelSettings): string | null {
  if (settings.preface.length > 100000) return "Preface must be 100,000 characters or fewer."
  for (const [key, label] of FRONT_MATTER_FIELDS) if (settings.front_matter[key].length > 100000) return `${label} must be 100,000 characters or fewer.`
  for (const [key, label, limit] of EPUB_FIELDS) if (settings.epub_metadata[key].length > limit) return `${label} must be ${limit.toLocaleString("en-US")} characters or fewer.`
  return null
}

export function importFileError(files: File[], kind: "manuscript" | "notes" | "world"): string | null {
  const extensions = kind === "notes" ? ["zip"] : kind === "world" ? ["docx", "doc", "pdf", "txt", "md"] : ["docx", "doc", "pdf", "txt", "md", "epub"]
  if (!files.length) return "Choose files first."
  if (kind === "notes" && files.length !== 1) return "Choose one notes ZIP."
  for (const file of files) {
    if (!extensions.includes(file.name.split(".").pop()?.toLowerCase() ?? "")) return `${file.name}: choose ${extensions.join(", ")} files.`
    if (!file.size) return `${file.name} is empty.`
  }
  return null
}
