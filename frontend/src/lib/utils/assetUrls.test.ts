import { describe, expect, it } from "vitest"

import { resolveAssetUrl, resolveMediaAssetSrc } from "./assetUrls"

describe("asset url helpers", () => {
  it("resolves relative api assets against the current origin", () => {
    expect(resolveAssetUrl("/api/v1/books/demo/cover")).toBe(
      new URL("/api/v1/books/demo/cover", window.location.origin).toString(),
    )
  })

  it("keeps absolute asset urls intact", () => {
    expect(resolveAssetUrl("https://cdn.example.com/cover.png")).toBe("https://cdn.example.com/cover.png")
  })

  it("falls back to base64 media when url is missing", () => {
    expect(
      resolveMediaAssetSrc({
        content_base64: "YWJj",
        content_type: "image/png",
      }),
    ).toBe("data:image/png;base64,YWJj")
  })

  it("prefers a resolved media url over base64 fallback", () => {
    expect(
      resolveMediaAssetSrc({
        url: "/api/v1/reader/media/demo",
        content_base64: "YWJj",
        content_type: "image/png",
      }),
    ).toBe(new URL("/api/v1/reader/media/demo", window.location.origin).toString())
  })
})
