import { capture } from "@/lib/analytics/posthog"

const UUID_PATH_SEGMENT = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
const INTEGER_PATH_SEGMENT = /^\d+$/

export function normalizedTelemetryPath(value: unknown): string {
  const raw = String(value ?? "").trim()
  if (!raw) return "unknown"

  let pathname = raw.split(/[?#]/, 1)[0] || "/"
  try {
    pathname = new URL(raw, "https://telemetry.invalid").pathname
  } catch {
    // Keep the already query-free relative path when URL parsing fails.
  }

  return pathname
    .split("/")
    .map((segment) =>
      UUID_PATH_SEGMENT.test(segment) || INTEGER_PATH_SEGMENT.test(segment) ? ":id" : segment,
    )
    .join("/")
    .slice(0, 240)
}

function errorType(value: unknown): string {
  if (value instanceof Error) return value.name || "Error"
  if (value === null) return "null"
  return typeof value
}

export function captureApiFailure(error: {
  code?: unknown
  config?: { method?: unknown; url?: unknown }
  response?: { headers?: Record<string, unknown>; status?: unknown }
}): void {
  const status = Number(error.response?.status || 0)
  const code = String(error.code ?? "").trim().slice(0, 80)
  if (code === "ERR_CANCELED" || (status > 0 && status < 500)) return

  const responseHeaders = error.response?.headers ?? {}
  const requestId = String(
    responseHeaders["x-request-id"] ?? responseHeaders["X-Request-ID"] ?? "",
  )
    .trim()
    .slice(0, 120)

  capture("api_request_failed", {
    code: code || undefined,
    method: String(error.config?.method ?? "get").toUpperCase().slice(0, 12),
    path: normalizedTelemetryPath(error.config?.url),
    request_id: requestId || undefined,
    status: status || undefined,
  })
}

export function captureCaughtRenderError(error: unknown, area: "route" | "chat_panel"): void {
  capture("browser_caught_render_error", {
    area,
    error_type: errorType(error),
  })
}

export function captureWebVital(metric: {
  id: string
  name: string
  navigationType?: string
  rating?: string
  value: number
}): void {
  capture("browser_web_vital", {
    id: metric.id.slice(0, 120),
    name: metric.name.slice(0, 40),
    navigation_type: metric.navigationType?.slice(0, 40),
    rating: metric.rating?.slice(0, 20),
    value: metric.value,
  })
}

export function installBrowserErrorTelemetry(target: Window = window): () => void {
  const onError = (event: ErrorEvent) => {
    capture("browser_uncaught_error", {
      error_type: errorType(event.error),
      source_path: normalizedTelemetryPath(event.filename),
    })
  }
  const onUnhandledRejection = (event: PromiseRejectionEvent) => {
    capture("browser_unhandled_rejection", {
      error_type: errorType(event.reason),
    })
  }

  target.addEventListener("error", onError)
  target.addEventListener("unhandledrejection", onUnhandledRejection)
  return () => {
    target.removeEventListener("error", onError)
    target.removeEventListener("unhandledrejection", onUnhandledRejection)
  }
}
