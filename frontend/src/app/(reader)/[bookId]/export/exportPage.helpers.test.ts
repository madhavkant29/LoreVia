// @vitest-environment node
import { describe, expect, it } from "vitest"
import { importFileError, novelSettingsError, novelSettingsFromWorkspace } from "./exportPage.helpers"
import { exportErrorMessage, safeFileBase } from "@/lib/utils/exportFiles"

describe("export settings and file validation", () => {
  it("fills every optional publishing field without sharing mutable defaults", () => {
    const first = novelSettingsFromWorkspace()
    first.front_matter.dedication = "Changed"
    expect(novelSettingsFromWorkspace().front_matter.dedication).toBe("")
    expect(novelSettingsFromWorkspace().epub_metadata.language).toBe("en")
  })
  it("checks publishing limits without truncating drafts", () => {
    const settings = novelSettingsFromWorkspace()
    settings.epub_metadata.publisher = "a".repeat(501)
    expect(novelSettingsError(settings)).toContain("500 characters")
    settings.epub_metadata.publisher = "a".repeat(500)
    expect(novelSettingsError(settings)).toBeNull()
    settings.preface = "a".repeat(100001)
    expect(novelSettingsError(settings)).toContain("Preface")
    settings.preface = ""
    settings.front_matter.dedication = "a".repeat(100001)
    expect(novelSettingsError(settings)).toContain("Dedication")
  })
  it("rejects empty, unsupported, and multiple notes archives", () => {
    expect(importFileError([], "notes")).toBe("Choose files first.")
    expect(importFileError([new File([], "empty.md")], "manuscript")).toContain("empty")
    expect(importFileError([new File(["x"], "program.exe")], "world")).toContain("choose")
    const archive = new File(["zip"], "Notes.ZIP")
    expect(importFileError([archive], "notes")).toBeNull()
    expect(importFileError([archive, archive], "notes")).toContain("one notes ZIP")
    expect(importFileError([new File(["chapter"], "book.EPUB")], "manuscript")).toBeNull()
  })
  it("produces portable filenames with a non-empty fallback", () => {
    expect(safeFileBase("The Gate!", "book")).toBe("The-Gate")
    expect(safeFileBase("?!", "book")).toBe("book")
    expect(safeFileBase(undefined, "book")).toBe("book")
  })
  it("reads API details including binary error responses without hiding access failures", async () => {
    expect(await exportErrorMessage(new Error("no"), "Failed.")).toBe("Failed.")
    expect(await exportErrorMessage({ isAxiosError: true, response: { status: 403 } }, "Failed.")).toContain("access and plan")
    expect(await exportErrorMessage({ isAxiosError: true, response: { data: new Blob([JSON.stringify({ detail: "No chapters" })]) } }, "Failed.")).toBe("Failed. No chapters")
    expect(await exportErrorMessage({ isAxiosError: true, response: { data: new Blob(["not JSON"]) } }, "Failed.")).toBe("Failed.")
  })
})
