import { describe, expect, it } from "vitest"

import { detectPublishedBlockType, parsePublishedTextBlocks } from "./publishedLayout"

describe("published layout utilities", () => {
  it("parses blank-line separated prose into normal paragraphs", () => {
    const blocks = parsePublishedTextBlocks("The door opened.\n\nA candle guttered in the hall.")

    expect(blocks).toEqual([
      { type: "paragraph", content: "The door opened." },
      { type: "paragraph", content: "A candle guttered in the hall." },
    ])
  })

  it("detects scene breaks between paragraphs", () => {
    const blocks = parsePublishedTextBlocks("The room went quiet.\n\n* * *\n\nMorning came cold.")

    expect(blocks.map((block) => block.type)).toEqual(["paragraph", "scene_break", "paragraph"])
    expect(blocks[1]?.content).toBe("* * *")
  })

  it("detects em-dash scene breaks used in novel formatting", () => {
    const blocks = parsePublishedTextBlocks("The room went quiet.\n\n\u2014\u2014\u2014\n\nMorning came cold.")

    expect(blocks.map((block) => block.type)).toEqual(["paragraph", "scene_break", "paragraph"])
    expect(blocks[1]?.content).toBe("\u2014\u2014\u2014")
  })

  it("detects quoted documents and removes markdown quote markers", () => {
    const blocks = parsePublishedTextBlocks("> CASE FILE 17\n> The witness refused to sign.")

    expect(blocks).toEqual([
      { type: "quote", content: "CASE FILE 17\nThe witness refused to sign." },
    ])
  })

  it("detects broadcasts as inset blocks", () => {
    expect(detectPublishedBlockType("RADIO: Evacuation routes remain closed.")).toBe("broadcast")
    expect(detectPublishedBlockType("News: The harbor lights failed at dawn.")).toBe("broadcast")
  })

  it("detects letters, poems, and system artifacts without changing manuscript text", () => {
    expect(detectPublishedBlockType("Dear Mara,\nI found the key.\nYours,\nN.")).toBe("letter")
    expect(detectPublishedBlockType("Ash in the garden\nRain on the stair\nNobody answers")).toBe("poem")
    expect(detectPublishedBlockType("SYSTEM: Memory archive restored.")).toBe("artifact")
  })
})
