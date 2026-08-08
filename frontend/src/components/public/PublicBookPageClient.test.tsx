// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const { apiMock, queryState, themeState, useQueryMock } = vi.hoisted(() => ({
  apiMock: { getBook: vi.fn(), trackView: vi.fn(), createContentReport: vi.fn() },
  queryState: { data: null as unknown, isLoading: false },
  themeState: { theme: "light" },
  useQueryMock: vi.fn(),
}))

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
}))
vi.mock("@tanstack/react-query", () => ({ useQuery: useQueryMock }))
vi.mock("@/lib/api/public", () => ({ publicApi: apiMock }))
vi.mock("@/lib/stores/preferencesStore", () => ({ usePreferencesStore: () => themeState }))

import { PublicBookPageClient } from "./PublicBookPageClient"

let root: Root | null = null
let container: HTMLDivElement | null = null

async function renderElement(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root?.render(element)
    await Promise.resolve()
  })
  return container
}

async function clickButton(label: string) {
  const button = Array.from(document.body.querySelectorAll("button")).find((item) => item.textContent?.includes(label))
  expect(button).toBeTruthy()
  await act(async () => {
    button?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await Promise.resolve()
  })
}

function setValue(field: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement, value: string) {
  const prototype = field instanceof HTMLTextAreaElement
    ? HTMLTextAreaElement.prototype
    : field instanceof HTMLSelectElement
      ? HTMLSelectElement.prototype
      : HTMLInputElement.prototype
  Object.getOwnPropertyDescriptor(prototype, "value")?.set?.call(field, value)
  field.dispatchEvent(new Event(field instanceof HTMLSelectElement ? "change" : "input", { bubbles: true }))
}

function buildBook() {
  return {
    id: "book-1",
    public_slug: "atlas-rising",
    title: "Atlas Rising",
    author_username: "mira",
    creator_display_name: "Mira Vale",
    content_source_type: "creator_original",
    description: "A gate opens at dawn.",
    source_public_domain_note: "Source note.",
    visibility_notice: "Preview visibility notice.",
    total_chapters: 2,
    chapters: [
      { number: 1, title: "Opening", description: "The gate appears." },
      { number: 2, title: null, description: null },
    ],
    analytics: {
      book_view_count: 1234,
      unique_reader_count_30d: 42,
      chapter_view_count: 98,
      published_at: null,
      chapter_count: 2,
      total_words: 15000,
      open_discussion_count: 1,
      has_open_discussion: true,
      discussion_comment_count: 7,
      discussion_interest_count: 3,
    },
  }
}

beforeEach(() => {
  Object.values(apiMock).forEach((mock) => mock.mockReset())
  apiMock.getBook.mockResolvedValue(buildBook())
  apiMock.trackView.mockResolvedValue({})
  apiMock.createContentReport.mockResolvedValue({ message: "Report received." })
  queryState.data = buildBook()
  queryState.isLoading = false
  themeState.theme = "light"
  useQueryMock.mockReset().mockImplementation(() => queryState)
})

afterEach(async () => {
  await act(async () => root?.unmount())
  container?.remove()
  document.body.innerHTML = ""
  root = null
  container = null
})

describe("PublicBookPageClient", () => {
  it("renders book analytics, chapters, tracks a view, and submits a copyright report", async () => {
    themeState.theme = "dark"
    const view = await renderElement(<PublicBookPageClient bookId="atlas-rising" />)
    expect(view.textContent).toContain("Atlas Rising")
    expect(view.textContent).toContain("Published by @mira")
    expect(view.textContent).toContain("1,234")
    expect(view.textContent).toContain("15,000")
    expect(view.textContent).toContain("This book has an active public discussion.")
    expect(view.querySelector('a[href="/public/atlas-rising/chapter/1"]')).not.toBeNull()
    expect(view.querySelector('a[href="/public/atlas-rising/chapter/2"]')?.textContent).toContain("Chapter 2")
    expect(view.querySelector("main")?.className).toContain("bg-[#0a0f14]")
    expect(apiMock.trackView).toHaveBeenCalledWith("atlas-rising", { eventType: "book_view" })

    await clickButton("Report this book")
    const textareas = Array.from(document.body.querySelectorAll("textarea"))
    const inputs = Array.from(document.body.querySelectorAll("input"))
    await act(async () => {
      setValue(textareas[0], "This copies my original work.")
      setValue(textareas[1], "The opening paragraph is duplicated.")
      setValue(inputs[0], "Rights Owner")
      setValue(inputs[1], "owner@example.test")
      setValue(textareas[2], "My published novel")
      setValue(inputs[2], "https://example.test/original")
      inputs[3].click()
      await Promise.resolve()
    })
    await clickButton("Submit report")
    expect(apiMock.createContentReport).toHaveBeenCalledWith(expect.objectContaining({
      bookId: "book-1",
      reportType: "copyright",
      reason: "This copies my original work.",
      reporterEmail: "owner@example.test",
      copyrightOwnerName: "Rights Owner",
    }))
    expect(document.body.textContent).toContain("Report received.")
  })

  it("switches to a non-copyright report and closes the modal", async () => {
    const view = await renderElement(<PublicBookPageClient bookId="book-1" />)
    await clickButton("Report this book")
    const select = document.body.querySelector("select") as HTMLSelectElement
    await act(async () => {
      setValue(select, "spam")
      await Promise.resolve()
    })
    expect(document.body.textContent).not.toContain("Original work description")
    await clickButton("Cancel")
    expect(document.body.textContent).not.toContain("Report a copyright or policy issue")
  })

  it("renders loading and missing states and configures initial query data", async () => {
    queryState.isLoading = true
    queryState.data = null
    let view = await renderElement(<PublicBookPageClient bookId="missing" initialBook={buildBook() as never} />)
    expect(view.textContent).toContain("Loading public book...")
    expect(useQueryMock.mock.calls[0][0].initialData.title).toBe("Atlas Rising")
    await act(async () => root?.unmount())
    container?.remove()
    root = null
    container = null

    queryState.isLoading = false
    view = await renderElement(<PublicBookPageClient bookId="missing" />)
    expect(view.textContent).toContain("Public book not found.")
  })
})
