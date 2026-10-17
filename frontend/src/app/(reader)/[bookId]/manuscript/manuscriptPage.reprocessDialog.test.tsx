// @vitest-environment jsdom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { describe, expect, it } from "vitest"

import { ManuscriptReprocessDialog } from "./manuscriptPage.reprocessDialog"

describe("ManuscriptReprocessDialog", () => {
  it("explains reserve-then-settle processed-word accounting", () => {
    const container = document.createElement("div")
    document.body.appendChild(container)
    const root = createRoot(container)

    act(() => {
      root.render(
        <ManuscriptReprocessDialog
          isDark={false}
          reprocessing={false}
          onCancel={() => undefined}
          onConfirm={() => undefined}
        />
      )
    })

    const dialog = document.body.querySelector('[role="dialog"]')
    expect(dialog?.textContent).toContain("full word count is reserved first")
    expect(dialog?.textContent).toContain("only chapters that finish successfully are charged")
    expect(dialog?.textContent).toContain("Reserve words and reprocess")

    act(() => root.unmount())
    container.remove()
  })
})
