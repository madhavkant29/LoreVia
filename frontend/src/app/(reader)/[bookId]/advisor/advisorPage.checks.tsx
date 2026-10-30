"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { isAxiosError } from "axios"
import { intelligenceApi } from "@/lib/api/intelligence"
import { useAdaptivePolling } from "@/lib/hooks/useAdaptivePolling"
import { normalizeBookRouteId } from "@/lib/utils/bookRoutes"
import type { AdvisorSuggestionsResponse } from "@/types/intelligence"
import { SuggestionGroup } from "./advisorPage.components"
import { advisorAuditStatus, parseAdvisorChoices, type AdvisorNote } from "./advisorPage.helpers"

export function AdvisorChecks({ bookId, userId, isDark, onAsk, onSave, saving }: { bookId: string; userId: string; isDark: boolean; onAsk: (prompt: string) => void; onSave: (note: AdvisorNote) => void; saving: boolean }) {
  const projectId = normalizeBookRouteId(bookId)
  const choiceKey = `lorevia-advisor-scan:${userId}:${projectId}`
  const jobKey = `lorevia-advisor-job:${userId}:${projectId}`
  const [storageError, setStorageError] = useState(false)
  const [choices, setChoices] = useState(() => { try { return parseAdvisorChoices(localStorage.getItem(choiceKey) ?? localStorage.getItem(`lorevia-advisor-scan:${bookId}`) ?? localStorage.getItem(`lorevia-advisor-scan:${projectId}`)) } catch { return { dismissed: [], intentional: [] } } })
  const [payload, setPayload] = useState<AdvisorSuggestionsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [job, setJob] = useState<string | null>(null)
  const [paused, setPaused] = useState(false)
  const [status, setStatus] = useState("")
  const mounted = useRef(true)
  const request = useRef(0)
  const startingRef = useRef(false)
  const loadingRef = useRef(false)
  const jobRef = useRef<string | null>(null)
  jobRef.current = job

  useEffect(() => {
    mounted.current = true
    try { const stored = sessionStorage.getItem(jobKey); if (stored) { setJob(stored); setStatus("Checking the previously started scan…") } } catch { setStorageError(true) }
    return () => { mounted.current = false; loadingRef.current = false }
  }, [jobKey])
  useEffect(() => { try { localStorage.setItem(choiceKey, JSON.stringify(choices)) } catch { setStorageError(true) } }, [choices, choiceKey])

  const load = useCallback(async () => {
    if (loadingRef.current) return false
    const id = ++request.current
    loadingRef.current = true; setLoading(true); setError(null)
    try { const data = await intelligenceApi.advisorSuggestions(bookId); if (mounted.current && request.current === id) { setPayload(data); return true }; return false }
    catch { if (mounted.current && request.current === id) setError("Recommended checks could not be loaded. Any previous findings remain below."); return false }
    finally { if (request.current === id) { loadingRef.current = false; if (mounted.current) setLoading(false) } }
  }, [bookId])
  useEffect(() => { void load() }, [load])

  const finish = useCallback(() => {
    jobRef.current = null; setJob(null)
    try { sessionStorage.removeItem(jobKey) } catch { setStorageError(true) }
  }, [jobKey])
  const poll = useCallback(async ({ signal }: { signal: AbortSignal }) => {
    if (!job) throw new Error("Missing scan job")
    const result = await intelligenceApi.advisorSuggestionsJobStatus(bookId, job, signal)
    if (!mounted.current || signal.aborted) return result
    if (result.status === "complete") {
      request.current++; loadingRef.current = false; setLoading(false)
      if (result.result) { setPayload(result.result); setError(null); setStatus("Checks updated.") }
      else { setError("The scan finished without a report. Reload checks to retrieve the latest available findings."); setStatus("") }
      finish()
    } else if (result.status === "failed") { setError(result.error || "The scan failed. You can start a new scan; previous findings remain below."); setStatus(""); finish() }
    else { setStatus(result.progress?.total ? `Scanning evidence group ${result.progress.completed}/${result.progress.total}…` : "Checking extracted story evidence…"); setError(null) }
    return result
  }, [bookId, job, finish])
  const polling = useAdaptivePolling({ enabled: !!job && !paused, poll, getProgress: (result) => `${result.status}:${result.progress?.completed ?? 0}`, isTerminal: (result) => result.status === "complete" || result.status === "failed", initialDelayMs: 1000, maxDelayMs: 8000, timeoutMs: 25 * 60 * 1000, resetKey: job, onError: (failure) => {
    if (isAxiosError(failure) && failure.response?.status === 404) { finish(); setStatus(""); setError("This scan could no longer be found. Reload checks before starting another scan."); return }
    if (isAxiosError(failure) && failure.response?.status === 403) { setPaused(true); setError("This account cannot check the scan right now. Check your access and plan, then resume checking."); return }
    setError("The scan status could not be checked. The job may still be running; resume checking to use the same job.")
  } })

  async function start() {
    if (startingRef.current || jobRef.current || loadingRef.current) return
    startingRef.current = true; setStarting(true); setError(null); setStatus("Starting a continuity scan…")
    try {
      const result = await intelligenceApi.advisorSuggestionsScan(bookId)
      if (!mounted.current) return
      if (result.cached) { setStatus("Loading the latest cached checks…"); const loaded = await load(); if (mounted.current) setStatus(loaded ? "Latest available checks loaded." : "") }
      else if (result.job_id) { jobRef.current = result.job_id; setJob(result.job_id); setPaused(false); try { sessionStorage.setItem(jobKey, result.job_id) } catch { setStorageError(true) } }
      else { setError("The scan start could not be confirmed. Reload checks before trying again."); setStatus("") }
    } catch { if (mounted.current) { setError("The scan start could not be confirmed. Reload checks before trying again."); setStatus("") } }
    finally { startingRef.current = false; if (mounted.current) setStarting(false) }
  }
  const hidden = new Set([...choices.dismissed, ...choices.intentional])
  const suggestions = payload?.suggestions ?? []
  const visible = suggestions.filter((item) => !hidden.has(item.id))
  const hiddenItems = suggestions.filter((item) => hidden.has(item.id))
  const knownSeverities = new Set(["warning", "direction", "opportunity", "info"])
  const legacyPriorityCount = visible.filter((item) => !knownSeverities.has(item.severity)).length
  const meta = payload?.meta
  const restore = (id: string) => setChoices((current) => ({ dismissed: current.dismissed.filter((item) => item !== id), intentional: current.intentional.filter((item) => item !== id) }))
  return <div className="space-y-6">
    <div className="flex flex-wrap items-start justify-between gap-4"><p className="advisor-muted max-w-2xl text-sm leading-7">Review structural risks, unresolved decisions, and setup opportunities derived from extracted story evidence. Findings are suggestions to verify, not proof of a plot hole.</p><div className="flex flex-wrap gap-3"><button type="button" className="app-button-secondary" disabled={starting || !!job || loading} onClick={() => void start()}>{starting ? "Starting…" : "Refresh checks"}</button><button type="button" className="app-button-secondary" disabled={loading || starting || !!job} onClick={() => void load()}>Reload checks</button></div></div>
    {storageError ? <p role="status" className="text-sm">Browser storage is unavailable. Hidden checks and scan recovery may not survive leaving this page.</p> : null}
    {status || loading || job ? <div className="border-l-2 border-[rgb(var(--border))] pl-4 text-sm leading-6"><p role="status">{polling.timedOut ? "Status checking paused after 25 minutes. The scan may still be running." : paused ? "Status checking paused. Server processing may continue." : loading ? "Loading recommended checks…" : status}</p>{job ? <div className="mt-2 flex flex-wrap gap-3"><button type="button" className="app-button-secondary" onClick={() => { setPaused(false); setError(null); polling.refresh() }}>Resume checking</button>{!paused && !polling.timedOut ? <button type="button" className="app-button-secondary" onClick={() => setPaused(true)}>Stop checking</button> : null}</div> : null}</div> : null}
    {error ? <div role="alert" className="border-l-2 border-amber-600 pl-4 text-sm leading-7"><p>{error}</p>{!job ? <button type="button" disabled={loading || starting} className="min-h-11 underline" onClick={() => void load()}>Retry loading checks</button> : null}</div> : null}
    {meta ? <section aria-label="Evidence used" className="border-y border-[rgb(var(--border))] py-4"><dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">{[["Characters", meta.character_count], ["States", meta.state_count], ["Open threads", meta.open_thread_count], ["Clues", meta.clue_count], ["Relationships", meta.relationship_count], ["World elements", meta.world_element_count]].map(([label, value]) => <div key={label} className="flex items-baseline justify-between gap-3 text-sm"><dt className="advisor-muted">{label}</dt><dd className="font-semibold tabular-nums">{value}</dd></div>)}</dl><div className="advisor-muted mt-4 space-y-2 border-t border-[rgb(var(--border))] pt-4 text-sm leading-6"><p>{meta.heuristic_count} heuristic finding{meta.heuristic_count === 1 ? "" : "s"}{meta.proactive_audit_applied ? " · Proactive audit included" : ""}{meta.fallback_applied ? " · Fallback analysis" : ""}</p><p>Evidence sources: {meta.scan_basis.length ? meta.scan_basis.join(", ") : "none yet"}.</p>{meta.data_gaps.length ? <p>Missing context: {meta.data_gaps.join(", ")}.</p> : null}{meta.audit_failure_category ? <p role="status">AI audit status: {advisorAuditStatus(meta.audit_failure_category)}</p> : null}{meta.audit_summary ? <p className="text-[rgb(var(--foreground))]">{meta.audit_summary}</p> : null}</div></section> : null}
    {meta?.audit_groups_total ? <p className="advisor-muted text-sm">AI evidence groups reviewed: {meta.audit_groups_completed ?? 0}/{meta.audit_groups_total}.{meta.audit_failure_category ? " The remaining groups can be retried with Refresh checks." : ""}</p> : null}
    {payload && !suggestions.length ? <p className="py-5 text-sm">{meta?.audit_failure_category ? "The AI audit did not finish, and no heuristic checks were supported. This is not a clean scan; refresh checks later." : meta?.proactive_audit_applied ? "No supported checks were found in the reviewed evidence. This does not prove the manuscript is free of continuity problems." : "No supported checks are available from the extracted evidence yet. Refresh checks after processing more story data."}</p> : payload && !visible.length ? <p className="py-5 text-sm">All current checks are hidden. Restore them below to review them again.</p> : null}
    {legacyPriorityCount ? <p role="status" className="advisor-muted text-sm">{legacyPriorityCount} check{legacyPriorityCount === 1 ? " has" : "s have"} an unrecognized priority from an earlier scan and {legacyPriorityCount === 1 ? "is" : "are"} shown under Info.</p> : null}
    {[{ label: "Warnings", severity: "warning" }, { label: "Future Direction", severity: "direction" }, { label: "Opportunities", severity: "opportunity" }, { label: "Info", severity: "info" }].map((group) => <SuggestionGroup key={group.severity} label={group.label} items={visible.filter((item) => item.severity === group.severity || (group.severity === "info" && !knownSeverities.has(item.severity)))} isDark={isDark} onAsk={onAsk} onSaveNote={onSave} saving={saving} onMarkIntentional={(id) => setChoices((current) => ({ ...current, intentional: [...new Set([...current.intentional, id])] }))} onDismiss={(id) => setChoices((current) => ({ ...current, dismissed: [...new Set([...current.dismissed, id])] }))} />)}
    {hidden.size ? <details><summary className="cursor-pointer py-3 text-sm font-semibold">Hidden checks ({hiddenItems.length} in this report) · Intentional choices ({choices.intentional.length})</summary><p className="advisor-muted text-sm leading-6">These choices apply on this browser and account. New findings with different identifiers may still appear.</p>{hiddenItems.map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 border-b border-[rgb(var(--border))] py-3"><p className="text-sm">{item.title} · {choices.intentional.includes(item.id) ? "Intentional" : "Dismissed"}</p><button type="button" className="app-button-secondary" onClick={() => restore(item.id)}>Restore {item.title}</button></div>)}<button type="button" className="app-button-secondary mt-3" onClick={() => setChoices({ dismissed: [], intentional: [] })}>Restore all hidden checks</button></details> : null}
  </div>
}
