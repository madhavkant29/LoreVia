import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it } from "vitest"

import { ManuscriptSceneOrderStatus, type SceneOrderSaveState } from "./ManuscriptSceneOrderStatus"

let container: HTMLDivElement | null = null
let root: Root | null = null

describe("ManuscriptSceneOrderStatus", () => {
  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

  afterEach(() => {
    if (root) {
      act(() => root?.unmount())
    }
    container?.remove()
    container = null
    root = null
  })

  it.each([
    ["idle", false, "Drag the handle to reorder scenes"],
    ["idle", true, "Drop between scenes to place it"],
    ["saving", false, "Saving order..."],
    ["saved", false, "Order saved"],
    ["failed", false, "Could not save order"],
  ] as Array<[SceneOrderSaveState, boolean, string]>)("renders %s scene order state", (state, isDragging, label) => {
    const view = renderStatus(state, isDragging)
    expect(view.textContent).toContain(label)
  })
})

function renderStatus(state: SceneOrderSaveState, isDragging: boolean) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => {
    root?.render(<ManuscriptSceneOrderStatus isDark={false} isDragging={isDragging} state={state} />)
  })
  return container
}
