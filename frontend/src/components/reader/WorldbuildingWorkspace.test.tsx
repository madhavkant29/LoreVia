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
    listDocuments: (...args: unknown[]) => listDocumentsMock(...args),
    listNotes: (...args: unknown[]) => listNotesMock(...args),
    listCanonOverrides: (...args: unknown[]) => listCanonOverridesMock(...args),
    listElements: (...args: unknown[]) => listElementsMock(...args),
    listWiki: (...args: unknown[]) => listWikiMock(...args),
  },
}))

function renderWithQuery(ui: React.ReactNode) {
  const container = document.createElement("div")
  document.body.appendChild(container)
  const root = createRoot(container)
  const queryClient = new QueryClient()

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
  listDocumentsMock.mockReset()
  listNotesMock.mockReset()
  listCanonOverridesMock.mockReset()
  listElementsMock.mockReset()
  listWikiMock.mockReset()
  getStatsMock.mockReset()
  document.body.innerHTML = ""
})

describe("WorldbuildingWorkspace", () => {
  it("does not loop while notes are still loading", async () => {
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
      await Promise.resolve()
    })

    expect(container.textContent).toContain("Loading saved world-gap notes...")
    expect(
      consoleErrorSpy.mock.calls.some(([message]) =>
        String(message).includes("Maximum update depth exceeded"),
      ),
    ).toBe(false)

    consoleErrorSpy.mockRestore()
    unmount()
  })
})
