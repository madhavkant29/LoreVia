// @vitest-environment jsdom

import { act } from "react"
import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createRoot } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"

import { WorldbuildingWorkspace } from "./WorldbuildingWorkspace"

const listDocumentsMock = vi.fn()
const listNotesMock = vi.fn()
const listCanonOverridesMock = vi.fn()
const listElementsMock = vi.fn()
const listWikiMock = vi.fn()
const getStatsMock = vi.fn()
const getBootstrapMock = vi.fn()
const getDocumentMock = vi.fn()
const getGapsMock = vi.fn()
const getIntegrationMock = vi.fn()
const updateDocumentMock = vi.fn()
const uploadDocumentsMock = vi.fn()
const deleteDocumentMock = vi.fn()
const createNoteMock = vi.fn()
const updateNoteStatusMock = vi.fn()
const deleteNoteMock = vi.fn()
const saveCanonOverrideMock = vi.fn()
const acceptSuggestionMock = vi.fn()
const generateWikiMock = vi.fn()
const queryMock = vi.fn()
const getNotesByChapterMock = vi.fn()
vi.mock("@/lib/api/reader", () => ({ readerApi: { getChapterList: async () => ({ chapters: [{ number: 2 }] }) } }))

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
}))

vi.mock("@/lib/api/books", () => ({
  booksApi: {
    getStats: (...args: unknown[]) => getStatsMock(...args),
  },
}))

vi.mock("@/lib/api/worldBuilding", () => ({
  worldBuildingApi: {
    getBootstrap: (...args: unknown[]) => getBootstrapMock(...args),
    listDocuments: (...args: unknown[]) => listDocumentsMock(...args),
    listNotes: (...args: unknown[]) => listNotesMock(...args),
    listCanonOverrides: (...args: unknown[]) => listCanonOverridesMock(...args),
    listElements: (...args: unknown[]) => listElementsMock(...args),
    listWiki: (...args: unknown[]) => listWikiMock(...args),
    getDocument: (...args: unknown[]) => getDocumentMock(...args),
    getGaps: (...args: unknown[]) => getGapsMock(...args),
    getIntegration: (...args: unknown[]) => getIntegrationMock(...args),
    updateDocument: (...args: unknown[]) => updateDocumentMock(...args),
    uploadDocuments: (...args: unknown[]) => uploadDocumentsMock(...args),
    deleteDocument: (...args: unknown[]) => deleteDocumentMock(...args),
    createNote: (...args: unknown[]) => createNoteMock(...args),
    updateNoteStatus: (...args: unknown[]) => updateNoteStatusMock(...args),
    deleteNote: (...args: unknown[]) => deleteNoteMock(...args),
    saveCanonOverride: (...args: unknown[]) => saveCanonOverrideMock(...args),
    acceptSuggestion: (...args: unknown[]) => acceptSuggestionMock(...args),
    generateWiki: (...args: unknown[]) => generateWikiMock(...args),
    query: (...args: unknown[]) => queryMock(...args),
    getNotesByChapter: (...args: unknown[]) => getNotesByChapterMock(...args),
  },
}))

function renderWithQuery(ui: React.ReactNode, seedQueryData?: (queryClient: QueryClient) => void) {
  const container = document.createElement("div")
  document.body.appendChild(container)
  const root = createRoot(container)
  const queryClient = new QueryClient()
  seedQueryData?.(queryClient)

  act(() => {
    root.render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
  })

  return {
    container,
    unmount: () => {
      act(() => {
        root.unmount()
      })
      container.remove()
      queryClient.clear()
    },
  }
}

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

afterEach(() => {
  vi.restoreAllMocks()
  getBootstrapMock.mockReset()
  listDocumentsMock.mockReset()
  listNotesMock.mockReset()
  listCanonOverridesMock.mockReset()
  listElementsMock.mockReset()
  listWikiMock.mockReset()
  getStatsMock.mockReset()
  getDocumentMock.mockReset()
  getGapsMock.mockReset()
  getIntegrationMock.mockReset()
  updateDocumentMock.mockReset()
  uploadDocumentsMock.mockReset()
  deleteDocumentMock.mockReset()
  createNoteMock.mockReset()
  updateNoteStatusMock.mockReset()
  deleteNoteMock.mockReset()
  saveCanonOverrideMock.mockReset()
  acceptSuggestionMock.mockReset()
  generateWikiMock.mockReset()
  queryMock.mockReset()
  getNotesByChapterMock.mockReset()
  document.body.innerHTML = ""
})

async function flushUi(times = 4) {
  for (let index = 0; index < times; index += 1) {
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0))
    })
  }
}

async function waitForText(container: HTMLElement, text: string, attempts = 12) {
  for (let index = 0; index < attempts; index += 1) {
    if (container.textContent?.includes(text)) return
    await flushUi()
  }
  expect(container.textContent).toContain(text)
}

function clickByText(container: HTMLElement, text: string, index = 0) {
  const matches = Array.from(container.querySelectorAll("button, a")).filter((element) =>
    element.textContent?.includes(text)
  )
  const match = matches[index] as HTMLElement | undefined
  expect(match, `Expected to find ${text}`).toBeTruthy()
  act(() => {
    match?.click()
  })
  return match
}

function clickExactButton(container: HTMLElement, text: string, index = 0) {
  const matches = Array.from(container.querySelectorAll("button")).filter((element) =>
    element.textContent?.trim() === text
  )
  const match = matches[index] as HTMLElement | undefined
  expect(match, `Expected to find exact button ${text}`).toBeTruthy()
  act(() => {
    match?.click()
  })
  return match
}

function setFieldValue(field: HTMLInputElement | HTMLTextAreaElement, value: string) {
  const prototype = field instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype
  const descriptor = Object.getOwnPropertyDescriptor(prototype, "value")
  act(() => {
    descriptor?.set?.call(field, value)
    field.dispatchEvent(new Event("input", { bubbles: true }))
  })
}

const documentsFixture = [
  {
    id: "doc-1",
    title: "World Bible",
    word_count: 1200,
    updated_at: "2026-06-01T00:00:00Z",
  },
]

const notesFixture = [
  {
    id: "note-1",
    note_type: "world_gap",
    title: "Rename the old capital",
    body: "The capital is named twice.",
    priority: "high",
    status: "open",
    chapter_number: 2,
    linked_gap_id: "gap-1",
    context_label: "Capital",
    suggested_fix: "Use one name.",
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-01T00:00:00Z",
  },
  {
    id: "note-2",
    note_type: "world_gap",
    title: "Addressed moon rule",
    body: "Already fixed.",
    priority: "medium",
    status: "addressed",
    chapter_number: null,
    linked_gap_id: null,
    context_label: null,
    suggested_fix: null,
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-01T00:00:00Z",
  },
]

const elementFixture = {
  id: "element-1",
  name: "Aster Sea",
  element_type: "region",
  source_scope: "worldbuilding",
  description: "A storm-fed sea.",
  confidence: 0.86,
  usage_count: 4,
  chapter_numbers: [1, 2],
  world_document_title: "World Bible",
  suggestions: [{ id: "sug-1", title: "Seed sea storms", description: "Mention the storms earlier." }],
}

const gapFixture = {
  generated_at: "2026-06-03T00:00:00Z",
  consistency_flags: [
    {
      id: "flag-1",
      type: "contradiction",
      title: "Two capitals",
      description: "The old and new capital both appear current.",
    },
  ],
  gap_groups: [
    {
      key: "canon",
      label: "Canon gaps",
      description: "World canon cleanup",
      items: [
        {
          id: "gap-1",
          title: "Capital mismatch",
          description: "The capital changes names.",
          severity: "high",
          priority: 8,
          world_document_id: "doc-1",
          world_document_title: "World Bible",
          story_chapter_number: 2,
          canonical_name: "Capital",
          entity_type: "place",
          confidence: 0.9,
          world_evidence: "The capital is Lume.",
          story_evidence: "The capital is Veyr.",
          suggested_fix: "Choose one capital name.",
        },
      ],
    },
  ],
  world_elements: [elementFixture],
}

const integrationFixture = {
  generated_at: "2026-06-04T00:00:00Z",
  integration_opportunities: [
    {
      id: "opp-1",
      world_document_id: "doc-1",
      world_document_title: "World Bible",
      element_name: "Aster Sea",
      element_type: "region",
      target_chapter: 4,
      description: "Use the sea as a pressure point.",
      priority: 7,
      suggestions: ["Echo the storm rule", "Let a sailor warn Mara"],
    },
  ],
  world_elements: [elementFixture],
}

const wikiFixture = [
  {
    id: "wiki-1",
    name: "Aster Sea",
    entry_type: "place",
    first_mention: 1,
    description: "A dangerous inland sea.",
  },
]

function seedWorldbuildingQueryData(queryClient: QueryClient) {
  queryClient.setQueryData(["worldbuilding:book-1:documents"], documentsFixture)
  queryClient.setQueryData(["worldbuilding:book-1:notes"], notesFixture)
  queryClient.setQueryData(["worldbuilding:book-1:canon-overrides"], [{ id: "canon-1", canonical_name: "Mara", aliases: ["Mar"] }])
  queryClient.setQueryData(["worldbuilding:book-1:elements"], [elementFixture])
  queryClient.setQueryData(["worldbuilding:book-1:wiki"], wikiFixture)
  queryClient.setQueryData(["worldbuilding:book-1:analysis:gap"], gapFixture)
  queryClient.setQueryData(["worldbuilding:book-1:document:doc-1"], {
    ...documentsFixture[0],
    text: "The Aster Sea obeys old storm rules.",
  })
}

function mockWorldbuildingSuccess() {
  getBootstrapMock.mockResolvedValue({
    documents: documentsFixture,
    notes: notesFixture,
    canon_overrides: [{ id: "canon-1", canonical_name: "Mara", aliases: ["Mar"] }],
    elements: [elementFixture],
    wiki: wikiFixture,
    stats: {
      private: {
        total_uploads: 2,
        upload_limit: 10,
        uploads_remaining: 8,
        upload_limit_unlimited: false,
      },
    },
    gap_analysis: gapFixture,
  })
  listDocumentsMock.mockResolvedValue(documentsFixture)
  listNotesMock.mockResolvedValue(notesFixture)
  listCanonOverridesMock.mockResolvedValue([{ id: "canon-1", canonical_name: "Mara", aliases: ["Mar"] }])
  listElementsMock.mockResolvedValue([elementFixture])
  listWikiMock.mockResolvedValue(wikiFixture)
  getStatsMock.mockResolvedValue(null)
  getDocumentMock.mockResolvedValue({ ...documentsFixture[0], text: "The Aster Sea obeys old storm rules." })
  getGapsMock.mockResolvedValue(gapFixture)
  getIntegrationMock.mockResolvedValue(integrationFixture)
  updateDocumentMock.mockResolvedValue({ ...documentsFixture[0], text: "Updated world text." })
  uploadDocumentsMock.mockResolvedValue([{ id: "doc-2", title: "New World Doc", word_count: 30, updated_at: "2026-06-02T00:00:00Z" }])
  deleteDocumentMock.mockResolvedValue({})
  createNoteMock.mockResolvedValue({ ...notesFixture[0], id: "note-3", title: "Saved opportunity", linked_gap_id: null, linked_integration_id: "opportunity-1" })
  updateNoteStatusMock.mockImplementation(async (_bookId: string, noteId: string, status: string) => ({ ...notesFixture.find((note) => note.id === noteId), status }))
  deleteNoteMock.mockResolvedValue({})
  saveCanonOverrideMock.mockResolvedValue({ id: "canon-2", canonical_name: "Aster Sea", aliases: ["Sea"] })
  acceptSuggestionMock.mockResolvedValue({})
  generateWikiMock.mockResolvedValue({ generated_count: 2, updated_names: ["Aster Sea", "Mara"] })
  queryMock.mockResolvedValue({
    mode: "gap_detection",
    answer: "The canon holds if the storm rule stays consistent.",
    simulation_steps: ["Check source", "Compare chapter"],
    logic_alerts: [{ title: "Storm conflict" }],
    suggestions: [{ title: "Clarify the oath" }],
    citations: [{ source: "World Bible" }],
  })
  getNotesByChapterMock.mockResolvedValue([notesFixture[0]])
}

describe("WorldbuildingWorkspace", () => {
  it("does not loop while workspace data is still loading", async () => {
    getBootstrapMock.mockImplementation(() => new Promise(() => {}))
    listDocumentsMock.mockResolvedValue([])
    listNotesMock.mockImplementation(() => new Promise(() => {}))
    listCanonOverridesMock.mockResolvedValue([])
    listElementsMock.mockResolvedValue([])
    listWikiMock.mockResolvedValue([])
    getStatsMock.mockResolvedValue(null)

    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {})
    const { container, unmount } = renderWithQuery(
      <WorldbuildingWorkspace bookId="book-1" isDark={false} focus="gap" />,
    )

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0))
    })

    expect(container.textContent).toContain("Loading canon sources, comparison, and saved cleanup notes")
    expect(
      consoleErrorSpy.mock.calls.some(([message]) =>
        String(message).includes("Maximum update depth exceeded"),
      ),
    ).toBe(false)

    consoleErrorSpy.mockRestore()
    unmount()
  })

  it("drives the worldbuilding runtime workspace actions", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true)
    mockWorldbuildingSuccess()
    const { container, unmount } = renderWithQuery(
      <WorldbuildingWorkspace bookId="book-1" isDark={false} focus="gap" />,
      seedWorldbuildingQueryData,
    )

    await flushUi(8)

    await waitForText(container, "World Bible")
    await waitForText(container, "Canon gaps")

    clickByText(container, "Refresh comparison")
    await flushUi()
    expect(getGapsMock).toHaveBeenCalledWith("book-1")

    clickByText(container, "Canon tools")
    await flushUi()
    expect(container.textContent).toContain("Aster Sea")
    clickByText(container, "Refresh opportunities")
    await flushUi()
    expect(getIntegrationMock).toHaveBeenCalledWith("book-1")
    expect(container.textContent).toContain("Use the sea as a pressure point.")

    clickByText(container, "Save as note")
    await flushUi()
    expect(createNoteMock).toHaveBeenCalled()

    const inputs = Array.from(container.querySelectorAll("input"))
    const textInputs = inputs.filter((input) => input.type !== "file" && input.type !== "checkbox")
    setFieldValue(textInputs[0] as HTMLInputElement, "Aster Sea")
    setFieldValue(textInputs[1] as HTMLInputElement, "Sea, Storm Road")
    clickByText(container, "Save override")
    await flushUi()
    expect(saveCanonOverrideMock).toHaveBeenCalledWith("book-1", {
      canonical_name: "Aster Sea",
      aliases: ["Sea", "Storm Road"],
    })

    clickByText(container, "Mark implemented")
    await flushUi()
    expect(acceptSuggestionMock).toHaveBeenCalledWith("element-1", {
      suggestion_id: "sug-1",
      mark_implemented: true,
    })

    clickByText(container, "Generate wiki")
    await flushUi()
    expect(generateWikiMock).toHaveBeenCalledWith("book-1")

    const textareas = Array.from(container.querySelectorAll("textarea"))
    setFieldValue(textareas[0] as HTMLTextAreaElement, "Does the storm rule still work?")
    clickByText(container, "Canon status")
    await flushUi()
    expect(queryMock).toHaveBeenCalledWith("book-1", {
      query: "Does the storm rule still work?",
      mode: "gap_detection",
    })
    expect(container.textContent).toContain("The canon holds")

    clickByText(container, "Canon sources")
    await flushUi(4)
    const sourceTextareas = Array.from(container.querySelectorAll("textarea"))
    setFieldValue(sourceTextareas[sourceTextareas.length - 1] as HTMLTextAreaElement, "Updated world text.")
    clickByText(container, "Save document")
    await flushUi()
    expect(updateDocumentMock).toHaveBeenCalled()

    clickByText(container, "Review gaps")
    await flushUi()
    const gapInputs = Array.from(container.querySelectorAll("input"))
    setFieldValue(gapInputs[gapInputs.length - 1] as HTMLInputElement, "2")
    clickByText(container, "Filter by chapter")
    await flushUi()
    expect(getNotesByChapterMock).toHaveBeenCalledWith("book-1", 2)

    clickExactButton(container, "Resolve")
    await flushUi()
    expect(updateNoteStatusMock).toHaveBeenCalledWith("book-1", "note-1", "addressed")

    clickExactButton(container, "Delete")
    await flushUi()
    expect(deleteNoteMock).toHaveBeenCalledWith("book-1", "note-1")

    unmount()
  })

  it("shows a recoverable bootstrap failure without claiming sources are empty", async () => {
    mockWorldbuildingSuccess()
    getBootstrapMock.mockRejectedValueOnce(new Error("offline"))
    const { container, unmount } = renderWithQuery(<WorldbuildingWorkspace bookId="book-1" isDark={false} focus="gap" />)
    await flushUi(6)
    expect(container.textContent).toContain("Worldbuilding data could not be loaded")
    expect(container.textContent).not.toContain("No world documents")
    clickExactButton(container, "Retry worldbuilding workspace"); await flushUi(6)
    expect(container.textContent).toContain("Canon conflicts")
    unmount()
  })

  it("keeps a new source draft attached to the new document across tabs", async () => {
    mockWorldbuildingSuccess()
    const { container, unmount } = renderWithQuery(<WorldbuildingWorkspace bookId="book-1" isDark={false} focus="gap" />, seedWorldbuildingQueryData)
    await flushUi(6); clickExactButton(container, "Canon sources"); await flushUi(4)
    clickExactButton(container, "New blank document")
    setFieldValue(container.querySelector("textarea")!, "A newly drafted canon rule")
    clickExactButton(container, "Review gaps"); clickExactButton(container, "Canon sources"); await flushUi(4)
    expect(container.querySelector("textarea")?.value).toBe("A newly drafted canon rule")
    expect(container.textContent).toContain("Create document")
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false)
    clickByText(container, "World Bible"); await flushUi(3)
    expect(confirm).toHaveBeenCalled()
    expect(container.querySelector("textarea")?.value).toBe("A newly drafted canon rule")
    uploadDocumentsMock.mockRejectedValueOnce(new Error("offline"))
    clickExactButton(container, "Create document"); await flushUi(6)
    expect(uploadDocumentsMock).toHaveBeenCalledWith("book-1", { title: "Worldbuilding Manuscript", text: "A newly drafted canon rule" })
    expect(updateDocumentMock).not.toHaveBeenCalled()
    expect(container.querySelector("textarea")?.value).toBe("A newly drafted canon rule")
    expect(container.textContent).toContain("Your draft is retained")
    unmount()
  })

  it("ignores a late chapter filter after returning to all cleanup notes", async () => {
    mockWorldbuildingSuccess()
    const { container, unmount } = renderWithQuery(<WorldbuildingWorkspace bookId="book-1" isDark={false} focus="gap" />, seedWorldbuildingQueryData)
    await flushUi(6)
    setFieldValue(container.querySelector('input[aria-label="Chapter number filter"]')!, "2")
    clickExactButton(container, "Filter by chapter"); await flushUi(4)
    let finish!: (value: unknown) => void
    getNotesByChapterMock.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    setFieldValue(container.querySelector('input[aria-label="Chapter number filter"]')!, "3")
    clickExactButton(container, "Filter by chapter"); await flushUi(2)
    clickExactButton(container, "Show all")
    await act(async () => { finish([]) }); await flushUi(4)
    expect(container.textContent).toContain("Showing all cleanup notes.")
    expect(container.textContent).toContain("Rename the old capital")
    expect(container.textContent).not.toContain("Showing chapter 3")
    unmount()
  })

  it("keeps the comparison marked outdated when a new source saves but refresh fails", async () => {
    mockWorldbuildingSuccess()
    const created = { ...documentsFixture[0], id: "doc-new", title: "New canon" }
    uploadDocumentsMock.mockResolvedValueOnce([created])
    listDocumentsMock.mockResolvedValue([documentsFixture[0], created])
    getGapsMock.mockRejectedValueOnce(new Error("offline"))
    const { container, unmount } = renderWithQuery(<WorldbuildingWorkspace bookId="book-1" isDark={false} focus="gap" />, seedWorldbuildingQueryData)
    await flushUi(6); clickExactButton(container, "Canon sources"); await flushUi(4)
    clickExactButton(container, "New blank document")
    setFieldValue(container.querySelector("textarea")!, "A new source rule")
    clickExactButton(container, "Create document"); await flushUi(6)
    clickExactButton(container, "Review gaps"); await flushUi(3)
    expect(container.textContent).toContain("This comparison uses earlier source or manuscript content.")
    expect(container.textContent).toContain("Capital mismatch")
    expect(container.textContent).toContain("Retry comparison")
    unmount()
  })

  it("retains canon queries after a failure and blocks concurrent canon writes", async () => {
    mockWorldbuildingSuccess()
    const { container, unmount } = renderWithQuery(<WorldbuildingWorkspace bookId="book-1" isDark={false} focus="gap" />, seedWorldbuildingQueryData)
    await flushUi(6); clickExactButton(container, "Canon tools"); await flushUi(2)
    setFieldValue(container.querySelector("textarea")!, "Does the storm rule still work?")
    clickExactButton(container, "Canon status"); await flushUi(4)
    expect(container.textContent).toContain("The canon holds")
    let reject!: (reason: Error) => void
    queryMock.mockImplementationOnce(() => new Promise((_resolve, fail) => { reject = fail }))
    setFieldValue(container.querySelector("textarea")!, "What changes at night?")
    clickExactButton(container, "Canon status"); await flushUi(2)
    expect(container.querySelector("fieldset")?.disabled).toBe(true)
    clickExactButton(container, "Generate wiki")
    expect(generateWikiMock).not.toHaveBeenCalled()
    await act(async () => { reject(new Error("offline")) }); await flushUi(4)
    expect(container.querySelector("textarea")?.value).toBe("What changes at night?")
    expect(container.textContent).toContain("The canon holds")
    expect(container.textContent).toContain("question and any previous answer are retained")
    expect(container.querySelector("fieldset")?.disabled).toBe(false)
    unmount()
  })

  it("preserves existing source edits across tabs and prevents editing during a save", async () => {
    mockWorldbuildingSuccess()
    let finish!: (value: unknown) => void
    updateDocumentMock.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    const { container, unmount } = renderWithQuery(<WorldbuildingWorkspace bookId="book-1" isDark={false} focus="gap" />, seedWorldbuildingQueryData)
    await flushUi(6); clickExactButton(container, "Canon sources"); await flushUi(4)
    setFieldValue(container.querySelector("textarea")!, "Retained world revision")
    clickExactButton(container, "Canon tools"); clickExactButton(container, "Canon sources"); await flushUi(4)
    expect(container.querySelector("textarea")?.value).toBe("Retained world revision")
    clickExactButton(container, "Save document"); await flushUi(2)
    expect(container.querySelector("fieldset")?.disabled).toBe(true)
    await act(async () => { finish({ ...documentsFixture[0], text: "Retained world revision" }) })
    getDocumentMock.mockResolvedValue({ ...documentsFixture[0], text: "Retained world revision" })
    await flushUi(6)
    expect(updateDocumentMock).toHaveBeenCalledTimes(1)
    expect(container.querySelector("textarea")?.value).toBe("Retained world revision")
    expect(container.querySelector("fieldset")?.disabled).toBe(false)
    unmount()
  })
})
