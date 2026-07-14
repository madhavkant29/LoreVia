// @vitest-environment jsdom

import { act } from "react"
import { describe, expect, it, vi } from "vitest"

import {
  ManuscriptExportMenu,
  ManuscriptModeSwitch,
  clickByText,
  getContainer,
  renderElement,
} from "./overviewCards.test-utils"

describe("overview manuscript controls", () => {
  it("supports manuscript export menu interactions", async () => {
    const onToggle = vi.fn()
    const onPresetChange = vi.fn()
    const onIncludeTableOfContentsChange = vi.fn()
    const onPrint = vi.fn()
    const onCompile = vi.fn()

    await renderElement(
      <ManuscriptExportMenu
        isDark={false}
        open
        activePreset="standard_manuscript"
        exporting={null}
        includeTableOfContents={false}
        onToggle={onToggle}
        onPresetChange={onPresetChange}
        onIncludeTableOfContentsChange={onIncludeTableOfContentsChange}
        onPrint={onPrint}
        onCompile={onCompile}
      />,
    )

    clickByText("Export")
    expect(onToggle).toHaveBeenCalledTimes(1)

    const select = getContainer().querySelector("select")
    act(() => {
      select!.value = "trade_paperback"
      select!.dispatchEvent(new Event("change", { bubbles: true }))
    })
    const checkbox = getContainer().querySelector("input[type='checkbox']")
    act(() => {
      checkbox!.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })
    clickByText("Print")
    clickByText("Compile Word")
    clickByText("Compile submission PDF")

    expect(onPresetChange).toHaveBeenCalledWith("trade_paperback")
    expect(onIncludeTableOfContentsChange).toHaveBeenCalledWith(true)
    expect(onPrint).toHaveBeenCalledTimes(1)
    expect(onCompile).toHaveBeenCalledWith("docx")
    expect(onCompile).toHaveBeenCalledWith("pdf")
  })

  it("supports manuscript mode switching", async () => {
    const onSelect = vi.fn()

    await renderElement(
      <ManuscriptModeSwitch
        isDark={false}
        options={["chapter", "book"] as const}
        selected="chapter"
        onSelect={onSelect}
        renderLabel={(value) => value === "chapter" ? "Chapter" : "Book"}
      />,
    )

    expect(getContainer().querySelector("[aria-pressed='true']")?.textContent).toBe("Chapter")
    clickByText("Book")
    expect(onSelect).toHaveBeenCalledWith("book")
  })
})
