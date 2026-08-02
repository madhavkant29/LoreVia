// @vitest-environment jsdom

import { act } from "react"
import { describe, expect, it } from "vitest"

import {
  authState,
  flush,
  render,
  rerender,
  setInputValue,
  text,
} from "./runtime-reader-routes.test-utils"

import NotesPage from "@/app/(dashboard)/notes/page"
import QuotesPage from "@/app/(dashboard)/quotes/page"

describe("dashboard reader runtime routes", () => {
  it("renders notes and quotes filtering, gated, populated, and empty states", async () => {
    await render(<NotesPage />)
    expect(text()).toContain("Keep manuscript notes visible")
    expect(text()).toContain("Continuity note")
    setInputValue("#notes-search", "missing")
    await act(flush)
    expect(text()).toContain("No notes match that search")

    await rerender(<QuotesPage />)
    expect(text()).toContain("Keep every highlighted line")
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
