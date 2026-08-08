import type { Book, BookProcessing, ProcessingStage } from "@/types/book"

export type NormalizedProcessingStatus = {
  stage: ProcessingStage
  label: string
  detail: string | null
  progressPct: number | null
  chaptersCompleted: number | null
  chaptersTotal: number | null
  lastError: string | null
  retryAvailable: boolean
  resumeAvailable?: boolean
  paused?: boolean
  partialReady: boolean
  ready: boolean
  failed: boolean
  failureKind: "recoverable" | "support_required" | null
  stateVariant: "processing" | "partial_ready" | "ready" | "recoverable_failure" | "support_required"
}

const STAGE_LABELS: Record<ProcessingStage, string> = {
  queued: "Queued for processing",
  parsing: "Parsing manuscript",
  extracting: "Extracting story data",
  summarizing: "Building summaries",
  embedding: "Indexing search",
  analyzing: "Running story analysis",
  ready: "Ready",
  failed: "Processing failed",
}

const STAGE_ALIASES: Record<string, ProcessingStage> = {
  pending: "queued",
  processing: "extracting",
  upload: "queued",
  uploading: "queued",
  parse: "parsing",
  parser: "parsing",
  extraction: "extracting",
  extract: "extracting",
  summary: "summarizing",
  summaries: "summarizing",
  embedding: "embedding",
  embeddings: "embedding",
  indexing: "embedding",
  analysis: "analyzing",
  analyze: "analyzing",
  complete: "ready",
  completed: "ready",
  done: "ready",
  error: "failed",
  failed: "failed",
  cancelled: "failed",
  canceled: "failed",
}

export function normalizeProcessingStage(processing?: BookProcessing | null, book?: Pick<Book, "status"> | null): ProcessingStage {
  const status = clean(processing?.status ?? book?.status)
  const stage = clean(processing?.stage)
  if (processing?.is_fully_ready || status === "ready") return "ready"
  if (status === "failed" || status === "error" || stage === "failed" || stage === "error") return "failed"
  return STAGE_ALIASES[stage] ?? STAGE_ALIASES[status] ?? "extracting"
}

export function normalizeProcessingStatus(processing?: BookProcessing | null, book?: Pick<Book, "status"> | null): NormalizedProcessingStatus | null {
  if (!processing && (!book || book.status === "ready")) return null

  const stage = normalizeProcessingStage(processing, book)
  const progressPct = clampProgress(processing?.progress_pct)
  const chaptersCompleted = nonNegativeInt(processing?.chapters_completed)
  const chaptersTotal = nonNegativeInt(processing?.chapters_total)
  const retryActions = Array.isArray(processing?.retry_actions) ? processing.retry_actions : []
  const retryExplicitlyDisabled = processing?.retry_available === false
  const retryAvailable = Boolean(
    processing?.retry_available
    || retryActions.some((action) => action !== "wait_for_analysis")
    || (stage === "failed" && !retryExplicitlyDisabled)
    || processing?.last_error
  )
  const resumeAvailable = Boolean(
    processing?.resume_available || retryActions.includes("continue_processing")
  )
  const partialReady = stage !== "ready" && stage !== "failed" && chaptersCompleted !== null && chaptersCompleted > 0
  const detail = buildProcessingDetail(stage, chaptersCompleted, chaptersTotal, progressPct, partialReady)
  const failureKind = stage === "failed" ? (retryAvailable ? "recoverable" : "support_required") : null

  return {
    stage,
    label: resumeAvailable ? "Processing paused" : processing?.current_step_label || STAGE_LABELS[stage],
    detail: resumeAvailable
      ? processing?.resume_blockers?.[0]?.detail || "Continue when processing capacity is available"
      : detail,
    progressPct,
    chaptersCompleted,
    chaptersTotal,
    lastError: processing?.last_error || null,
    retryAvailable,
    resumeAvailable,
    paused: resumeAvailable,
    partialReady,
    ready: stage === "ready",
    failed: stage === "failed",
    failureKind,
    stateVariant: stage === "ready"
      ? "ready"
      : failureKind === "recoverable"
        ? "recoverable_failure"
        : failureKind === "support_required"
          ? "support_required"
          : partialReady
            ? "partial_ready"
            : "processing",
  }
}

function buildProcessingDetail(
  stage: ProcessingStage,
  chaptersCompleted: number | null,
  chaptersTotal: number | null,
  progressPct: number | null,
  partialReady: boolean
) {
  if (stage === "ready") return "All story tools are ready"
  if (stage === "failed") return "Retry is available"
  const chapterCopy = chaptersCompleted !== null && chaptersTotal
    ? `${chaptersCompleted}/${chaptersTotal} chapters`
    : null
  const progressCopy = progressPct !== null ? `${Math.round(progressPct)}%` : null
  if (partialReady) return ["First chapters ready", chapterCopy || progressCopy].filter(Boolean).join(" - ")
  return [chapterCopy, progressCopy].filter(Boolean).join(" - ") || "You can start reading/editing now"
}

function clean(value: unknown) {
  return String(value ?? "").trim().toLowerCase().replace(/-/g, "_")
}

function clampProgress(value: unknown) {
  if (typeof value !== "number" || Number.isNaN(value)) return null
  return Math.max(0, Math.min(100, value))
}

function nonNegativeInt(value: unknown) {
  if (typeof value !== "number" || Number.isNaN(value) || value < 0) return null
  return Math.floor(value)
}
