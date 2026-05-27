import { describe, expect, it } from "vitest"

import {
  getAskLoreViaAnswerLabel,
  getAskLoreViaDescription,
  getAskLoreViaHelperText,
  getAskLoreViaScopeLabel,
} from "./askLoreVia"

describe("ask lorevia scope copy", () => {
  it("builds author-facing scope label and helper copy", () => {
    expect(getAskLoreViaScopeLabel("author", 3)).toBe("All processed chapters through Chapter 3")
    expect(getAskLoreViaDescription("author", 3)).toContain("all processed chapters through Chapter 3")
    expect(getAskLoreViaHelperText("author", 3)).toBe("Enter to ask · Shift+Enter for new line · Answers grounded through Chapter 3")
    expect(getAskLoreViaAnswerLabel("author", 3)).toBe("Answer · Processed through Chapter 3")
  })

  it("builds reader-facing scope label and helper copy", () => {
    expect(getAskLoreViaScopeLabel("reader", 5)).toBe("Up to Chapter 5")
    expect(getAskLoreViaDescription("reader", 5)).toContain("chapters 1-5")
    expect(getAskLoreViaHelperText("reader", 5)).toBe("Enter to ask · Shift+Enter for new line · Answers grounded in Chapters 1-5")
    expect(getAskLoreViaAnswerLabel("reader", 5)).toBe("Answer · Chapters 1-5")
  })
})
