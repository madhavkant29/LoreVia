import { describe, expect, it } from "vitest"

import { metadata } from "./layout"
import manifest from "./manifest"

describe("app metadata", () => {
  it("declares stable root icon URLs for crawlers and browsers", () => {
    expect(metadata.icons).toMatchObject({
      icon: expect.arrayContaining([
        expect.objectContaining({ url: "/favicon.ico", sizes: "any" }),
        expect.objectContaining({ url: "/favicon-16x16.png", sizes: "16x16", type: "image/png" }),
        expect.objectContaining({ url: "/favicon-32x32.png", sizes: "32x32", type: "image/png" }),
        expect.objectContaining({ url: "/icon-192.png", sizes: "192x192", type: "image/png" }),
        expect.objectContaining({ url: "/icon-512.png", sizes: "512x512", type: "image/png" }),
      ]),
      apple: expect.arrayContaining([
        expect.objectContaining({ url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" }),
        expect.objectContaining({ url: "/apple-icon.png", sizes: "180x180", type: "image/png" }),
      ]),
      shortcut: "/favicon.ico",
    })
  })

  it("keeps the web manifest pointed at stable app icons", () => {
    expect(manifest().icons).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ src: "/icon-192.png", sizes: "192x192", type: "image/png" }),
        expect.objectContaining({ src: "/icon-512.png", sizes: "512x512", type: "image/png" }),
      ]),
    )
  })
})
