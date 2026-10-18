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
  autoResume?: boolean
  nextResumeAt?: string | null
  paused?: boolean
  partialReady: boolean
  ready: boolean
  failed: boolean
  frozen: boolean
  failureKind: "recoverable" | "support_required" | null
  stateVariant: "processing" | "partial_ready" | "ready" | "recoverable_failure" | "support_required" | "frozen"
}

const FROZEN_FALLBACK_DETAIL =
  "Import interrupted - please upload again. Your project and files have been preserved."

const STAGE_LABELS: Record<ProcessingStage, string> = {
  queued: "Queued for processing",
  parsing: "Parsing manuscript",
  extracting: "Extracting story data",
  summarizing: "Building summaries",
  embedding: "Indexing search",
  analyzing: "Running story analysis",
  ready: "Ready",
  failed: "Processing failed",
  frozen: "Import interrupted",
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
  frozen: "frozen",
}

export function normalizeProcessingStage(processing?: BookProcessing | null, book?: Pick<Book, "status"> | null): ProcessingStage {
  if (processing?.frozen) return "frozen"
  const status = clean(processing?.status ?? book?.status)
  const stage = clean(processing?.stage)
  if (processing?.is_fully_ready || status === "ready") return "ready"
  if (status === "failed" || status === "error" || stage === "failed" || stage === "error") return "failed"
  return STAGE_ALIASES[stage] ?? STAGE_ALIASES[status] ?? "extracting"
}

export function normalizeProcessingStatus(processing?: BookProcessing | null, book?: Pick<Book, "status"> | null): NormalizedProcessingStatus | null {
  if (!processing && (!book || book.status === "ready")) return null

  const reportedStage = normalizeProcessingStage(processing, book)
  const analysisFailed = reportedStage !== "ready" && reportedStage !== "frozen" && processing?.pipeline?.analysis?.status === "failed"
  const stage = analysisFailed ? "failed" : reportedStage
  const frozen = stage === "frozen"
  const chaptersCompleted = nonNegativeInt(analysisFailed
    ? processing?.pipeline?.analysis?.completed_chapters
    : processing?.chapters_completed)
  const chaptersTotal = nonNegativeInt(analysisFailed
    ? processing?.pipeline?.analysis?.total_chapters
    : processing?.chapters_total)
  const progressPct = analysisFailed && chaptersCompleted !== null && chaptersTotal
    ? clampProgress((chaptersCompleted / chaptersTotal) * 100)
    : clampProgress(processing?.progress_pct)
  const retryActions = Array.isArray(processing?.retry_actions) ? processing.retry_actions : []
  const retryExplicitlyDisabled = processing?.retry_available === false
  const blocker = processing?.resume_blockers?.[0]
  const autoResume = !analysisFailed && Boolean(
    processing?.auto_resume
    || (processing?.pause_reason === "llm_token_limit" && blocker?.auto_resume)
  )
  const nextResumeAt = processing?.next_resume_at || blocker?.next_resume_at || null
  const resumeAvailable = !frozen && !analysisFailed && !autoResume && Boolean(
    processing?.resume_available || retryActions.includes("continue_processing")
  )
  const retryAvailable = !frozen && !autoResume && !resumeAvailable && !retryExplicitlyDisabled && Boolean(
    retryActions.some((action) => action !== "wait_for_analysis" && action !== "continue_processing")
    || stage === "failed"
  )
  const partialReady = stage !== "ready" && stage !== "failed" && stage !== "frozen" && chaptersCompleted !== null && chaptersCompleted > 0
  const detail = frozen
    ? FROZEN_FALLBACK_DETAIL
    : analysisFailed
      ? retryAvailable
        ? `${chaptersCompleted ?? 0}/${chaptersTotal ?? 0} chapters analysed. Retry failed analysis to finish processing.`
        : "Story analysis did not finish. Contact support for help."
    : autoResume
      ? buildAutoResumeDetail(blocker?.kind, nextResumeAt, chaptersCompleted, chaptersTotal)
      : buildProcessingDetail(stage, chaptersCompleted, chaptersTotal, progressPct, partialReady)
  const failureKind = stage === "failed" ? (retryAvailable ? "recoverable" : "support_required") : null

  return {
    stage,
    label: frozen ? "Import interrupted" : analysisFailed ? "Story analysis incomplete" : resumeAvailable || autoResume ? "Processing paused" : processing?.current_step_label || STAGE_LABELS[stage],
    detail: resumeAvailable
      ? blocker?.detail || "Continue when processing capacity is available"
      : detail,
    progressPct,
    chaptersCompleted,
    chaptersTotal,
    lastError: frozen || autoResume || stage !== "failed" ? null : processing?.last_error || null,
    retryAvailable,
    resumeAvailable,
    autoResume,
    nextResumeAt,
    paused: resumeAvailable || autoResume,
    partialReady,
    ready: stage === "ready",
    failed: stage === "failed",
    frozen,
    failureKind,
    stateVariant: stage === "ready"
      ? "ready"
      : frozen
        ? "frozen"
        : failureKind === "recoverable"
          ? "recoverable_failure"
          : failureKind === "support_required"
            ? "support_required"
            : partialReady
              ? "partial_ready"
              : "processing",
  }
}

function buildAutoResumeDetail(
  blockerKind: string | undefined,
  nextResumeAt: string | null,
  chaptersCompleted: number | null,
  chaptersTotal: number | null,
) {
  const parsed = nextResumeAt ? new Date(nextResumeAt) : null
  const scheduledResume = parsed && !Number.isNaN(parsed.getTime()) ? parsed : null
  let resumeCopy: string
  if (blockerKind === "llm_capacity") {
    resumeCopy = scheduledResume
      ? `AI processing capacity is temporarily busy. Reprocessing will retry automatically around ${scheduledResume.toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}.`
      : "AI processing capacity is temporarily busy. Reprocessing will retry automatically shortly."
  } else {
    const limitLabel = blockerKind === "llm_budget" ? "Monthly AI capacity" : "Token limit"
    const fallbackLabel = blockerKind === "llm_budget" ? "the monthly reset" : "the rolling window refreshes"
    resumeCopy = scheduledResume
      ? `${limitLabel} reached. Reprocessing will resume automatically around ${scheduledResume.toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}.`
      : `${limitLabel} reached. Reprocessing will resume automatically when ${fallbackLabel}.`
  }
  const progressCopy = chaptersCompleted !== null && chaptersTotal
    ? ` ${chaptersCompleted}/${chaptersTotal} chapters complete.`
    : ""
  return `${resumeCopy}${progressCopy}`
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
