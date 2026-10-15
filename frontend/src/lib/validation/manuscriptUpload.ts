export const BOOK_UPLOAD_MAX_BYTES = 100 * 1024 * 1024
export const MANUSCRIPT_IMPORT_MAX_FILE_BYTES = 20 * 1024 * 1024
export const MANUSCRIPT_IMPORT_MAX_FILES = 20
export const MANUSCRIPT_IMPORT_MAX_TOTAL_BYTES = 60 * 1024 * 1024
export const COVER_UPLOAD_MAX_BYTES = 5 * 1024 * 1024

export const NOVEL_UPLOAD_ACCEPT = ".pdf,.epub,.docx,.txt,.md,.scrivzip,.scriv.zip"
export const SCREENPLAY_UPLOAD_ACCEPT = ".pdf,.fountain,.txt,.md"
export const MANUSCRIPT_IMPORT_ACCEPT = ".pdf,.epub,.docx,.txt,.md,.fountain"
export const COVER_ACCEPT = "image/png,image/jpeg,image/webp"

const NOVEL_SUPPORTED_EXTENSIONS = [
  ".pdf",
  ".epub",
  ".docx",
  ".txt",
  ".md",
  ".scrivzip",
  ".scriv.zip",
] as const

const SCREENPLAY_SUPPORTED_EXTENSIONS = [".pdf", ".fountain", ".txt", ".md"] as const

const COVER_SUPPORTED_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp"] as const

export type UploadWorkType = "novel" | "screenplay" | "other"

export function formatMegabytes(bytes: number): string {
  const megabytes = bytes / (1024 * 1024)
  return Number.isInteger(megabytes) ? `${megabytes} MB` : `${megabytes.toFixed(1)} MB`
}

function hasExtension(fileName: string, extensions: readonly string[]): boolean {
  const lower = fileName.toLowerCase()
  return extensions.some((extension) => lower.endsWith(extension))
}

function isLegacyDoc(fileName: string): boolean {
  const lower = fileName.toLowerCase()
  return lower.endsWith(".doc") && !lower.endsWith(".docx")
}

export function validateManuscriptFile(
  file: File,
  options: { workType: UploadWorkType; maxBytes?: number },
): string | null {
  const maxBytes = options.maxBytes ?? BOOK_UPLOAD_MAX_BYTES
  if (file.size <= 0) {
    return `${file.name} is empty. Choose a file that contains manuscript text.`
  }
  if (file.size > maxBytes) {
    return `${file.name} is ${formatMegabytes(file.size)}, which is over the ${formatMegabytes(maxBytes)} limit for a single manuscript file.`
  }
  if (isLegacyDoc(file.name)) {
    return `${file.name} is a legacy .doc file, which isn't supported yet. Save it as .docx and try again.`
  }
  const supported =
    options.workType === "screenplay" ? SCREENPLAY_SUPPORTED_EXTENSIONS : NOVEL_SUPPORTED_EXTENSIONS
  if (!hasExtension(file.name, supported)) {
    const accepted = options.workType === "screenplay" ? "PDF, Fountain, TXT, or Markdown" : "PDF, EPUB, DOCX, TXT, or Markdown"
    return `${file.name} isn't a supported format. Use ${accepted}.`
  }
  return null
}

export function validateManuscriptFiles(
  files: File[],
  options: { workType: UploadWorkType; maxBytes?: number; maxFiles?: number; maxTotalBytes?: number },
): string | null {
  const maxBytes = options.maxBytes ?? MANUSCRIPT_IMPORT_MAX_FILE_BYTES
  const maxFiles = options.maxFiles ?? MANUSCRIPT_IMPORT_MAX_FILES
  const maxTotalBytes = options.maxTotalBytes ?? MANUSCRIPT_IMPORT_MAX_TOTAL_BYTES
  if (files.length === 0) {
    return "Select at least one file."
  }
  if (files.length > maxFiles) {
    return `Add at most ${maxFiles} files at once.`
  }
  const totalBytes = files.reduce((sum, file) => sum + Math.max(0, file.size), 0)
  if (totalBytes > maxTotalBytes) {
    return `The selected files add up to ${formatMegabytes(totalBytes)}, which is over the ${formatMegabytes(maxTotalBytes)} total limit.`
  }
  for (const file of files) {
    const error = validateManuscriptFile(file, { workType: options.workType, maxBytes })
    if (error) return error
  }
  return null
}

export function validateCoverFile(file: File): string | null {
  if (file.size <= 0) {
    return `${file.name} is empty. Choose a cover image.`
  }
  if (file.size > COVER_UPLOAD_MAX_BYTES) {
    return `${file.name} is ${formatMegabytes(file.size)}, which is over the ${formatMegabytes(COVER_UPLOAD_MAX_BYTES)} cover image limit.`
  }
  if (!hasExtension(file.name, COVER_SUPPORTED_EXTENSIONS)) {
    return `${file.name} isn't a supported cover image. Use PNG, JPEG, or WebP.`
  }
  return null
}
