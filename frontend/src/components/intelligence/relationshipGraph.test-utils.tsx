// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, vi } from "vitest"

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

export let root: Root | null = null
export let container: HTMLDivElement | null = null
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

export const graphData = {
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

export async function renderGraph(element: ReactElement) {
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

export async function flush() {
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
  })
}

export async function waitForText(expected: string) {
  for (let index = 0; index < 20; index += 1) {
    if (text().includes(expected)) return
    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 0))
    })
  }
  throw new Error(`Expected text not found: ${expected}. Saw: ${text()}`)
}

export function text() {
  return container?.textContent ?? ""
}

export function clickButton(label: string) {
  const button = Array.from(container?.querySelectorAll("button") ?? []).find((item) =>
    item.textContent?.includes(label) || item.getAttribute("aria-label") === label
  )
  if (!button) throw new Error(`Missing button: ${label}`)
  act(() => {
    button.dispatchEvent(new MouseEvent("click", { bubbles: true }))
  })
}

export function setFieldValue(field: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement, value: string) {
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

export function graphHandle() {
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

export function cleanupRelationshipGraphRender() {
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
}

afterEach(() => {
  cleanupRelationshipGraphRender()
  document.body.innerHTML = ""
  vi.clearAllMocks()
})
export { booksApiMock, readerApiMock }
