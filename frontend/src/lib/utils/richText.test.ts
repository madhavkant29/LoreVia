import { afterEach, describe, expect, it, vi } from "vitest"

import { htmlToPlainText, renderMarkdownHtml, renderRichTextHtml, sanitizeRichTextHtml } from "./richText"

describe("richText utilities", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

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

  it("rejects protocol-relative links and svg data images", () => {
    const html = [
      '<a href="//evil.example/path">Protocol relative</a>',
      '<a href="/safe/path">Safe relative</a>',
      '<img src="data:image/svg+xml;base64,PHN2Zy8+" alt="svg">',
      '<img src="data:image/png;base64,iVBORw0KGgo=" alt="png">',
    ].join("")

    const sanitized = sanitizeRichTextHtml(html)

    expect(sanitized).not.toContain("//evil.example")
    expect(sanitized).toContain('<a href="/safe/path" target="_blank" rel="noreferrer noopener">Safe relative</a>')
    expect(sanitized).not.toContain("data:image/svg+xml")
    expect(sanitized).toContain('src="data:image/png;base64,iVBORw0KGgo="')
  })

  it("does not return raw html when sanitized during server rendering", () => {
    vi.stubGlobal("window", undefined)

    const sanitized = sanitizeRichTextHtml('<img src=x onerror="alert(1)"><script>alert(2)</script><p>Safe</p>')

    expect(sanitized).not.toContain("<script")
    expect(sanitized).not.toContain("onerror")
    expect(sanitized).toContain("<p>")
    expect(sanitized).toContain("Safe")
  })

  it("renders plain text input as escaped paragraphs", () => {
    const rendered = renderRichTextHtml("Hello world\nSecond line\n\nNext paragraph")

    expect(rendered).toBe("<p>Hello world<br>Second line</p><p>Next paragraph</p>")
  })

  it("renders markdown as safe formatted html", () => {
    const rendered = renderMarkdownHtml("**Bold**\n*Italic*\n\n<script>alert(1)</script>")

    expect(rendered).toContain("<strong>Bold</strong>")
    expect(rendered).toContain("<em>Italic</em>")
    expect(rendered).not.toContain("<script>")
    expect(rendered).toContain("&lt;script&gt;alert(1)&lt;/script&gt;")
  })

  it("extracts readable block text from rich html", () => {
    const plainText = htmlToPlainText("<h1>Title</h1><p>Lead</p><ul><li>Point A</li><li>Point B</li></ul>")

    expect(plainText).toBe("Title\n\nLead\n\nPoint A\n\nPoint B")
  })

  it("preserves scene breaks, page breaks, and inline styling metadata", () => {
    const html = [
      '<p style="color: rgb(29, 78, 216); font-size: 16px; font-family: Georgia;">Styled line</p>',
      '<div data-scene-break="true">ignore me</div>',
      '<div data-page-break="true">ignore me too</div>',
      '<mark style="background-color: rgb(254, 240, 138);">Highlight</mark>',
    ].join("")

    const sanitized = sanitizeRichTextHtml(html)

    expect(sanitized).toContain('data-scene-break="true"')
    expect(sanitized).toContain('class="scene-break-node"')
    expect(sanitized).toContain("***")
    expect(sanitized).toContain('data-page-break="true"')
    expect(sanitized).toContain("Page break")
    expect(sanitized).toContain("font-size: 16px;")
    expect(sanitized).toContain("font-family: Georgia;")
    expect(sanitized).toContain("background-color: rgb(254, 240, 138);")
  })
})
