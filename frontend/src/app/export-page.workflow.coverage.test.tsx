// @vitest-environment jsdom

import { act } from "react"
import { describe, expect, it } from "vitest"

import {
  ExportStudioPage,
  booksApiMock,
  click,
  getContainer,
  objectUrlMock,
  renderPage,
  setFieldValue,
  setInputFiles,
  text,
  waitForText,
  worldBuildingApiMock,
} from "./export-page.test-utils"

describe("ExportStudioPage workflows", () => {
  it("renders export studio and drives export, preview, import, and settings actions", async () => {
    await renderPage(<ExportStudioPage />)
    await waitForText("Ship clean outputs")

    expect(text()).toContain("The Ember Gate!")
    expect(text()).toContain("Bring material into this book")
    expect(text()).toContain("A note before the gate opens.")

    await click("DOCX")
    await click("EPUB")

    const checkboxes = Array.from(getContainer().querySelectorAll('input[type="checkbox"]')) as HTMLInputElement[]
    await act(async () => {
      checkboxes.forEach((item) => item.dispatchEvent(new MouseEvent("click", { bubbles: true })))
      await Promise.resolve()
    })
    expect(text()).toContain("Image placement")
    expect(text()).toContain("Include stored captions")

    const textareas = Array.from(getContainer().querySelectorAll("textarea")) as HTMLTextAreaElement[]
    await act(async () => {
      setFieldValue(textareas[0], "Updated preface")
      setFieldValue(textareas[1], "Updated dedication")
      await Promise.resolve()
    })
    const inputs = Array.from(getContainer().querySelectorAll('input:not([type="checkbox"]):not([type="file"])')) as HTMLInputElement[]
    await act(async () => {
      setFieldValue(inputs[0], "Indie Press")
      setFieldValue(inputs[2], "9780000000000")
      await Promise.resolve()
    })

    await click("Save novel settings")
    expect(booksApiMock.saveNovelSettings).toHaveBeenCalledWith("book-1", expect.objectContaining({
      preface: "Updated preface",
      front_matter: expect.objectContaining({ dedication: "Updated dedication" }),
      epub_metadata: expect.objectContaining({ publisher: "Indie Press", isbn: "9780000000000" }),
    }))
    expect(text()).toContain("Saved novel export settings.")

    await click("Preview export files")
    expect(booksApiMock.previewCharacterBibleVault).toHaveBeenCalledWith("book-1")
    expect(text()).toContain("Loaded the character bible file preview.")
    expect(text()).toContain("Characters/Mira.md")

    await click("Export character bible")
    expect(booksApiMock.exportCharacterBible).toHaveBeenCalledWith("book-1", "docx", "serif")
    expect(objectUrlMock).toHaveBeenCalled()
    expect(text()).toContain("Downloaded character bible as DOCX.")

    await click("Vault ZIP")
    await click("Export manuscript")
    expect(booksApiMock.exportManuscript).toHaveBeenCalledWith("book-1", "epub", "standard_manuscript", false, "serif", true)
    expect(text()).toContain("Downloaded manuscript as EPUB.")

    await click("Export novel")
    expect(booksApiMock.exportNovel).toHaveBeenCalledWith("book-1", "pdf", "standard_novel", true, "serif", expect.objectContaining({
      includeImageCaptions: false,
      previewChapters: 2,
    }))
    expect(text()).toContain("Downloaded first 2-chapter sample as PDF.")

    await click("Export notes ZIP")
    expect(booksApiMock.exportVaultNotes).toHaveBeenCalledWith("book-1")
    expect(text()).toContain("Downloaded notes workspace ZIP.")

    const fileInputs = Array.from(getContainer().querySelectorAll('input[type="file"]')) as HTMLInputElement[]
    const manuscriptFile = new File(["chapter"], "chapter-one.md", { type: "text/markdown" })
    const notesFile = new File(["notes"], "notes.zip", { type: "application/zip" })
    const worldFile = new File(["world"], "world.md", { type: "text/markdown" })
    await act(async () => {
      setInputFiles(fileInputs[0], [manuscriptFile])
      setInputFiles(fileInputs[1], [notesFile])
      setInputFiles(fileInputs[2], [worldFile])
      await Promise.resolve()
    })
    expect(text()).toContain("chapter-one.md")
    expect(text()).toContain("notes.zip")
    expect(text()).toContain("world.md")

    await click("Import manuscript files")
    expect(booksApiMock.importManuscript).toHaveBeenCalledWith("book-1", expect.objectContaining({
      files: [manuscriptFile],
      workType: "novel",
    }))
    expect(text()).toContain("Imported 1 chapter files into this book.")

    await click("Import notes ZIP")
    expect(booksApiMock.importVaultNotes).toHaveBeenCalledWith("book-1", notesFile)
    expect(text()).toContain("Imported notes.zip into the notes workspace.")

    await click("Import worldbuilding")
    expect(worldBuildingApiMock.uploadDocuments).toHaveBeenCalledWith("book-1", { files: [worldFile] })
    expect(text()).toContain("Imported 1 worldbuilding file.")

    await click("Export everything")
    await waitForText("Downloaded one ZIP with all manuscript, novel, character bible, and notes export files.")
    expect(booksApiMock.exportCharacterBible).toHaveBeenCalledTimes(5)
    expect(booksApiMock.exportManuscript).toHaveBeenCalledTimes(5)
    expect(booksApiMock.exportNovel).toHaveBeenCalledTimes(4)
    expect(text()).toContain("Downloaded one ZIP with all manuscript, novel, character bible, and notes export files.")
  })
})
