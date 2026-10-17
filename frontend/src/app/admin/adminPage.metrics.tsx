"use client"

import { useState } from "react"

import type { AdminQueueDepth, AdminSubscriptionMetrics } from "@/types/admin"

export function AdminMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-t border-[#d9dfd6] py-3">
      <p className="text-xs font-medium text-[#657166]">{label}</p>
      <p className="mt-1 text-xl font-semibold text-[#1c261f]">{value}</p>
    </div>
  )
}

export function QueueDepthPanel({ queueDepth }: { queueDepth: AdminQueueDepth | null }) {
  if (!queueDepth) return null
  const queues: { label: string; value: number }[] = [
    { label: "Extraction", value: queueDepth.extraction },
    { label: "Analysis", value: queueDepth.analysis },
    { label: "Embedding", value: queueDepth.embedding },
    { label: "Intelligence", value: queueDepth.intelligence },
  ]
  const max = Math.max(...queues.map((queue) => queue.value), 1)

  return (
    <section className="rounded-lg border border-[#d9dfd6] bg-white p-5">
      <h2 className="text-xl font-semibold">Worker Queues</h2>
      <div className="mt-4 space-y-3">
        {queues.map((queue) => (
          <div key={queue.label}>
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium text-[#46534a]">{queue.label}</span>
              <span className="text-[#617065]">{queue.value.toLocaleString()}</span>
            </div>
            <div className="mt-1 h-3 rounded-full bg-[#edf0eb]">
              <div
                className="h-3 rounded-full bg-[#1f615d] transition-all"
                style={{ width: `${Math.min((queue.value / max) * 100, 100).toFixed(0)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

export function SubscriptionMetricsPanel({
  metrics,
  disabled,
  onRefresh,
}: {
  metrics: AdminSubscriptionMetrics | null
  disabled: boolean
  onRefresh: (startDate: string, endDate: string, reactivationWindow: number) => void
}) {
  const today = new Date().toISOString().slice(0, 10)
  const thirtyDaysAgo = new Date(Date.now() - 29 * 86400000).toISOString().slice(0, 10)
  const [startDate, setStartDate] = useState(thirtyDaysAgo)
  const [endDate, setEndDate] = useState(today)
  const [reactivationWindow, setReactivationWindow] = useState(30)

  function formatRate(value: number | null | undefined): string {
    if (value == null) return "—"
    return `${(value * 100).toFixed(1)}%`
  }

  return (
    <section className="rounded-lg border border-[#d9dfd6] bg-white p-5">
      <h2 className="text-xl font-semibold">Subscription Metrics</h2>
      <div className="mt-4 flex flex-wrap gap-3">
        <label className="grid gap-1 text-sm font-medium text-[#46534a]">
          Start
          <input
            type="date"
            className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]"
            value={startDate}
            onChange={(event) => setStartDate(event.target.value)}
          />
        </label>
        <label className="grid gap-1 text-sm font-medium text-[#46534a]">
          End
          <input
            type="date"
            className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]"
            value={endDate}
            onChange={(event) => setEndDate(event.target.value)}
          />
        </label>
        <label className="grid gap-1 text-sm font-medium text-[#46534a]">
          Reactivation window (days)
          <input
            type="number"
            className="w-24 rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]"
            value={reactivationWindow}
            min={1}
            max={365}
            onChange={(event) => setReactivationWindow(Number(event.target.value))}
          />
        </label>
        <button
          disabled={disabled || !startDate || !endDate}
          className="self-end rounded-md border border-[#1f615d] bg-[#1f615d] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          onClick={() => onRefresh(startDate, endDate, reactivationWindow)}
        >
          Refresh
        </button>
      </div>
      {metrics ? (
        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <AdminMetric label="Cohort" value={`${metrics.cohort_start} → ${metrics.cohort_end}`} />
          <AdminMetric label="Trial Starts" value={metrics.trial_starts.toLocaleString()} />
          <AdminMetric label="Trial → Paid" value={`${metrics.trial_to_paid_conversions.toLocaleString()} (${formatRate(metrics.trial_to_paid_rate)})`} />
          <AdminMetric label="Cancellations" value={metrics.cancellation_events.toLocaleString()} />
          <AdminMetric label="Resolved" value={metrics.resolved_cancellation_events.toLocaleString()} />
          <AdminMetric label="Unresolved" value={metrics.unresolved_cancellation_events.toLocaleString()} />
          <AdminMetric label="Reactivated" value={metrics.reactivated_after_cancellation.toLocaleString()} />
          <AdminMetric label="Churned" value={metrics.churned_after_cancellation.toLocaleString()} />
          <AdminMetric label="Churn Rate" value={formatRate(metrics.post_cancel_churn_rate)} />
        </div>
      ) : (
        <p className="mt-4 text-sm text-[#617065]">Select a date range and refresh to load metrics.</p>
      )}
    </section>
  )
}
