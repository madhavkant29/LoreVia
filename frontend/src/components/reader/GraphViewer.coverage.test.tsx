// @vitest-environment jsdom

import { act, type ReactElement } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const cytoscapeMock = vi.hoisted(() => vi.fn())

vi.mock("cytoscape", () => ({
  default: cytoscapeMock,
}))

import { GraphViewer } from "@/components/reader/GraphViewer"

let root: Root | null = null
let container: HTMLDivElement | null = null

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

async function flush() {
  await Promise.resolve()
  await new Promise((resolve) => window.setTimeout(resolve, 0))
  await Promise.resolve()
}

async function renderElement(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  await act(async () => {
    root?.render(element)
    await flush()
  })
}

function text() {
  return container?.textContent ?? ""
}

function buttons(label: string) {
  return Array.from(container?.querySelectorAll("button") ?? []).filter((node) =>
    node.textContent?.includes(label),
  )
}

async function click(label: string, index = 0) {
  const target = buttons(label)[index]
  if (!target) throw new Error(`Missing button: ${label}\n${text()}`)

  await act(async () => {
    target.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await flush()
  })
}

function makeStorage() {
  const store: Record<string, string> = {}
  return {
    clear: vi.fn(() => {
      Object.keys(store).forEach((key) => delete store[key])
    }),
    getItem: vi.fn((key: string) => store[key] ?? null),
    removeItem: vi.fn((key: string) => {
      delete store[key]
    }),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value
    }),
  }
}

function makeCytoscapeCore() {
  const callbacks: Record<string, Array<(event?: { target: { data: (key: string) => string } }) => void>> = {}
  const nodeList = [
    {
      id: () => "Story Vault/Characters/Mara.md",
      position: () => ({ x: 10, y: 20 }),
      length: 1,
      data: (key: string) => (key === "path" ? "Story Vault/Characters/Mara.md" : "Mara"),
      addClass: vi.fn().mockReturnThis(),
      removeClass: vi.fn().mockReturnThis(),
      connectedEdges: vi.fn(() => ({
        addClass: vi.fn().mockReturnThis(),
        removeClass: vi.fn().mockReturnThis(),
        connectedNodes: vi.fn(() => ({ removeClass: vi.fn().mockReturnThis() })),
      })),
    },
  ]
  const cy = {
    callbacks,
    destroy: vi.fn(),
    elements: vi.fn(() => ({
      addClass: vi.fn().mockReturnThis(),
      removeClass: vi.fn().mockReturnThis(),
    })),
    fit: vi.fn(),
    getElementById: vi.fn(() => nodeList[0]),
    layout: vi.fn(() => ({ run: vi.fn() })),
    nodes: vi.fn(() => ({ forEach: (fn: (node: (typeof nodeList)[number]) => void) => nodeList.forEach(fn) })),
    on: vi.fn((event: string, selectorOrCallback: string | ((event?: { target: { data: (key: string) => string } }) => void), maybeCallback?: (event?: { target: { data: (key: string) => string } }) => void) => {
      const callback = typeof selectorOrCallback === "function" ? selectorOrCallback : maybeCallback
      callbacks[event] = callbacks[event] ?? []
      if (callback) callbacks[event].push(callback)
    }),
    style: vi.fn(() => ({
      selector: vi.fn().mockReturnThis(),
      style: vi.fn().mockReturnThis(),
      update: vi.fn().mockReturnThis(),
    })),
    zoom: vi.fn((value?: unknown) => (value ? cy : 1)),
  }
  return cy
}

beforeEach(() => {
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: makeStorage(),
  })
  cytoscapeMock.mockReset().mockImplementation(makeCytoscapeCore)
})

afterEach(() => {
  if (root) {
    act(() => {
      root?.unmount()
    })
  }
  container?.remove()
  root = null
  container = null
  document.body.innerHTML = ""
})

describe("GraphViewer", () => {
  it("renders populated, local, command, storage, and empty states", async () => {
    await renderElement(
      <GraphViewer
        graph={{
          nodes: [
            { id: "Story Vault/Characters/Mara.md", path: "Story Vault/Characters/Mara.md", title: "Mara", folder: "Characters", link_count: 3 },
            { id: "Story Vault/Plot/Key.md", path: "Story Vault/Plot/Key.md", title: "Key", folder: "Plot", link_count: 1 },
          ],
          edges: [
            { source: "Story Vault/Characters/Mara.md", target: "Story Vault/Plot/Key.md", label: "links" },
          ],
        }}
        selectedPath="Story Vault/Characters/Mara.md"
        onOpenNote={vi.fn()}
        isDark
      />,
    )
    await act(flush)

    expect(text()).toContain("Graph View")
    expect(text()).toContain("2 notes | 1 links")
    expect(cytoscapeMock).toHaveBeenCalled()

    await click("+")
    await click("-")
    await click("Fit")
    await click("Local")
    expect(text()).toContain("Global")
    await click("Reset")
    expect(window.localStorage.removeItem).toHaveBeenCalled()

    const cy = cytoscapeMock.mock.results[0]?.value
    cy.callbacks.mouseover?.[0]?.({ target: { data: () => "Story Vault/Characters/Mara.md" } })
    cy.callbacks.mouseout?.[0]?.()
    cy.callbacks.dragfree?.[0]?.()
    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 220))
    })
    expect(window.localStorage.setItem).toHaveBeenCalled()

    root?.unmount()
    container?.remove()
    root = null
    container = null

    await renderElement(
      <GraphViewer
        graph={{ nodes: [], edges: [] }}
        selectedPath={null}
        onOpenNote={vi.fn()}
        isDark={false}
      />,
    )
    expect(text()).toContain("Add a few wiki-links")
  })
})
