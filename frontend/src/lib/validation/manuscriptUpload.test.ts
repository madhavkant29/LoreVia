import { describe, expect, it } from "vitest"

import {
  BOOK_UPLOAD_MAX_BYTES,
  COVER_UPLOAD_MAX_BYTES,
  MANUSCRIPT_IMPORT_MAX_FILE_BYTES,
  MANUSCRIPT_IMPORT_MAX_FILES,
  NOVEL_UPLOAD_ACCEPT,
  SCREENPLAY_UPLOAD_ACCEPT,
  validateCoverFile,
  validateManuscriptFile,
  validateManuscriptFiles,
} from "./manuscriptUpload"

function makeFile(name: string, size: number, type = "application/octet-stream"): File {
  const file = new File(["x"], name, { type })
  Object.defineProperty(file, "size", { configurable: true, value: size })
  return file
}

describe("manuscript upload validation", () => {
  it("accepts small supported novel manuscripts", () => {
    expect(validateManuscriptFile(makeFile("draft.docx", 2048), { workType: "novel" })).toBeNull()
    expect(validateManuscriptFile(makeFile("draft.pdf", 2048), { workType: "novel" })).toBeNull()
    expect(validateManuscriptFile(makeFile("draft.epub", 2048), { workType: "novel" })).toBeNull()
    expect(validateManuscriptFile(makeFile("draft.txt", 2048), { workType: "novel" })).toBeNull()
    expect(validateManuscriptFile(makeFile("draft.md", 2048), { workType: "novel" })).toBeNull()
    expect(validateManuscriptFile(makeFile("draft.scriv.zip", 2048), { workType: "novel" })).toBeNull()
  })

  it("accepts a manuscript exactly at the size limit", () => {
    expect(
      validateManuscriptFile(makeFile("big.pdf", BOOK_UPLOAD_MAX_BYTES), { workType: "novel" }),
    ).toBeNull()
  })

  it("rejects files over the upload limit with the actual limit", () => {
    const error = validateManuscriptFile(makeFile("huge.pdf", BOOK_UPLOAD_MAX_BYTES + 1), {
      workType: "novel",
    })
    expect(error).toContain("huge.pdf")
    expect(error).toContain("100 MB")
  })

  it("rejects empty files", () => {
    const error = validateManuscriptFile(makeFile("empty.txt", 0), { workType: "novel" })
    expect(error).toContain("empty.txt")
    expect(error?.toLowerCase()).toContain("empty")
  })

  it("rejects unsupported extensions", () => {
    const error = validateManuscriptFile(makeFile("cover.png", 2048), { workType: "novel" })
    expect(error).toContain("isn't a supported format")
  })

  it("explains that legacy .doc files need conversion", () => {
    const error = validateManuscriptFile(makeFile("old.doc", 2048), { workType: "novel" })
    expect(error).toContain(".docx")
  })

  it("uses screenplay formats when the workspace is screenplay mode", () => {
    expect(validateManuscriptFile(makeFile("act1.fountain", 2048), { workType: "screenplay" })).toBeNull()
    expect(validateManuscriptFile(makeFile("act1.epub", 2048), { workType: "screenplay" })).not.toBeNull()
  })

  it("enforces per-file, count, and total limits for multi-file imports", () => {
    const overFileLimit = validateManuscriptFiles(
      [makeFile("one.pdf", MANUSCRIPT_IMPORT_MAX_FILE_BYTES + 1)],
      { workType: "novel" },
    )
    expect(overFileLimit).toContain("20 MB")

    const tooMany = Array.from({ length: MANUSCRIPT_IMPORT_MAX_FILES + 1 }, (_, index) =>
      makeFile(`chapter-${index}.txt`, 10),
    )
    expect(validateManuscriptFiles(tooMany, { workType: "novel" })).toContain(
      String(MANUSCRIPT_IMPORT_MAX_FILES),
    )

    const tooHeavy = Array.from({ length: 4 }, (_, index) => makeFile(`part-${index}.txt`, 16 * 1024 * 1024))
    const totalError = validateManuscriptFiles(tooHeavy, { workType: "novel" })
    expect(totalError).toContain("60 MB")
  })

  it("accepts an import exactly at the aggregate limit", () => {
    const files = [
      makeFile("part-a.txt", 20 * 1024 * 1024),
      makeFile("part-b.txt", 20 * 1024 * 1024),
      makeFile("part-c.txt", 20 * 1024 * 1024),
    ]
    expect(validateManuscriptFiles(files, { workType: "novel" })).toBeNull()
  })

  it("rejects empty selections", () => {
    expect(validateManuscriptFiles([], { workType: "novel" })).toContain("at least one file")
  })

  it("validates cover files", () => {
    expect(validateCoverFile(makeFile("cover.png", 2048, "image/png"))).toBeNull()
    expect(validateCoverFile(makeFile("cover.jpg", 2048, "image/jpeg"))).toBeNull()
    expect(validateCoverFile(makeFile("cover.webp", 2048, "image/webp"))).toBeNull()
    expect(validateCoverFile(makeFile("cover.gif", 2048, "image/gif"))).toContain("PNG, JPEG, or WebP")
    expect(validateCoverFile(makeFile("huge.png", COVER_UPLOAD_MAX_BYTES + 1))).toContain("5 MB")
  })

  it("exposes accept attributes that include backend-supported formats", () => {
    expect(NOVEL_UPLOAD_ACCEPT).toContain(".docx")
    expect(NOVEL_UPLOAD_ACCEPT).toContain(".epub")
    expect(SCREENPLAY_UPLOAD_ACCEPT).toContain(".fountain")
  })
})
