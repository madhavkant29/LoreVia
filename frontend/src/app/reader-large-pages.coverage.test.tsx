// @vitest-environment jsdom

import { describe, expect, it } from "vitest"
import {
  booksApiMock,
  changeFieldValue,
  clickButtonWithSibling,
  clickText,
  clickTextIfExists,
  flushUi,
  getReaderLargePagesContainer,
  renderManuscriptPage,
} from "./reader-large-pages.test-utils"

describe("large reader runtime pages", () => {
  it("renders the loaded manuscript workspace and exercises scene/runtime controls", async () => {
    renderManuscriptPage()
    await flushUi()
    await flushUi()

    const container = getReaderLargePagesContainer()
    await clickText("Outline")
    expect(container?.textContent).toContain("The Ember Gate")
    expect(container?.textContent).toContain("Chapters")
    expect(container?.textContent).toContain("Chapter 1")
    expect(container?.textContent).toContain("Draft")

    await clickText("Insert")
    expect(booksApiMock.getSceneInsertion).toHaveBeenCalledWith("book-1", "scene-1", 2, "end", false)

    await clickButtonWithSibling("Edit", "Delete")
    await clickText("Change scene draft")
    await clickText("Name scene version")
    await clickText("Snapshot scene dialog")
    await clickText("Compare scene version")
    await clickText("Restore scene version")
    expect(booksApiMock.createSceneSnapshot).toHaveBeenCalledWith("book-1", "scene-1", "Scene milestone")
    expect(booksApiMock.getSceneVersionDetail).toHaveBeenCalledWith("book-1", "scene-version-1")
    expect(booksApiMock.restoreSceneVersion).toHaveBeenCalledWith("book-1", "scene-version-1")
    await clickText("Save scene dialog")
    expect(booksApiMock.saveScene).toHaveBeenCalled()
    await clickText("Reprocess chapter")
    expect(booksApiMock.reprocessChapter).toHaveBeenCalled()

    await clickText("Plan")
    expect(container?.textContent).toContain("runtime panel")

    await clickText("Analysis")
    expect(container?.textContent).toContain("runtime panel")
    await clickText("Toggle left rail")
    await clickText("Toggle page setup")
    await clickText("Toggle search tools")
    await clickText("Replace chapter text")
  }, 15_000)

  it("covers write mode export, snapshots, chapter creation, and full-book saving", async () => {
    renderManuscriptPage()
    await flushUi()
    await flushUi()

    const container = getReaderLargePagesContainer()
    await clickText("Write")
    await clickText("Focus mode")
    await clickText("Editor settings")
    await clickText("On")
    await clickText("Submission preset")
    await clickText("Include TOC")
    await clickText("Print manuscript")
    expect(window.print).toHaveBeenCalled()
    await clickText("Export manuscript")
    await clickText("Compile manuscript dialog")
    expect(booksApiMock.exportManuscript).toHaveBeenCalledWith("book-1", "pdf", expect.any(String), expect.any(Boolean), "serif", true)
    await clickText("Exit focus")

    await clickText("Outline")
    await clickText("Create chapter snapshot")
    await clickText("Preview chapter snapshot")
    await clickText("Restore chapter snapshot")
    expect(booksApiMock.createChapterSnapshot).toHaveBeenCalled()
    expect(booksApiMock.getChapterVersionDetail).toHaveBeenCalledWith("book-1", "version-1")
    expect(booksApiMock.restoreChapterVersion).toHaveBeenCalledWith("book-1", "version-1")
    await flushUi()
    expect(booksApiMock.getRestoreStatus).toHaveBeenCalledWith(
      "book-1",
      "version-1",
      expect.any(AbortSignal),
    )

    await clickText("Save now")
    expect(booksApiMock.saveChapterContent).toHaveBeenCalledWith(
      "book-1",
      2,
      expect.objectContaining({ expectedContentVersion: 3, clientMutationId: expect.any(String) }),
    )

    await clickText("New chapter")
    expect(container?.textContent).toContain("Chapter 3")
    await clickText("Save now")

    await clickText("Full book")
    expect(container?.textContent).toContain("Full-book mode")
    await clickText("Save all chapters")
  }, 15_000)

  it("covers planning, note injection, annotations, and insight actions", async () => {
    renderManuscriptPage()
    await flushUi()
    await flushUi()

    const container = getReaderLargePagesContainer()
    await clickText("Plan")
    await clickText("Save goals")
    await clickText("Add corkboard card")
    await clickText("Apply chapter template")
    await clickText("Save templates")
    expect(booksApiMock.saveBookNote).toHaveBeenCalledWith("book-1", expect.objectContaining({ title: "Template: Reversal beat" }))
    expect(booksApiMock.updateWriterWorkspace).toHaveBeenCalled()

    await clickText("Write")
    await clickText("Inspector")
    await clickText("Open notes pane")
    await clickText("Inject note")
    await clickText("Open character card")
    expect(booksApiMock.saveBookNote).toHaveBeenCalled()

    await clickText("Analysis")
    expect(container?.textContent).toContain("Annotations")
    expect(container?.textContent).toContain("Check color.")
    await clickText("Use selection")
    expect(container?.textContent).toContain("Selected passage")
    const annotationText = container?.querySelector('textarea[aria-label="Inline annotation"]') as HTMLTextAreaElement
    expect(annotationText).toBeTruthy()
    await changeFieldValue(annotationText, "Anchor this color change.")
    await clickText("Private")
    await clickText("Save annotation")
    expect(booksApiMock.saveManuscriptAnnotation).toHaveBeenCalledWith("book-1", expect.objectContaining({
      category: "general",
      visibility: "private",
      quote: "amber light",
      comment: "Anchor this color change.",
    }))

    await clickText("Resolve")
    await clickText("Delete")
    expect(booksApiMock.saveManuscriptAnnotation).toHaveBeenCalledWith("book-1", expect.objectContaining({
      annotationId: "annotation-new",
      status: "resolved",
    }))
    expect(booksApiMock.deleteManuscriptAnnotation).toHaveBeenCalledWith("book-1", "annotation-1")

    await clickText("Change rich text")
    await clickText("Save chapter note")
    await clickText("Save to workspace notes")

    await clickText("Insights")
    expect(container?.textContent).toContain("Continuity check")
    await clickTextIfExists("Save as note")
    await clickTextIfExists("Download continuity report")
  }, 15_000)

  it("covers character editing from the manuscript workspace", async () => {
    renderManuscriptPage()
    await flushUi()
    await flushUi()

    const container = getReaderLargePagesContainer()
    await clickText("Write")
    await clickText("Inspector")
    await clickText("Open character card")
    await clickText("Analysis")
    await clickText("Insights")
    await clickText("Characters")
    await clickText("Edit card")
    const cardFields = Array.from(container?.querySelectorAll("input, textarea") ?? []) as Array<HTMLInputElement | HTMLTextAreaElement>
    const descriptionField = cardFields.find((field) => field.value === "Mara guards the gate.") as HTMLTextAreaElement
    const arcField = cardFields.find((field) => field.value === "She learns to trust.") as HTMLTextAreaElement
    const tagsField = cardFields.find((field) => field.value === "guarded") as HTMLInputElement
    const motivationsField = cardFields.find((field) => field.value === "protect the gate") as HTMLInputElement
    const fearsField = cardFields.find((field) => field.value === "betrayal") as HTMLInputElement
    expect(descriptionField).toBeTruthy()
    expect(arcField).toBeTruthy()
    expect(tagsField).toBeTruthy()
    expect(motivationsField).toBeTruthy()
    expect(fearsField).toBeTruthy()
    await changeFieldValue(descriptionField, "Mara protects the gate and the town.")
    await changeFieldValue(arcField, "She chooses trust over control.")
    await changeFieldValue(tagsField, "guarded, decisive")
    await changeFieldValue(motivationsField, "protect the gate, save Theo")
    await changeFieldValue(fearsField, "betrayal, failure")
    await clickButtonWithSibling("Save", "Cancel")
    expect(booksApiMock.updateCharacter).toHaveBeenCalledWith("book-1", "char-1", {
      arcSummary: "She chooses trust over control.",
      description: "Mara protects the gate and the town.",
      personalityTags: ["guarded", "decisive"],
      motivations: ["protect the gate", "save Theo"],
      fears: ["betrayal", "failure"],
    })
    await clickText("Save as note")

    await clickText("Write")
  }, 15_000)
})
