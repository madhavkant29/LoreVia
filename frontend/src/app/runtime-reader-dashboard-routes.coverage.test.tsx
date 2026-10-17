// @vitest-environment jsdom

import { act } from "react"
import { describe, expect, it, vi } from "vitest"

import {
  authState,
  click,
  flush,
  getContainer,
  render,
  rerender,
  setInputValue,
  text,
} from "./runtime-reader-routes.test-utils"

import NotesPage from "@/app/(dashboard)/notes/page"
import QuotesPage from "@/app/(dashboard)/quotes/page"

describe("dashboard reader runtime routes", () => {
  it("copies quote text with explicit success and recoverable clipboard failure feedback", async () => {
    const writeText = vi.fn().mockRejectedValueOnce(new Error("denied")).mockResolvedValue(undefined)
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } })
    await render(<QuotesPage />)
    await click("Copy quote")
    expect(text()).toContain("Could not copy. Select and copy the full quote text")
    await click("Copy quote")
    expect(writeText).toHaveBeenLastCalledWith("The gate remembers every oath.")
    expect(text()).toContain("Copied the complete quote text.")
    expect(getContainer()?.querySelector('a[href="/book-1/chapter/2"]')?.textContent).toBe("Open chapter 2")
  })

  it("reads a saved note inline and distinguishes source links from the book notes workspace", async () => {
    await render(<NotesPage />)
    await click("Read note")
    expect(getContainer()?.querySelector('button[aria-expanded="true"]')?.textContent).toContain("Close note")
    expect(getContainer()?.querySelector('a[href="/book-1/chapter/2"]')?.textContent).toBe("Open chapter 2")
    expect(getContainer()?.querySelector('a[href="/book-1/notes"]')?.textContent).toBe("Book notes workspace")
    await click("Close note")
    expect(getContainer()?.querySelector('button[aria-expanded="false"]')?.textContent).toContain("Read note")
  })

  it("renders notes and quotes filtering, gated, populated, and empty states", async () => {
    await render(<NotesPage />)
    expect(text()).toContain("Search notes from every manuscript")
    expect(text()).toContain("Continuity note")
    setInputValue("#notes-search", "missing")
    await act(flush)
    expect(text()).toContain("No notes match that search")

    await rerender(<QuotesPage />)
    expect(text()).toContain("Search highlighted passages")
    expect(text()).toContain("Mara")
    setInputValue("#quotes-search", "missing")
    await act(flush)
    expect(text()).toContain("No quotes match that search")

    authState.user = { id: "free-user", tier: "free" }
    await rerender(<NotesPage />)
    expect(text()).toContain("Notes require an active trial or paid plan")
    await rerender(<QuotesPage />)
    expect(text()).toContain("Saved quotes require an active trial or paid plan")
  })
})
