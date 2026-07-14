import React from "react"
import { afterEach, beforeEach, vi } from "vitest"

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    prefetch: _prefetch,
    replace: _replace,
    scroll: _scroll,
    shallow: _shallow,
    locale: _locale,
    ...props
  }: {
    href: string
    children: React.ReactNode
    prefetch?: boolean | null
    replace?: boolean
    scroll?: boolean
    shallow?: boolean
    locale?: string | false
    [key: string]: unknown
  }) => React.createElement("a", { href, ...props }, children),
}))

const originalConsoleError = console.error
const originalConsoleWarn = console.warn

let unexpectedConsoleMessages: string[] = []

const KNOWN_LEGACY_WARNING_PATTERNS = [
  /was not wrapped in act\(\.\.\.\)/,
  /Each child in a list should have a unique "key" prop/,
]

const isKnownLegacyWarning = (message: string) =>
  KNOWN_LEGACY_WARNING_PATTERNS.some((pattern) => pattern.test(message))

const formatConsoleMessage = (level: "error" | "warn", args: unknown[]) => {
  const message = args
    .map((item) => {
      if (item instanceof Error) return item.stack ?? item.message
      if (typeof item === "string") return item
      try {
        return JSON.stringify(item)
      } catch {
        return String(item)
      }
    })
    .join(" ")
  return `${level}: ${message}`
}

beforeEach(() => {
  unexpectedConsoleMessages = []
  vi.spyOn(console, "error").mockImplementation((...args: unknown[]) => {
    const message = formatConsoleMessage("error", args)
    unexpectedConsoleMessages.push(message)
    if (!isKnownLegacyWarning(message)) originalConsoleError(...args)
  })
  vi.spyOn(console, "warn").mockImplementation((...args: unknown[]) => {
    const message = formatConsoleMessage("warn", args)
    unexpectedConsoleMessages.push(message)
    if (!isKnownLegacyWarning(message)) originalConsoleWarn(...args)
  })
})

afterEach(() => {
  const messages = unexpectedConsoleMessages.filter((message) => !isKnownLegacyWarning(message))
  vi.restoreAllMocks()
  if (messages.length > 0) {
    throw new Error(`Unexpected console output during test:\n${messages.join("\n")}`)
  }
})
