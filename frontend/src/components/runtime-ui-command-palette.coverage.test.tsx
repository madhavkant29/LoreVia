// @vitest-environment jsdom

import { act } from "react"
import { describe, expect, it } from "vitest"

import {
  CommandPalette,
  cleanupRuntimeUi,
  flush,
  pushMock,
  queryState,
  renderElement,
  setInputValue,
  text,
} from "./runtime-ui-components.test-utils"

describe("runtime CommandPalette", () => {
  it("opens with keyboard, filters actions, navigates, and shows loading and empty states", async () => {
    await renderElement(<CommandPalette />)
    expect(text()).toBe("")

    await act(async () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true, bubbles: true }))
      await flush()
    })
    expect(text()).toContain("Command palette")
    expect(text()).toContain("Open Library")
    expect(text()).toContain("The Lantern Gate")

    setInputValue('input[aria-label="Search commands"]', "manuscript")
    expect(text()).toContain("Open manuscript: The Lantern Gate")
    await act(async () => {
      document.querySelector("input")?.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }))
      await flush()
    })
    expect(pushMock).toHaveBeenCalledWith("/the-lantern-gate--book-1/manuscript")

    cleanupRuntimeUi()
    queryState.value = { data: [], isLoading: true }
    await renderElement(<CommandPalette />)
    await act(async () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }))
      await flush()
    })
    expect(text()).toContain("Loading project actions")

    queryState.value = { data: [], isLoading: false }
    setInputValue('input[aria-label="Search commands"]', "zz-no-match")
    await act(flush)
    expect(text()).toContain("No matching commands")
    await act(async () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }))
      await flush()
    })
    expect(text()).toBe("")
  })
})
