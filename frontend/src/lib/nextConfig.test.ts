import path from "node:path"
import { createRequire } from "node:module"

import { afterEach, describe, expect, it } from "vitest"

const require = createRequire(import.meta.url)
const configPath = path.resolve(process.cwd(), "next.config.js")

function loadNextConfig() {
  delete require.cache[configPath]
  return require(configPath)
}

describe("next config", () => {
  const originalEnv = { ...process.env }

  afterEach(() => {
    process.env = { ...originalEnv }
    delete require.cache[configPath]
  })

  it("uses the local backend rewrite in development when no public api url is configured", async () => {
    delete process.env.NEXT_PUBLIC_API_URL
    process.env.NODE_ENV = "development"

    const nextConfig = loadNextConfig()
    const rewrites = await nextConfig.rewrites()

    expect(rewrites).toEqual([
      {
        source: "/api/v1/:path*",
        destination: "http://localhost:8000/api/v1/:path*",
      },
    ])
    expect(await nextConfig.headers()).toEqual([])
  })

  it("emits hardened production headers and routes api traffic to the configured origin", async () => {
    process.env.NODE_ENV = "production"
    process.env.NEXT_PUBLIC_API_URL = "https://staging.getlorevia.com/api/v1"

    const nextConfig = loadNextConfig()
    const rewrites = await nextConfig.rewrites()
    const headers = await nextConfig.headers()
    const headerMap = new Map(headers[0].headers.map((header: { key: string; value: string }) => [header.key, header.value]))
    const csp = headerMap.get("Content-Security-Policy") ?? ""

    expect(rewrites).toEqual([
      {
        source: "/api/v1/:path*",
        destination: "https://staging.getlorevia.com/api/v1/:path*",
      },
    ])
    expect(headerMap.get("X-Frame-Options")).toBe("DENY")
    expect(headerMap.get("X-Content-Type-Options")).toBe("nosniff")
    expect(headerMap.get("Permissions-Policy")).toContain("camera=()")
    expect(csp).toContain("frame-ancestors 'none'")
    expect(csp).toContain("object-src 'none'")
    expect(csp).toContain("https://staging.getlorevia.com")
  })
})
