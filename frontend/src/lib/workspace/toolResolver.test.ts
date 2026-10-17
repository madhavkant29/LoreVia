import { describe, expect, it } from "vitest"

import { applyBookPreferenceOperations, applyUserPreferenceOperations, defaultBookUiPreference, defaultUserUiPreference } from "@/lib/stores/uiPreferencesStore"
import { workspaceToolRegistry } from "@/lib/workspace/toolRegistry"
import { resolveWorkspaceTool } from "@/lib/workspace/toolResolver"
import type { Book } from "@/types/book"

function tool(id: string) {
  const found = workspaceToolRegistry.find((entry) => entry.id === id)
  if (!found) throw new Error(`Missing registry tool ${id}`)
  return found
}

function book(overrides: Partial<Book> = {}) {
  return {
    id: "book-1",
    title: "Draft",
    status: "ready",
    collaboration_role: null,
    collaboration_permissions: null,
    ...overrides,
  } as Book
}

describe("workspace tool resolver", () => {
  it("keeps non-hideable anchors visible even when a user preference tries to hide them", () => {
    const preference = defaultUserUiPreference("focused")
    preference.dashboard_visibility["dashboard.library"] = "user_hidden"

    const resolved = resolveWorkspaceTool(tool("dashboard.library"), {
      mode: "focused",
      globalPreference: preference,
    })

    expect(resolved.visibility).toBe("visible")
    expect(resolved.hidden).toBe(false)
  })

  it("temporarily reveals a hidden active route without mutating access", () => {
    const bookPreference = defaultBookUiPreference("book-1")
    bookPreference.hidden_book_tools = ["book.search"]

    const resolved = resolveWorkspaceTool(tool("book.search"), {
      mode: "focused",
      activePath: "/book-1/search",
      book: book(),
      bookPreference,
    })

    expect(resolved.visibility).toBe("temporarily_revealed")
    expect(resolved.hidden).toBe(false)
    expect(resolved.access).toBe("available")
  })

  it("keeps permission state separate from visibility", () => {
    const resolved = resolveWorkspaceTool(tool("book.manuscript"), {
      mode: "standard",
      book: book({
        collaboration_role: "editor",
        collaboration_permissions: {
          can_edit_manuscript: false,
          can_view_story_bible: false,
          can_run_ai_scans: false,
          can_export: false,
          can_comment: false,
        },
      } as Partial<Book>),
      bookPreference: defaultBookUiPreference("book-1"),
    })

    expect(resolved.access).toBe("permission_denied")
    expect(resolved.visibility).toBe("visible")
    expect(resolved.hidden).toBe(false)
  })

  it("lets power mode bypass preset hiding but not explicit user hiding", () => {
    const bookPreference = defaultBookUiPreference("book-1")

    const standard = resolveWorkspaceTool(tool("book.relationships"), {
      mode: "standard",
      book: book(),
      bookPreference,
    })
    const power = resolveWorkspaceTool(tool("book.relationships"), {
      mode: "power",
      book: book(),
      bookPreference,
    })

    bookPreference.hidden_book_tools = ["book.relationships"]
    const userHidden = resolveWorkspaceTool(tool("book.relationships"), {
      mode: "power",
      book: book(),
      bookPreference,
    })

    expect(standard.reason).toBe("hidden_by_preset")
    expect(power.hidden).toBe(false)
    expect(userHidden.reason).toBe("hidden_by_user")
    expect(userHidden.hidden).toBe(true)
  })

  it("reveals standard tools when a focused user explicitly shows advanced tools", () => {
    const bookPreference = defaultBookUiPreference("book-1", "focused")

    const hidden = resolveWorkspaceTool(tool("book.scenes"), {
      mode: "focused",
      book: book(),
      bookPreference,
    })
    bookPreference.advanced_tool_override = "show"
    const revealed = resolveWorkspaceTool(tool("book.scenes"), {
      mode: "focused",
      book: book(),
      bookPreference,
    })

    expect(hidden.reason).toBe("hidden_by_mode")
    expect(revealed.visibility).toBe("visible")
    expect(revealed.hidden).toBe(false)
  })

  it("keeps pricing visible for unpaid users even when navigation visibility is hidden", () => {
    const preference = defaultUserUiPreference("standard")
    preference.dashboard_visibility["dashboard.pricing"] = "user_hidden"

    const resolved = resolveWorkspaceTool(tool("dashboard.pricing"), {
      mode: "standard",
      globalPreference: preference,
      paidUser: false,
    })

    expect(resolved.visibility).toBe("visible")
    expect(resolved.hidden).toBe(false)
  })

  it("reports permission denial before processing state", () => {
    const resolved = resolveWorkspaceTool(tool("book.advisor"), {
      mode: "standard",
      book: book({
        status: "processing",
        collaboration_role: "viewer",
        collaboration_permissions: {
          can_edit_manuscript: false,
          can_view_story_bible: false,
          can_run_ai_scans: false,
          can_export: false,
          can_comment: false,
        },
      } as Partial<Book>),
      bookPreference: defaultBookUiPreference("book-1", "standard"),
    })

    expect(resolved.access).toBe("permission_denied")
  })

  it("uses public visibility preferences before dashboard visibility", () => {
    const preference = defaultUserUiPreference("standard")
    preference.dashboard_visibility["dashboard.public_uploads"] = "visible"
    preference.public_tool_visibility["dashboard.public_uploads"] = "user_hidden"

    const resolved = resolveWorkspaceTool(tool("dashboard.public_uploads"), {
      mode: "standard",
      globalPreference: preference,
    })

    expect(resolved.reason).toBe("hidden_by_user")
  })

  it("does not mark an already visible active route as temporarily revealed", () => {
    const preference = defaultBookUiPreference("book-1", "standard")
    const resolved = resolveWorkspaceTool(tool("book.manuscript"), {
      mode: "standard",
      activePath: "/book-1/manuscript",
      book: book(),
      bookPreference: preference,
    })

    expect(resolved.visibility).toBe("visible")
  })
})

describe("ui preference operation replay", () => {
  it("applies global operations immutably", () => {
    const preference = defaultUserUiPreference("standard")

    const next = applyUserPreferenceOperations(preference, [
      { op: "set", path: "/complexity_mode", value: "power" },
      { op: "set", path: "/dashboard_visibility/dashboard.stats", value: "user_hidden" },
    ])

    expect(next.complexity_mode).toBe("power")
    expect(next.dashboard_visibility["dashboard.stats"]).toBe("user_hidden")
    expect(preference.complexity_mode).toBe("standard")
    expect(preference.dashboard_visibility["dashboard.stats"]).toBeUndefined()
  })

  it("applies book operations immutably", () => {
    const preference = defaultBookUiPreference("book-1")

    const next = applyBookPreferenceOperations(preference, [
      { op: "set", path: "/book_preset", value: "review" },
      { op: "set", path: "/timeline_collapsed_sections/characters", value: true },
    ])

    expect(next.book_preset).toBe("review")
    expect(next.timeline_collapsed_sections.characters).toBe(true)
    expect(preference.book_preset).toBe("draft")
    expect(preference.timeline_collapsed_sections.characters).toBeUndefined()
  })
})
