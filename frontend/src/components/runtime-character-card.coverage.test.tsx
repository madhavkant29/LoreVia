// @vitest-environment jsdom

import { act } from "react"
import { describe, expect, it, vi } from "vitest"

import {
  characterFixture,
  click,
  confirmMock,
  firstField,
  flush,
  getContainer,
  renderElement,
  setFieldValue,
  text,
} from "./runtime-zero-components.test-utils"

import { CharacterCard } from "@/components/characters/CharacterCard"

describe("character card runtime coverage", () => {
  it("expands cards and exercises edit, share, export, delete, keyboard, and advanced paths", async () => {
    const onUpdated = vi.fn()
    const onDeleted = vi.fn()
    await renderElement(
      <CharacterCard
        character={{ ...characterFixture, book_id: "book-1" } as never}
        bookId="book-1"
        editable
        onUpdated={onUpdated}
        onDeleted={onDeleted}
        theme="dark"
      />,
    )

    const card = getContainer()?.querySelector('[role="button"]')
    if (!card) throw new Error("Missing character card")
    await act(async () => {
      card.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }))
      await flush()
    })
    expect(text()).toContain("Advanced details")
    await click("Edit")
    setFieldValue(firstField<HTMLInputElement>("input"), "Mara Bright")
    await click("Save edits")
    expect(onUpdated).toHaveBeenCalledWith(expect.objectContaining({ name: "Mara Bright" }))
    await click("Share")
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(expect.stringContaining("/share/mara"))
    await click("Edit")
    await click("Export PDF")
    expect(URL.createObjectURL).toHaveBeenCalled()
    await click("Open")
    expect(text()).toContain("Archetype")
    await click("Delete")
    expect(confirmMock).toHaveBeenCalled()
    expect(onDeleted).toHaveBeenCalledWith("char-1")
  })
})
