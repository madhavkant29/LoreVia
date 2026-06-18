// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const readerApiMock = vi.hoisted(() => ({
  getRelationships: vi.fn(),
}))
const booksApiMock = vi.hoisted(() => ({
  updateRelationship: vi.fn(),
  deleteRelationship: vi.fn(),
}))
const cytoscapeMock = vi.hoisted(() => vi.fn())

type FakeHandler = (event: { target: unknown }) => void

class FakeElement {
  private readonly handlers: Record<string, FakeHandler[]> = {}

  constructor(private readonly payload: Record<string, unknown>) {}

  data(key?: string) {
    return key ? this.payload[key] : this.payload
  }

  id() {
    return String(this.payload.id)
  }

  position() {
    return { x: Number(this.payload.x ?? 100), y: Number(this.payload.y ?? 100) }
  }

  nonempty() {
    return true
  }

  empty() {
    return false
  }

  select() {
    return this
  }

  unselect() {
    return this
  }

  on(eventName: string, handler: FakeHandler) {
    this.handlers[eventName] = [...(this.handlers[eventName] ?? []), handler]
  }

  emit(eventName: string) {
    ;(this.handlers[eventName] ?? []).forEach((handler) => handler({ target: this }))
  }
}

class EmptyElement {
  data() {
    return {}
  }

  nonempty() {
    return false
  }

  empty() {
    return true
  }

  select() {
    return this
  }

  emit() {}
}

class FakeCollection extends Array<FakeElement> {
  nonempty() {
    return this.length > 0
  }

  empty() {
    return this.length === 0
  }

  data(key?: string) {
    return this[0]?.data(key)
  }

  emit(eventName: string) {
    this[0]?.emit(eventName)
  }
}

class FakeCy {
  readonly nodesList: FakeElement[]
  readonly edgesList: FakeElement[]
  private readonly rootHandlers: Record<string, FakeHandler[]> = {}
  private readonly nodeHandlers: Record<string, FakeHandler[]> = {}
  private readonly edgeHandlers: Record<string, FakeHandler[]> = {}
  private zoomValue = 1
  private isDestroyed = false

  constructor(options: { elements?: Array<{ data: Record<string, unknown> }> }) {
    const elements = options.elements ?? []
    this.nodesList = elements
      .filter((element) => !element.data.source && !element.data.target)
      .map((element) => new FakeElement(element.data))
    this.edgesList = elements
      .filter((element) => element.data.source && element.data.target)
      .map((element) => new FakeElement(element.data))
  }

  userPanningEnabled() {}

  userZoomingEnabled() {}

  boxSelectionEnabled() {}

  on(eventName: string, selectorOrHandler: string | FakeHandler, handler?: FakeHandler) {
    if (selectorOrHandler === "node" && handler) {
      this.nodeHandlers[eventName] = [...(this.nodeHandlers[eventName] ?? []), handler]
      this.nodesList.forEach((node) => node.on(eventName, handler))
      return
    }
    if (selectorOrHandler === "edge" && handler) {
      this.edgeHandlers[eventName] = [...(this.edgeHandlers[eventName] ?? []), handler]
      this.edgesList.forEach((edge) => edge.on(eventName, handler))
      return
    }
    if (typeof selectorOrHandler === "function") {
      this.rootHandlers[eventName] = [...(this.rootHandlers[eventName] ?? []), selectorOrHandler]
    }
  }

  emit(eventName: string, args?: Array<{ target: unknown }>) {
    const event = args?.[0] ?? { target: this }
    ;(this.rootHandlers[eventName] ?? []).forEach((handler) => handler(event))
  }

  getElementById(id: string) {
    return this.nodesList.find((node) => node.id() === id)
      ?? this.edgesList.find((edge) => edge.id() === id)
      ?? new EmptyElement()
  }

  nodes() {
    return this.nodesList
  }

  edges() {
    const collection = new FakeCollection(...this.edgesList)
    return collection
  }

  elements() {
    return { unselect: vi.fn() }
  }

  layout() {
    return { run: vi.fn() }
  }

  fit() {}

  animate() {}

  width() {
    return 840
  }

  height() {
    return 560
  }

  zoom(value?: { level: number }) {
    if (value) {
      this.zoomValue = value.level
    }
    return this.zoomValue
  }

  destroyed() {
    return this.isDestroyed
  }

  destroy() {
    this.isDestroyed = true
  }
}

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))
vi.mock("cytoscape", () => ({ default: cytoscapeMock }))
vi.mock("@/lib/api/reader", () => ({ readerApi: readerApiMock }))
vi.mock("@/lib/api/books", () => ({ booksApi: booksApiMock }))

import { RelationshipGraph } from "./RelationshipGraph"
import { graphLabelKey, graphStorageKey } from "./relationshipGraphDisplay"

let root: Root | null = null
let container: HTMLDivElement | null = null
let queryClient: QueryClient | null = null
const localStorageStore: Record<string, string> = {}
const localStorageMock = {
  getItem: vi.fn((key: string) => localStorageStore[key] ?? null),
  setItem: vi.fn((key: string, value: string) => {
    localStorageStore[key] = value
  }),
  removeItem: vi.fn((key: string) => {
    delete localStorageStore[key]
  }),
  clear: vi.fn(() => {
    Object.keys(localStorageStore).forEach((key) => delete localStorageStore[key])
  }),
}

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const graphData = {
  nodes: [
    {
      id: "mira",
      name: "Mira Vale",
      role: "protagonist",
      aliases: ["Captain Vale"],
      description: "A gate captain with a hidden oath.",
      arc_summary: "Learns to trust the crew.",
      personality_tags: ["precise", "guarded"],
      motivations: ["protect the gate"],
      fears: ["failing the city"],
      first_chapter: 1,
      mention_count: 42,
      visibility_score: 9,
      is_manual: true,
      graph_visibility_override: "include",
    },
    {
      id: "joren",
      name: "Joren Ash",
      role: "mentor",
      aliases: [],
      description: "Knows the old route.",
      first_chapter: 2,
      mention_count: 18,
      visibility_score: 6,
      is_manual: false,
      graph_visibility_override: null,
    },
    {
      id: "sera",
      name: "Sera Moon",
      role: "rival",
      aliases: [],
      description: "Wants the gate sealed.",
      first_chapter: 3,
      mention_count: 9,
      visibility_score: 4,
      is_manual: false,
      graph_visibility_override: null,
    },
  ],
  edges: [
    {
      id: "rel-1",
      source: "mira",
      target: "joren",
      type: "mentor",
      description: "Joren trains Mira in old gate law.",
      sentiment: 0.5,
      from_chapter: 2,
      to_chapter: null,
      status: "ongoing",
      shared_labels: ["mentor"],
      character_a_to_b_labels: ["student"],
      character_b_to_a_labels: ["teacher"],
      label_evidence: [{ excerpt: "Joren corrected her stance." }],
    },
    {
      id: "rel-2",
      source: "mira",
      target: "sera",
      type: "rival",
      description: "Sera challenges Mira's command.",
      sentiment: -0.6,
      from_chapter: 4,
      to_chapter: 6,
      status: "ended",
      shared_labels: ["rival"],
      character_a_to_b_labels: [],
      character_b_to_a_labels: [],
      label_evidence: [],
    },
  ],
}

async function renderGraph(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  queryClient = client

  await act(async () => {
    root?.render(<QueryClientProvider client={client}>{element}</QueryClientProvider>)
    await Promise.resolve()
    await Promise.resolve()
  })
}

async function flush() {
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
  })
}

async function waitForText(expected: string) {
  for (let index = 0; index < 20; index += 1) {
    if (text().includes(expected)) return
    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 0))
    })
  }
  throw new Error(`Expected text not found: ${expected}. Saw: ${text()}`)
}

function text() {
  return container?.textContent ?? ""
}

function clickButton(label: string) {
  const button = Array.from(container?.querySelectorAll("button") ?? []).find((item) =>
    item.textContent?.includes(label) || item.getAttribute("aria-label") === label
  )
  if (!button) throw new Error(`Missing button: ${label}`)
  act(() => {
    button.dispatchEvent(new MouseEvent("click", { bubbles: true }))
  })
}

function setFieldValue(field: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement, value: string) {
  const prototype =
    field instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : field instanceof HTMLInputElement
        ? HTMLInputElement.prototype
        : HTMLSelectElement.prototype
  const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set
  setter?.call(field, value)
  field.dispatchEvent(new Event(field instanceof HTMLSelectElement ? "change" : "input", { bubbles: true }))
}

function graphHandle() {
  return (window as typeof window & {
    __LOREVIA_RELATIONSHIP_GRAPH__?: {
      selectNode: (id: string) => void
      selectEdge: (id: string) => void
      clearSelection: () => void
    }
  }).__LOREVIA_RELATIONSHIP_GRAPH__
}

beforeEach(() => {
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: localStorageMock,
  })
  window.localStorage.clear()
  cytoscapeMock.mockImplementation((options) => new FakeCy(options))
  readerApiMock.getRelationships.mockResolvedValue(graphData)
  booksApiMock.updateRelationship.mockResolvedValue({
    rel_type: "ally",
    description: "Mira and Joren choose trust.",
    sentiment: 0.7,
    from_chapter: 2,
    to_chapter: 5,
    shared_labels: ["loyal_friend"],
    character_a_to_b_labels: ["student"],
    character_b_to_a_labels: ["teacher"],
    label_evidence: [],
  })
  booksApiMock.deleteRelationship.mockResolvedValue({})
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
  queryClient?.clear()
  queryClient = null
  document.body.innerHTML = ""
  vi.clearAllMocks()
})

describe("RelationshipGraph", () => {
  it("loads relationship data and supports graph filtering, selection, labels, and corrections", async () => {
    const onSelectCharacterId = vi.fn()
    const onGraphDataChange = vi.fn()

    await renderGraph(
      <RelationshipGraph
        bookId="book-1"
        upToChapter={7}
        authorMode
        theme="dark"
        onSelectCharacterId={onSelectCharacterId}
        onGraphDataChange={onGraphDataChange}
      />,
    )
    await flush()
    await waitForText("3 characters")

    expect(readerApiMock.getRelationships).toHaveBeenCalledWith("book-1", 7, {
      includeInactive: false,
      include: "nodes,edges",
    })
    expect(text()).toContain("3 characters")
    expect(text()).toContain("2 connections")
    expect(onGraphDataChange).toHaveBeenCalledWith(graphData)

    const filter = container?.querySelector('select[aria-label="Filter relationships"]') as HTMLSelectElement
    await act(async () => {
      setFieldValue(filter, "mentor")
      await Promise.resolve()
    })
    expect(text()).toContain("1 connections")

    await act(async () => {
      graphHandle()?.selectNode("mira")
      await Promise.resolve()
    })
    expect(onSelectCharacterId).toHaveBeenCalledWith("mira")
    expect(text()).toContain("Mira Vale")
    expect(text()).toContain("forced visible")
    expect(text()).toContain("A gate captain with a hidden oath.")

    const labelInput = container?.querySelector("input") as HTMLInputElement
    await act(async () => {
      setFieldValue(labelInput, "Captain Mira")
      await Promise.resolve()
    })
    expect(window.localStorage.getItem(graphLabelKey("book-1"))).toContain("Captain Mira")

    clickButton("Reset to canonical name")
    expect(window.localStorage.getItem(graphLabelKey("book-1"))).not.toContain("Captain Mira")

    clickButton("Center node")
    clickButton("Grid")
    clickButton("Zoom in")
    clickButton("Zoom out")
    clickButton("Reset zoom")
    clickButton("Fit")
    clickButton("Reset layout")
    expect(window.localStorage.getItem(graphStorageKey("book-1", 7))).toBeNull()

    await act(async () => {
      graphHandle()?.selectEdge("rel-1")
      await Promise.resolve()
    })
    expect(text()).toContain("Joren trains Mira in old gate law.")
    expect(text()).toContain("Strongly positive")
    expect(text()).toContain("Author correction")

    const note = Array.from(container?.querySelectorAll("textarea") ?? [])[0]
    await act(async () => {
      setFieldValue(note, "Mira and Joren choose trust.")
      await Promise.resolve()
    })
    await act(async () => {
      clickButton("Save correction")
      await Promise.resolve()
      await Promise.resolve()
    })
    expect(booksApiMock.updateRelationship).toHaveBeenCalledWith("book-1", "rel-1", expect.objectContaining({
      description: "Mira and Joren choose trust.",
      relType: "mentor",
    }))
    expect(onGraphDataChange).toHaveBeenCalledWith(expect.objectContaining({
      edges: expect.arrayContaining([expect.objectContaining({ type: "ally" })]),
    }))

    await act(async () => {
      graphHandle()?.clearSelection()
      await Promise.resolve()
    })
    expect(text()).toContain("Select a character or connection")
  })

  it("renders compact empty states and handles update failures", async () => {
    readerApiMock.getRelationships.mockResolvedValueOnce({ nodes: [], edges: [] })

    await renderGraph(<RelationshipGraph bookId="book-1" upToChapter={3} compact authorMode={false} />)
    await flush()
    await waitForText("No graphable relationships yet")

    expect(text()).toContain("No graphable relationships yet")
    expect(text()).toContain("Open characters")

    act(() => {
      root?.unmount()
    })
    container?.remove()
    root = null
    container = null
    queryClient?.clear()
    readerApiMock.getRelationships.mockResolvedValueOnce(graphData)
    booksApiMock.updateRelationship.mockRejectedValueOnce(new Error("network"))

    await renderGraph(<RelationshipGraph bookId="book-1" upToChapter={3} authorMode />)
    await flush()
    await waitForText("3 characters")
    await act(async () => {
      graphHandle()?.selectEdge("rel-2")
      await Promise.resolve()
    })
    await act(async () => {
      clickButton("Save correction")
      await Promise.resolve()
      await Promise.resolve()
    })
    expect(text()).toContain("Could not save the relationship correction.")
  })
})
