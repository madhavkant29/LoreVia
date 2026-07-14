// @vitest-environment jsdom

import { act } from "react"
import { describe, expect, it, vi } from "vitest"

import {
  MarkdownPreview,
  flush,
  getContainer,
  renderElement,
  text,
} from "./runtime-ui-components.test-utils"

describe("runtime MarkdownPreview", () => {
  it("renders headings, code, links, embeds, cycles, and note clicks", async () => {
    const onOpenNote = vi.fn()
    await renderElement(
      <MarkdownPreview
        content={"# Heading\n\n**Bold** and *italic* with `code`.\n- Item\n[Site](https://example.com)\n[[Mara|Mara]]\n![[Gate]]\n![[Mara]]"}
        isDark={false}
        currentPath="Characters/Mara.md"
        notes={[
          { path: "Places/Gate.md", content: "Gate links back to [[Mara]]." },
          { path: "Characters/Mara.md", content: "Mara note." },
        ] as never}
        onOpenNote={onOpenNote}
      />,
    )

    expect(getContainer().querySelector("h1")?.textContent).toBe("Heading")
    expect(getContainer().querySelector("strong")?.textContent).toBe("Bold")
    expect(getContainer().querySelector("code")?.textContent).toBe("code")
    expect(text()).toContain("Embedded note")
    const vaultLink = Array.from(getContainer().querySelectorAll("a")).find((node) => node.getAttribute("href")?.startsWith("#vault-note=Mara"))
    expect(vaultLink).toBeTruthy()
    await act(async () => {
      vaultLink?.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }))
      await flush()
    })
    expect(onOpenNote).toHaveBeenCalledWith("Mara")
  })
})
