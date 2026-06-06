// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from "vitest"

import {
  choosePrimaryEmptyStateAction,
  filterCommandActions,
  getRecentCommandActions,
  loadRecentCommandActionIds,
  recordRecentCommandAction,
} from "./uxActions"
import type { CommandAction, SmartEmptyStateAction } from "@/types/ux"

const actions: CommandAction[] = [
  { id: "library", label: "Open Library", group: "Navigation", keywords: ["projects"] },
  { id: "ask", label: "Ask LoreVia", group: "Project tools", keywords: ["citations", "questions"] },
  { id: "graph", label: "Open relationship graph", group: "Story bible", keywords: ["characters"] },
]
const storage = new Map<string, string>()

vi.stubGlobal("localStorage", {
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, value),
  removeItem: (key: string) => storage.delete(key),
})

Object.defineProperty(window, "localStorage", {
  configurable: true,
  value: globalThis.localStorage,
})

beforeEach(() => {
  storage.clear()
})

describe("uxActions", () => {
  it("filters commands by label, group, and keywords", () => {
    expect(filterCommandActions(actions, "library").map((action) => action.id)).toEqual(["library"])
    expect(filterCommandActions(actions, "story characters").map((action) => action.id)).toEqual(["graph"])
    expect(filterCommandActions(actions, "missing")).toEqual([])
  })

  it("records recent command ids without duplicates", () => {
    recordRecentCommandAction("library")
    recordRecentCommandAction("ask")
    recordRecentCommandAction("library")

    expect(loadRecentCommandActionIds()).toEqual(["library", "ask"])
    expect(getRecentCommandActions(actions).map((action) => action.id)).toEqual(["library", "ask"])
  })

  it("chooses the primary empty-state action when available", () => {
    const emptyActions: SmartEmptyStateAction[] = [
      { label: "Secondary", tone: "secondary" },
      { label: "Primary", tone: "primary" },
    ]

    expect(choosePrimaryEmptyStateAction(emptyActions)?.label).toBe("Primary")
    expect(choosePrimaryEmptyStateAction([{ label: "Only" }])?.label).toBe("Only")
  })
})
