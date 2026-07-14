// @vitest-environment jsdom

import { act, createRef, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const booksApiMock = vi.hoisted(() => ({
  get: vi.fn(),
  importManuscript: vi.fn(),
  saveCharacterBibleVaultNote: vi.fn(),
  setMode: vi.fn(),
}))
const intelligenceApiMock = vi.hoisted(() => ({
  continuityReport: vi.fn(),
  editorialReviewStream: vi.fn(),
}))

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

vi.mock("@/components/ui/Skeleton", () => ({
  Skeleton: ({ className = "" }: { className?: string }) => <div className={className}>Loading row</div>,
}))

vi.mock("@/components/ui/Tooltip", () => ({
  Tooltip: ({ children, content }: { children: ReactNode; content: string }) => (
    <span data-tooltip={content}>{children}</span>
  ),
}))

vi.mock("@/lib/api/books", () => ({ booksApi: booksApiMock }))
vi.mock("@/lib/api/intelligence", () => ({ intelligenceApi: intelligenceApiMock }))

import { AskLoreViaWorkspace } from "@/components/reader/AskLoreViaWorkspace"
import { StoryAdvisorEditorialPanel } from "@/components/reader/StoryAdvisorEditorialPanel"
import { VaultPreview } from "@/components/reader/VaultPreview"

let root: Root | null = null
let container: HTMLDivElement | null = null

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

async function renderElement(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  await act(async () => {
    root?.render(element)
    await flush()
  })
}

async function flush() {
  await Promise.resolve()
  await new Promise((resolve) => window.setTimeout(resolve, 0))
  await Promise.resolve()
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

function setFieldValue(
  item: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement,
  value: string,
) {
  const prototype =
    item instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : item instanceof HTMLSelectElement
        ? HTMLSelectElement.prototype
        : HTMLInputElement.prototype
  const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set
  setter?.call(item, value)
  item.dispatchEvent(new Event(item instanceof HTMLSelectElement ? "change" : "input", { bubbles: true }))
}

function field<T extends HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>(selector: string, index = 0) {
  const item = Array.from(container?.querySelectorAll(selector) ?? [])[index]
  if (!item) throw new Error(`Missing field: ${selector}\n${text()}`)
  return item as T
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

beforeEach(() => {
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: makeStorage(),
  })
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
  })
  Object.defineProperty(window.URL, "createObjectURL", {
    configurable: true,
    value: vi.fn(() => "blob:mock"),
  })
  Object.defineProperty(window.URL, "revokeObjectURL", {
    configurable: true,
    value: vi.fn(),
  })
  HTMLAnchorElement.prototype.click = vi.fn()

  booksApiMock.get.mockReset().mockResolvedValue({ mode: "reader" })
  booksApiMock.importManuscript.mockReset().mockResolvedValue({ mode: "author", imported_chapters: [2, 3] })
  booksApiMock.saveCharacterBibleVaultNote.mockReset().mockImplementation((_bookId, payload) =>
    Promise.resolve({ content: payload.content, persisted: payload.content.trim().length > 0 }),
  )
  booksApiMock.setMode.mockReset().mockResolvedValue({ mode: "author" })
  intelligenceApiMock.continuityReport.mockReset().mockResolvedValue(new Blob(["pdf"], { type: "application/pdf" }))
  intelligenceApiMock.editorialReviewStream.mockReset().mockImplementation(async (_bookId, _text, _chapter, options) => {
    options?.onStage?.("Cross-checking manuscript memory")
    return {
      review: {
        overall_verdict: "The scene works but has continuity and grammar fixes.",
        thematic_fit: { score: "strong", notes: "The lock imagery reinforces the theme." },
        continuity_issues: [
          {
            severity: "critical",
            type: "location_conflict",
            title: "Lantern moves rooms",
            description: "The lantern is established outside but appears inside.",
            suggestion: "Move the reveal to the entry hall.",
          },
        ],
        grammar_issues: [
          {
            issue: "Tense shift",
            original: "Mara unlocks and waited",
            fix: "Mara unlocks and waits",
          },
        ],
        formatting_notes: ["Add a scene break before the reveal."],
      },
      retrieved_passages: [
        {
          chapter_num: 1,
          chapter_title: "The Door",
          excerpt: "The lantern waits outside the gate.",
        },
      ],
    }
  })
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

describe("reader runtime components", () => {
  it("renders Ask LoreVia prompts, history, citations, loading, error, input, and submit flows", async () => {
    const inputRef = createRef<HTMLTextAreaElement>()
    const bottomRef = createRef<HTMLDivElement>()
    const onInputChange = vi.fn()
    const onSubmit = vi.fn()
    const onKeyDown = vi.fn()

    await renderElement(
      <AskLoreViaWorkspace
        bookId="book-1"
        bookTitle="The Lantern Gate"
        mode="author"
        currentChapter={4}
        scopeLabel="Full manuscript"
        history={[
          {
            question: "Where is the lantern?",
            answer: "The lantern is outside the gate.",
            citations: [
              {
                chapter_num: 1,
                chapter_title: "The Door",
                excerpt: "The lantern waits outside.",
                source_type: "passage",
              },
            ],
          },
          { question: "Who holds the key?", answer: "Mara has it.", citations: [] },
          { question: "What changed?", answer: "Theo revealed the lock rule.", citations: [] },
        ]}
        input="What does Theo know?"
        loading
        error="The advisor is unavailable."
        isDark
        inputRef={inputRef}
        bottomRef={bottomRef}
        onInputChange={onInputChange}
        onSubmit={onSubmit}
        onKeyDown={onKeyDown}
        quickPrompts={["Summarize Mara's arc", "Find the lantern"]}
      />,
    )

    expect(text()).toContain("Ask LoreVia")
    expect(text()).toContain("The Lantern Gate")
    expect(text()).toContain("Chapter 1 - The Door")
    expect(text()).toContain("The advisor is unavailable.")
    expect(text()).toContain("Open Story Advisor")
    expect(text()).toContain("Loading Ask LoreVia answer")

    await click("Summarize Mara's arc")
    expect(onSubmit).toHaveBeenCalledWith("Summarize Mara's arc")

    const textarea = field<HTMLTextAreaElement>("textarea")
    setFieldValue(textarea, "What did Mara promise?")
    textarea.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }))
    expect(onInputChange).toHaveBeenCalledWith("What did Mara promise?")
    expect(onKeyDown).toHaveBeenCalled()

    expect((buttons("Asking...")[0] as HTMLButtonElement).disabled).toBe(true)
  })

  it("drives Story Advisor editorial import, review, save-note, mode conversion, and report download flows", async () => {
    const onSaveNote = vi.fn()

    await renderElement(
      <StoryAdvisorEditorialPanel
        bookId="book-1"
        isDark={false}
        canUseAuthorMode
        onSaveNote={onSaveNote}
      />,
    )
    await act(flush)

    expect(text()).toContain("Manuscript import")
    await click("Convert reader upload to author upload")
    expect(booksApiMock.setMode).toHaveBeenCalledWith("book-1", "author")
    expect(text()).toContain("author workspace")

    setFieldValue(field<HTMLInputElement>("input[type='number']"), "3")
    setFieldValue(field<HTMLTextAreaElement>("textarea"), "Mara unlocks and waited beside the lantern.")
    await click("Add to current upload")
    expect(booksApiMock.importManuscript).toHaveBeenCalledWith("book-1", expect.objectContaining({ chapterNumber: 3 }))
    expect(text()).toContain("Imported chapters 2, 3.")

    await click("Run Editorial Review")
    expect(intelligenceApiMock.editorialReviewStream).toHaveBeenCalledWith("book-1", expect.any(String), 3, expect.any(Object))
    expect(text()).toContain("The scene works")
    expect(text()).toContain("Lantern moves rooms")
    expect(text()).toContain("Tense shift")
    expect(text()).toContain("Cross-referenced passages")

    await click("Save note")
    await click("Save note", 1)
    await click("Save note", 2)
    expect(onSaveNote).toHaveBeenCalledTimes(3)

    await click("Download continuity report")
    expect(intelligenceApiMock.continuityReport).toHaveBeenCalledWith("book-1", expect.any(String), "pdf", 3)
    expect(window.URL.createObjectURL).toHaveBeenCalled()
  })

  it("renders Vault Preview search, edit, save, reset, copy, and zip export behavior", async () => {
    await renderElement(
      <VaultPreview
        bookId="book-1"
        isDark
        preview={{
          root_folder: "Story Vault",
          files: [
            { path: "Story Vault/Characters/Mara.md", content: "Mara keeps the brass key." },
            { path: "Story Vault/Plot/Theo.md", content: "Theo reveals the lock rule." },
          ],
        }}
      />,
    )
    await act(flush)

    expect(text()).toContain("Vault preview and editor")
    expect(text()).toContain("Mara")
    setFieldValue(field<HTMLInputElement>('input[aria-label="Search notes or content"]'), "Theo")
    expect(text()).toContain("Theo")
    await click("Theo")

    const noteEditor = field<HTMLTextAreaElement>('textarea[aria-label="Vault note content"]')
    setFieldValue(noteEditor, "Theo reveals the lock rule and hides the key.")
    expect(text()).toContain("unsaved edits")

    await click("Copy text")
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("Theo reveals the lock rule and hides the key.")

    await click("Save note")
    expect(booksApiMock.saveCharacterBibleVaultNote).toHaveBeenCalledWith(
      "book-1",
      expect.objectContaining({ path: "Story Vault/Plot/Theo.md", content: "Theo reveals the lock rule and hides the key." }),
    )
    expect(text()).toContain("Saved Plot/Theo.md")

    await click("Reset file")
    expect(booksApiMock.saveCharacterBibleVaultNote).toHaveBeenCalledWith(
      "book-1",
      expect.objectContaining({ path: "Story Vault/Plot/Theo.md", content: "Theo reveals the lock rule." }),
    )

    await click("Reset all")
    expect(booksApiMock.saveCharacterBibleVaultNote).toHaveBeenCalledWith(
      "book-1",
      expect.objectContaining({ path: "Story Vault/Characters/Mara.md", content: "Mara keeps the brass key." }),
    )

    await click("Download edited Vault ZIP")
    expect(window.URL.createObjectURL).toHaveBeenCalled()
    expect(text()).toContain("Downloaded edited vault")
  })
})
