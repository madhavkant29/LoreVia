// @vitest-environment jsdom

import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, expect, it, vi } from "vitest"

import {
  WorkspaceEmptyState,
  WorkspaceHeader,
  WorkspaceMetric,
  WorkspacePage,
  WorkspacePanel,
  WorkspaceTabButton,
} from "./Workspace"

let root: Root | null = null
let container: HTMLDivElement | null = null

afterEach(() => {
  act(() => root?.unmount())
  container?.remove()
  root = null
  container = null
})

it("renders workspace primitives across tones, accents, and optional content", () => {
  const onClick = vi.fn()
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => {
    root?.render(
      <WorkspacePage className="custom-page">
        <WorkspaceHeader eyebrow="Draft" title="Atlas" description="Revise the manuscript." actions={<button>Export</button>} meta={<span>Saved</span>} />
        <WorkspacePanel tone="strong" className="strong"><span>Strong panel</span></WorkspacePanel>
        <WorkspacePanel tone="subtle"><span>Subtle panel</span></WorkspacePanel>
        <WorkspacePanel><span>Default panel</span></WorkspacePanel>
        <WorkspaceMetric label="Words" value="1,250" note="Today" accent="accent" />
        <WorkspaceMetric label="Scenes" value="8" accent="success" />
        <WorkspaceMetric label="Flags" value="2" accent="warning" />
        <WorkspaceMetric label="Chapters" value="4" />
        <WorkspaceEmptyState title="No notes" body="Create the first note." />
        <WorkspaceTabButton active className="extra" onClick={onClick}>Overview</WorkspaceTabButton>
      </WorkspacePage>,
    )
  })

  expect(container.textContent).toContain("Draft")
  expect(container.textContent).toContain("Revise the manuscript.")
  expect(container.querySelector(".app-panel--strong")).not.toBeNull()
  expect(container.querySelector(".app-panel--subtle")).not.toBeNull()
  expect(container.querySelector(".app-stat--accent")).not.toBeNull()
  expect(container.querySelector(".app-stat--success")).not.toBeNull()
  expect(container.querySelector(".app-stat--warning")).not.toBeNull()
  const tab = Array.from(container.querySelectorAll("button")).find((button) => button.textContent === "Overview") as HTMLButtonElement
  expect(tab.className).toContain("app-tab--active")
  act(() => tab.click())
  expect(onClick).toHaveBeenCalledOnce()
})

it("omits optional workspace header and metric sections", () => {
  container = document.createElement("div")
  root = createRoot(container)
  act(() => root?.render(<><WorkspaceHeader eyebrow="Plan" title="Outline" /><WorkspaceMetric label="Words" value="0" /></>))
  expect(container.textContent).toBe("PlanOutlineWords0")
})
