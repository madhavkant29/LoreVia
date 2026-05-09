import { describe, expect, it } from "vitest"

import { htmlToPlainText, renderRichTextHtml, sanitizeRichTextHtml } from "./richText"

describe("richText utilities", () => {
  it("sanitizes unsafe links and images while preserving safe formatting", () => {
    const html = [
      '<div style="text-align:center" onclick="alert(1)">',
      '  <a href="javascript:alert(1)">Bad link</a>',
      '  <a href="https://example.com/docs">Safe link</a>',
      '  <img src="javascript:alert(1)" alt="bad" onerror="alert(1)">',
      '  <img src="/covers/chapter.png" alt="Cover">',
      "  Text",
      "</div>",
    ].join("")

    const sanitized = sanitizeRichTextHtml(html)

    expect(sanitized).not.toContain("javascript:")
    expect(sanitized).not.toContain("onclick=")
    expect(sanitized).toContain('style="text-align: center;"')
    expect(sanitized).toContain('<a href="https://example.com/docs" target="_blank" rel="noreferrer noopener">Safe link</a>')
    expect(sanitized).not.toContain("Bad link</a>")
    expect(sanitized).toContain('<img src="/covers/chapter.png" alt="Cover" loading="lazy">')
    expect(sanitized).toContain("Text")
  })

  it("renders plain text input as escaped paragraphs", () => {
    const rendered = renderRichTextHtml("Hello world\nSecond line\n\nNext paragraph")

    expect(rendered).toBe("<p>Hello world<br>Second line</p><p>Next paragraph</p>")
  })

  it("extracts readable block text from rich html", () => {
    const plainText = htmlToPlainText("<h1>Title</h1><p>Lead</p><ul><li>Point A</li><li>Point B</li></ul>")

    expect(plainText).toBe("Title\n\nLead\n\nPoint A\n\nPoint B")
  })
})
