import { describe, expect, it } from "vitest"

import { GET } from "./rss.xml/route"

describe("blog rss feed", () => {
  it("returns a valid rss feed for the public blog content", async () => {
    const response = await GET()
    const body = await response.text()

    expect(response.headers.get("Content-Type")).toContain("application/rss+xml")
    expect(body).toContain("<title>LoreVia Blog</title>")
    expect(body).toContain("<link>https://getlorevia.com/blog</link>")
    expect(body).toContain("https://getlorevia.com/blog/how-to-track-characters-in-a-novel")
    expect(body).toContain("<pubDate>Thu, 14 May 2026 00:00:00 GMT</pubDate>")
  })
})
