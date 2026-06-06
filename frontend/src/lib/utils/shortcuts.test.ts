import { describe, expect, it } from "vitest"

import { GLOBAL_SHORTCUTS, formatShortcutList } from "./shortcuts"

describe("shortcuts", () => {
  it("formats shortcut definitions for compact help text", () => {
    expect(formatShortcutList(GLOBAL_SHORTCUTS)).toContain("Ctrl/⌘ K: Open command palette")
  })
})
