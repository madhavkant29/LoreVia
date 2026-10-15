// @vitest-environment jsdom

import { describe, expect, it } from "vitest"
import {
  booksApiMock,
  click,
  firstField,
  getCharactersPageContainer,
  readerApiMock,
  renderCharactersPage,
  setFieldValue,
  waitForText,
} from "./characters-page.test-utils"

describe("CharactersPage", () => {
  it("renders the loaded author character workspace and relationship tab", async () => {
    await renderCharactersPage()
    await waitForText("Character workspace")
    await waitForText("Mira")
    await waitForText("Joren")
    expect(getCharactersPageContainer()?.textContent).toContain("silver key scar")

    await click("Relationships tab")
    await waitForText("Relationship graph rendered")
  })

  it("drives review queue and duplicate review actions", async () => {
    await renderCharactersPage()
    await waitForText("Character workspace")

    await click("Review queue")
    await waitForText("Grounded review workspace")
    await waitForText("Council")
    await click("Find evidence")
    await waitForText("Mira gives Joren the key.")
    await click("Mark as place")
    expect(booksApiMock.markCharacterCandidatePlace).toHaveBeenCalledWith("book-1", "candidate-1")
    await click("Reject candidate")
    expect(booksApiMock.rejectCharacterCandidate).toHaveBeenCalledWith("book-1", "candidate-1")

    await click("Open menu")
    await click("Review duplicate suggestions")
    await waitForText("Merge suggestion")
    await click("Details")
    await waitForText("Embedding similarity: 81%")
    await click("Compare evidence")
    await waitForText("Evidence panel")
    expect(readerApiMock.search).toHaveBeenCalledWith("book-1", expect.stringContaining("Mira"), 12)

    await click("Open menu")
    await click("Review duplicate suggestions")
    await waitForText("Merge records")
    await click("Keep separate")
    expect(booksApiMock.dismissDuplicateSuggestion).toHaveBeenCalledWith("book-1", "dup-1")

    await click("Start manual merge")
    await waitForText("Manual review")
    await click("Merge records")
    expect(booksApiMock.mergeCharacters).toHaveBeenCalledWith("book-1", { primaryId: "char-1", secondaryId: "char-2" })
  })

  it("drives character repair and relationship repair actions", async () => {
    await renderCharactersPage()
    await waitForText("Character workspace")

    await click("Open menu")
    await click("Open repair workspace")
    await waitForText("Book reprocess preview")
    await click("Refresh preview")
    await click("Apply repair plan")
    await click("Repair relationship timelines")
    expect(booksApiMock.applyCharacterReprocess).toHaveBeenCalledWith("book-1", {
      allowDemoteObviousNoise: true,
      allowMergeSafePairs: true,
    })
    expect(booksApiMock.repairRelationships).toHaveBeenCalledWith("book-1")
  })

  it("creates and edits characters", async () => {
    await renderCharactersPage()
    await waitForText("Character workspace")

    await click("Add character")
    await waitForText("Create character")
    setFieldValue(firstField<HTMLInputElement>("input"), "Lina")
    await click("Create character")
    expect(booksApiMock.createCharacter).toHaveBeenCalledWith("book-1", expect.objectContaining({ name: "Lina" }))

    await click("Overview tab")
    await click("Character actions")
    await click("Edit details")
    await waitForText("Save changes")
    setFieldValue(firstField<HTMLInputElement>("input"), "Mira Revised")
    await click("Save changes")
    expect(booksApiMock.updateCharacter).toHaveBeenCalledWith("book-1", expect.any(String), expect.objectContaining({ name: "Mira Revised" }))

    expect(getCharactersPageContainer()?.textContent).toContain("Mira")
  })
})
