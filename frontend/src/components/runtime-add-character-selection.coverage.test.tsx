// @vitest-environment jsdom

import { act } from "react"
import { describe, expect, it, vi } from "vitest"

import {
  booksApiMock,
  click,
  firstField,
  flush,
  renderElement,
  setFieldValue,
  text,
  unmountCurrentRoot,
} from "./runtime-zero-components.test-utils"

import { AddCharacterFromSelection } from "@/components/characters/AddCharacterFromSelection"

describe("add-character selection runtime coverage", () => {
  it("creates characters from selected text and handles validation, cancel, and API errors", async () => {
    const onClose = vi.fn()
    const onCreated = vi.fn()
    await renderElement(
      <AddCharacterFromSelection
        bookId="book-1"
        selectedText={"  Mara   Vale  "}
        isDark
        firstChapter={4}
        open
        onClose={onClose}
        onCreated={onCreated}
      />,
    )

    expect(text()).toContain("Add character from selection")
    expect(firstField<HTMLInputElement>("input").value).toBe("Mara Vale")
    setFieldValue(firstField<HTMLSelectElement>("select"), "sc")
    setFieldValue(firstField<HTMLTextAreaElement>("textarea"), "Gate keeper.")
    await click("Create character")
    expect(booksApiMock.createCharacter).toHaveBeenCalledWith("book-1", {
      name: "Mara Vale",
      firstChapter: 4,
      role: "sc",
      description: "Gate keeper.",
    })
    expect(onCreated).toHaveBeenCalledWith(expect.objectContaining({ id: "char-new" }))
    expect(onClose).toHaveBeenCalled()

    unmountCurrentRoot()
    onClose.mockClear()
    onCreated.mockClear()
    await renderElement(
      <AddCharacterFromSelection
        bookId="book-1"
        selectedText="Theo"
        isDark={false}
        open
        onClose={onClose}
        onCreated={onCreated}
      />,
    )
    setFieldValue(firstField<HTMLInputElement>("input"), "")
    await act(async () => {
      firstField<HTMLInputElement>("input").dispatchEvent(
        new KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
      )
      await flush()
    })
    expect(text()).toContain("Character name is required.")

    setFieldValue(firstField<HTMLInputElement>("input"), "Theo")
    booksApiMock.createCharacter.mockRejectedValueOnce(new Error("duplicate"))
    await click("Create character")
    expect(text()).toContain("Could not create this character")

    await act(async () => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }))
      await flush()
    })
    expect(onClose).toHaveBeenCalled()

    unmountCurrentRoot()
    onClose.mockClear()
    await renderElement(
      <AddCharacterFromSelection
        bookId="book-1"
        selectedText="Lina"
        isDark={false}
        open
        onClose={onClose}
      />,
    )
    await click("Cancel")
    expect(onClose).toHaveBeenCalled()

    unmountCurrentRoot()
    await renderElement(
      <AddCharacterFromSelection
        bookId="book-1"
        selectedText="Hidden"
        isDark={false}
        open={false}
        onClose={onClose}
      />,
    )
    expect(text()).not.toContain("Hidden")
  })
})
