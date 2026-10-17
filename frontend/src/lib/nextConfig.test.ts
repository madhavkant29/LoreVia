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
    delete process.env.API_ORIGIN
    Object.assign(process.env, { NODE_ENV: "development" })

    const nextConfig = loadNextConfig()
    const rewrites = await nextConfig.rewrites()

    expect(rewrites).toEqual([
      {
        source: "/api/v1/:path*",
        destination: "http://localhost:8000/api/v1/:path*",
      },
    ])
    expect(nextConfig.headers).toBeUndefined()
    expect(nextConfig.experimental.webpackBuildWorker).toBe(false)
  })

  it("routes api traffic to the configured server-side origin in production", async () => {
    Object.assign(process.env, {
      NODE_ENV: "production",
      API_ORIGIN: "https://api.getlorevia.com",
    })

    const nextConfig = loadNextConfig()
    const rewrites = await nextConfig.rewrites()

    expect(rewrites).toEqual([
      {
        source: "/api/v1/:path*",
        destination: "https://api.getlorevia.com/api/v1/:path*",
      },
    ])
    expect(nextConfig.headers).toBeUndefined()
  })

  it("falls back to NEXT_PUBLIC_API_URL for rewrites when API_ORIGIN is not set", async () => {
    delete process.env.API_ORIGIN
    Object.assign(process.env, {
      NODE_ENV: "production",
      NEXT_PUBLIC_API_URL: "https://staging.getlorevia.com/api/v1",
    })

    const nextConfig = loadNextConfig()
    const rewrites = await nextConfig.rewrites()

    expect(rewrites).toEqual([
      {
        source: "/api/v1/:path*",
        destination: "https://staging.getlorevia.com/api/v1/:path*",
      },
    ])
  })
})
