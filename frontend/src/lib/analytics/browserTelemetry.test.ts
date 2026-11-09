import { beforeEach, describe, expect, it, vi } from "vitest"

const captureMock = vi.hoisted(() => vi.fn())

vi.mock("@/lib/analytics/posthog", () => ({ capture: captureMock }))

import {
  captureApiFailure,
  captureCaughtRenderError,
  captureWebVital,
  installBrowserErrorTelemetry,
  normalizedTelemetryPath,
} from "./browserTelemetry"

describe("browser telemetry", () => {
  beforeEach(() => captureMock.mockReset())

  it("strips query data and normalizes identifiers from request paths", () => {
    expect(
      normalizedTelemetryPath(
        "/books/123e4567-e89b-42d3-a456-426614174000/chapters/42?token=secret",
      ),
    ).toBe("/books/:id/chapters/:id")
  })

  it("captures server failures with request correlation but no response body", () => {
    captureApiFailure({
      code: "ERR_BAD_RESPONSE",
      config: { method: "post", url: "/books/123e4567-e89b-42d3-a456-426614174000?draft=private" },
      response: {
        headers: { "x-request-id": "request-123" },
        status: 503,
      },
    })

    expect(captureMock).toHaveBeenCalledWith("api_request_failed", {
      code: "ERR_BAD_RESPONSE",
      method: "POST",
      path: "/books/:id",
      request_id: "request-123",
      status: 503,
    })
  })

  it("does not report expected client errors or cancellation", () => {
    captureApiFailure({ config: { url: "/books" }, response: { status: 422 } })
    captureApiFailure({ code: "ERR_CANCELED", config: { url: "/books" } })
    expect(captureMock).not.toHaveBeenCalled()
  })

  it("captures Web Vitals without page content", () => {
    captureWebVital({
      id: "vital-1",
      name: "LCP",
      navigationType: "navigate",
      rating: "good",
      value: 812.5,
    })
    expect(captureMock).toHaveBeenCalledWith("browser_web_vital", {
      id: "vital-1",
      name: "LCP",
      navigation_type: "navigate",
      rating: "good",
      value: 812.5,
    })
  })

  it("reports caught render failures without exception messages or page content", () => {
    captureCaughtRenderError(new TypeError("private manuscript text"), "route")
    expect(captureMock).toHaveBeenCalledWith("browser_caught_render_error", {
      area: "route",
      error_type: "TypeError",
    })
    expect(JSON.stringify(captureMock.mock.calls)).not.toContain("private manuscript text")
  })

  it("registers metadata-only global error handlers and removes them", () => {
    const addEventListener = vi.fn()
    const removeEventListener = vi.fn()
    const cleanup = installBrowserErrorTelemetry({
      addEventListener,
      removeEventListener,
    } as unknown as Window)

    const errorHandler = addEventListener.mock.calls.find(([name]) => name === "error")?.[1]
    const rejectionHandler = addEventListener.mock.calls.find(
      ([name]) => name === "unhandledrejection",
    )?.[1]
    errorHandler({ error: new TypeError("private manuscript text"), filename: "https://app.test/app.js?secret" })
    rejectionHandler({ reason: new RangeError("private manuscript text") })

    expect(captureMock).toHaveBeenNthCalledWith(1, "browser_uncaught_error", {
      error_type: "TypeError",
      source_path: "/app.js",
    })
    expect(captureMock).toHaveBeenNthCalledWith(2, "browser_unhandled_rejection", {
      error_type: "RangeError",
    })

    cleanup()
    expect(removeEventListener).toHaveBeenCalledTimes(2)
  })
})
