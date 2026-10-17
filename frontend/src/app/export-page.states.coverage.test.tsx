// @vitest-environment jsdom

import { describe, expect, it } from "vitest"

import {
  ExportStudioPage,
  book,
  booksApiMock,
  cleanupExportPage,
  click,
  renderPage,
  text,
  waitForText,
} from "./export-page.test-utils"

describe("ExportStudioPage states", () => {
  it("shows loading and error/fallback states", async () => {
    booksApiMock.get.mockResolvedValueOnce(null)

    await renderPage(<ExportStudioPage />)
    await waitForText("This project could not be loaded.")

    cleanupExportPage()

    booksApiMock.get.mockResolvedValueOnce(book)
    booksApiMock.getWriterWorkspace.mockResolvedValueOnce(null)
    booksApiMock.exportCharacterBible.mockRejectedValueOnce(new Error("fail"))
    booksApiMock.previewCharacterBibleVault.mockRejectedValueOnce(new Error("fail"))

    await renderPage(<ExportStudioPage />)
    await waitForText("Files & Export")

    await click("Character bible")
    await click("Preview export files")
    expect(text()).toContain("Could not load the vault preview.")

    await click("Export character bible")
    expect(text()).toContain("The export could not be completed.")
  })
})
