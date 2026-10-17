import { describe, expect, it } from "vitest"
import type { Book } from "@/types/book"
import { applyBookPreferenceOperations, defaultBookUiPreference, defaultUserUiPreference } from "@/lib/stores/uiPreferencesStore"
import { resolveWorkspaceTool } from "@/lib/workspace/toolResolver"
import { workspaceToolRegistry } from "@/lib/workspace/toolRegistry"
import { navigationToolDetail, navigationToolOperations, publicAccessStatus, restoreNavigationToolOperations, visibilityStateLabel } from "./visibilityPage.helpers"

const book = (values: Partial<Book> = {}) => ({ id: "book-1", title: "Story", status: "ready", is_public: false, ...values } as Book)
const publicBook = { is_public: true, public_status: "published", moderation_status: "clean", public_slug: "story" } as const

describe("visibility status", () => {
  it("does not infer public access from a reserved slug", () => {
    expect(publicAccessStatus(book({ public_slug: "reserved", public_status: "draft" }))).toMatchObject({ label: "Not public", href: null })
  })
  it("links published editions to the actual public route and encodes the identifier", () => {
    expect(publicAccessStatus(book(publicBook))).toMatchObject({ label: "Public page active", href: "/public/story" })
    expect(publicAccessStatus(book({ ...publicBook, public_slug: "title/space?" })).href).toBe("/public/title%2Fspace%3F")
    expect(publicAccessStatus(book({ ...publicBook, public_slug: null })).href).toBe("/public/book-1")
  })
  it.each([{ archived_at: "2026-10-01" }, { hidden_at: "2026-10-01" }, { public_status: "hidden" }, { public_status: "removed" }, { moderation_status: "under_review" }, { moderation_status: "hidden" }, { moderation_status: "removed" }])("does not show a public link for restricted state %j", values => {
    expect(publicAccessStatus(book({ ...publicBook, ...values })).href).toBeNull()
  })
  it("distinguishes pending reviews, incomplete legacy state, and permitted reported books", () => {
    expect(publicAccessStatus(book({ public_status: "pending_review" })).label).toBe("Awaiting review")
    expect(publicAccessStatus(book({ public_share_status: "pending" })).label).toBe("Awaiting review")
    expect(publicAccessStatus(book({ is_public: true })).label).toBe("Public status unverified")
    expect(publicAccessStatus(book({ ...publicBook, moderation_status: "future_status" })).href).toBeNull()
    expect(publicAccessStatus(book({ ...publicBook, moderation_status: "reported" })).href).toBe("/public/story")
  })
  it("keeps zero counts and readable states, and omits invalid counts", () => {
    expect(visibilityStateLabel({ state: "not_shared", label: "None", count: 0 })).toBe("0 · Not shared")
    expect(visibilityStateLabel({ state: "", label: "Missing", count: NaN })).toBe("Unknown")
    expect(visibilityStateLabel({ state: "active", label: "Active", count: -1 })).toBe("Active")
  })
})

describe("book-scoped navigation recovery", () => {
  const tool = workspaceToolRegistry.find(item => item.id === "book.foreshadowing")!
  it("reveals one advanced tool without changing the preset or global workspace mode", () => {
    const preference = defaultBookUiPreference("book-1", "focused")
    const next = applyBookPreferenceOperations(preference, navigationToolOperations(preference, tool.id, true))
    expect(next.book_preset).toBe("draft")
    expect(next.advanced_tool_override).toBeNull()
    expect(next.overview_cards).toEqual({ [tool.id]: "visible" })
    expect(resolveWorkspaceTool(tool, { mode: "focused", book: book(), bookPreference: next, globalPreference: defaultUserUiPreference("focused"), hasAuthorAccess: true }).hidden).toBe(false)
  })
  it("removes explicit hiding while preserving other hidden tools and avoids duplicates", () => {
    const preference = { ...defaultBookUiPreference("book-1"), hidden_book_tools: [tool.id, "book.notes"], overview_cards: { [tool.id]: "user_hidden" as const } }
    const next = applyBookPreferenceOperations(preference, navigationToolOperations(preference, tool.id, true))
    expect(next.hidden_book_tools).toEqual(["book.notes"])
    const hidden = applyBookPreferenceOperations(preference, navigationToolOperations(preference, tool.id, false))
    expect(hidden.hidden_book_tools).toEqual([tool.id, "book.notes"])
  })
  it("undo restores the prior tool preference without erasing a later change to another tool", () => {
    const previous = defaultBookUiPreference("book-1")
    const current = applyBookPreferenceOperations(previous, navigationToolOperations(previous, tool.id, true))
    current.hidden_book_tools = ["book.notes"]
    current.overview_cards["book.notes"] = "user_hidden"
    const restored = applyBookPreferenceOperations(current, restoreNavigationToolOperations(current, previous, tool.id))
    expect(restored.hidden_book_tools).toEqual(["book.notes"])
    expect(restored.overview_cards).toEqual({ "book.notes": "user_hidden" })
    const explicit = { ...previous, hidden_book_tools: [tool.id], overview_cards: { [tool.id]: false } }
    const restoredExplicit = applyBookPreferenceOperations(current, restoreNavigationToolOperations(current, explicit, tool.id))
    expect(restoredExplicit.hidden_book_tools).toContain(tool.id)
    expect(restoredExplicit.overview_cards[tool.id]).toBe(false)
  })
  it("describes hidden reasons separately from plan and processing requirements", () => {
    const item = resolveWorkspaceTool(tool, { mode: "focused", book: book({ status: "processing" }), bookPreference: defaultBookUiPreference("book-1"), hasAuthorAccess: false })
    expect(navigationToolDetail(item)).toContain("Hidden")
    expect(navigationToolDetail({ ...item, access: "plan_locked" })).toContain("Requires an Author")
    expect(navigationToolDetail({ ...item, hidden: false, access: "processing_blocked" })).toContain("Available after processing")
  })
})
