// @vitest-environment jsdom

import { describe, expect, it } from "vitest"

import {
  button,
  click,
  firstField,
  intelligenceApiMock,
  renderElement,
  setFieldValue,
  text,
} from "./runtime-zero-components.test-utils"

import { WhatsTheWordPanel } from "@/components/intelligence/WhatsTheWordPanel"

describe("what's the word runtime coverage", () => {
  it("opens the word finder, requests suggestions, retries, and handles errors", async () => {
    await renderElement(<WhatsTheWordPanel bookId="book-1" isDark className="panel" />)

    expect(text()).toContain("What's the word")
    await click("What's the word")
    expect(text()).toContain("Word finder")
    expect(text()).toContain("0 /")
    expect((button("Find word") as HTMLButtonElement).disabled).toBe(true)

    setFieldValue(
      firstField<HTMLTextAreaElement>("textarea"),
      "a smile that hides contempt behind polished manners",
    )
    expect((button("Find word") as HTMLButtonElement).disabled).toBe(false)
    await click("Find word")
    expect(intelligenceApiMock.whatsTheWordStream).toHaveBeenCalledWith(
      "book-1",
      "a smile that hides contempt behind polished manners",
      null,
      expect.any(Object),
    )
    expect(text()).toContain("smirk")
    expect(text()).toContain("A smile with concealed contempt.")

    await click("Try again")
    expect(intelligenceApiMock.whatsTheWordStream).toHaveBeenLastCalledWith(
      "book-1",
      "a smile that hides contempt behind polished manners",
      "smirk",
      expect.any(Object),
    )

    intelligenceApiMock.whatsTheWordStream.mockRejectedValueOnce(new Error("provider down"))
    setFieldValue(
      firstField<HTMLTextAreaElement>("textarea"),
      "a voice that sounds bitter while staying calm",
    )
    await click("Find word")
    expect(text()).toContain("Couldn't find the word right now")

    await click("Hide what's the word")
    expect(text()).not.toContain("Word finder")
  })
})
