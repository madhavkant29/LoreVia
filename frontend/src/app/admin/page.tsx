"use client"

import { useEffect, useState, useTransition } from "react"
import type { ReactNode } from "react"
import { adminApi } from "@/lib/api/admin"
import type {
  AdminAuditEvent,
  AdminBillingStatus,
  AdminContentReport,
  AdminMetrics,
  AdminPrincipal,
  AdminPublicShare,
  AdminQueueDepth,
  AdminRateLimitState,
  AdminRefundReview,
  AdminScope,
  AdminSession,
  AdminSubscriptionMetrics,
  AdminTaskExecution,
  AdminOperationsMetrics,
  AdminAiQualityMetrics,
  AdminContributionMargin,
  AdminSupportIncident,
} from "@/types/admin"
import { AdminMetric, QueueDepthPanel, SubscriptionMetricsPanel } from "./adminPage.metrics"

const SCOPE_OPTIONS: AdminScope[] = ["moderation_admin", "billing_admin", "super_admin"]
type AdminArea = "overview" | "moderation" | "billing" | "reliability" | "access"

function hasScope(session: AdminSession | null, scope: AdminScope) {
  return Boolean(session?.is_owner || session?.scopes.includes(scope))
}

function defaultAdminArea(session: AdminSession): AdminArea {
  if (hasScope(session, "super_admin")) return "overview"
  if (hasScope(session, "moderation_admin")) return "moderation"
  if (hasScope(session, "billing_admin")) return "billing"
  return session.is_owner ? "access" : "overview"
}

function formatDate(value?: string | null) {
  if (!value) return "Unknown"
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value))
}

function StatusBadge({
  children,
  tone = "neutral",
}: {
  children: ReactNode
  tone?: "neutral" | "success" | "warning" | "danger"
}) {
  const toneClass = {
    neutral: "border-[#d9dfd6] bg-[#f6f7f4] text-[#526056]",
    success: "border-[#b8d7c0] bg-[#eff8f0] text-[#1f6b3a]",
    warning: "border-[#ecd7b0] bg-[#fff8e8] text-[#8a5a12]",
    danger: "border-[#e8c4c0] bg-[#fff3f1] text-[#a2382b]",
  }[tone]

  return <span className={`inline-flex rounded-md border px-2 py-1 text-xs font-semibold ${toneClass}`}>{children}</span>
}

export default function AdminPage() {
  const [session, setSession] = useState<AdminSession | null>(null)
  const [billingStatus, setBillingStatus] = useState<AdminBillingStatus | null>(null)
  const [publicShares, setPublicShares] = useState<AdminPublicShare[]>([])
  const [reports, setReports] = useState<AdminContentReport[]>([])
  const [refunds, setRefunds] = useState<AdminRefundReview[]>([])
  const [principals, setPrincipals] = useState<AdminPrincipal[]>([])
  const [audit, setAudit] = useState<AdminAuditEvent[]>([])
  const [metrics, setMetrics] = useState<AdminMetrics | null>(null)
  const [queueDepth, setQueueDepth] = useState<AdminQueueDepth | null>(null)
  const [subscriptionMetrics, setSubscriptionMetrics] = useState<AdminSubscriptionMetrics | null>(null)
  const [taskExecutions, setTaskExecutions] = useState<AdminTaskExecution[]>([])
  const [operations, setOperations] = useState<AdminOperationsMetrics | null>(null)
  const [quality, setQuality] = useState<AdminAiQualityMetrics | null>(null)
  const [margin, setMargin] = useState<AdminContributionMargin | null>(null)
  const [incidents, setIncidents] = useState<AdminSupportIncident[]>([])
  const [message, setMessage] = useState<string | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [activeArea, setActiveArea] = useState<AdminArea>("overview")
  const [isPending, startTransition] = useTransition()

  async function loadAdminArea(currentSession: AdminSession, area: AdminArea) {
    const tasks: Promise<unknown>[] = []
    if (area === "moderation" && hasScope(currentSession, "moderation_admin")) {
      tasks.push(adminApi.publicShares().then(setPublicShares))
      tasks.push(adminApi.reports().then(setReports))
    }
    if (area === "billing" && hasScope(currentSession, "billing_admin")) {
      tasks.push(adminApi.billingStatus().then(setBillingStatus))
      tasks.push(adminApi.refunds().then(setRefunds))
      tasks.push(adminApi.subscriptionMetrics().then(setSubscriptionMetrics))
    }
    if (area === "overview" && hasScope(currentSession, "super_admin")) {
      tasks.push(adminApi.metrics().then(setMetrics))
      tasks.push(adminApi.queueDepth().then(setQueueDepth))
    }
    if (area === "reliability" && hasScope(currentSession, "super_admin")) {
      tasks.push(adminApi.taskExecutions().then(setTaskExecutions))
      tasks.push(adminApi.operationsMetrics().then(setOperations))
      tasks.push(adminApi.aiQuality().then(setQuality))
      tasks.push(adminApi.contributionMargin().then(setMargin))
      tasks.push(adminApi.supportIncidents().then(setIncidents))
    }
    if (area === "access" && currentSession.is_owner) {
      tasks.push(adminApi.access().then(setPrincipals))
      tasks.push(adminApi.audit().then(setAudit))
    }
    await Promise.all(tasks)
  }

  useEffect(() => {
    let cancelled = false
    adminApi
      .session()
      .then(async (nextSession) => {
        if (cancelled) return
        setSession(nextSession)
        setActiveArea(defaultAdminArea(nextSession))
      })
      .catch(() => {
        if (!cancelled) setNotFound(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!session) return
    void loadAdminArea(session, activeArea).catch(() => {
      setMessage("This admin area could not be refreshed.")
    })
  }, [activeArea, session])

  function runAction(action: () => Promise<unknown>, success: string) {
    startTransition(() => {
      action()
        .then(async () => {
          setMessage(success)
          if (session) await loadAdminArea(session, activeArea)
        })
        .catch((error) => {
          setMessage(error?.response?.data?.detail ?? "Admin action failed.")
        })
    })
  }

  if (notFound) {
    return (
      <main className="min-h-screen bg-[#f6f7f4] px-6 py-20 text-[#1c261f]">
        <div className="mx-auto max-w-3xl">
          <h1 className="text-3xl font-semibold">404</h1>
          <p className="mt-2 text-sm text-[#5f6c63]">Not found.</p>
        </div>
      </main>
    )
  }

  if (!session) {
    return <main className="min-h-screen bg-[#f6f7f4] px-6 py-20 text-[#1c261f]" />
  }

  return (
    <main className="min-h-screen bg-[#f6f7f4] text-[#1c261f]">
      <div className="mx-auto flex min-w-0 max-w-7xl flex-col gap-8 overflow-x-hidden px-5 py-8">
        <header className="flex flex-col gap-3 border-b border-[#d9dfd6] pb-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm font-semibold text-[#526056]">LoreVia administration</p>
            <h1 className="mt-2 text-3xl font-semibold">Operations Console</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[#617065]">Moderation, billing, access, and audit review for protected operational workflows.</p>
          </div>
          <div className="text-sm text-[#526056]">
            {session.is_owner ? "Owner" : session.scopes.join(", ")}
            {session.requires_step_up ? " / verification required" : " / recently verified"}
          </div>
        </header>

        <nav aria-label="Admin areas" className="flex min-w-0 max-w-full gap-1 overflow-x-auto border-b border-[#d9dfd6]">
          {([
            { id: "overview" as const, label: "Overview", visible: hasScope(session, "super_admin") },
            { id: "moderation" as const, label: "Moderation", visible: hasScope(session, "moderation_admin") },
            { id: "billing" as const, label: "Billing", visible: hasScope(session, "billing_admin") },
            { id: "reliability" as const, label: "Reliability", visible: hasScope(session, "super_admin") },
            { id: "access" as const, label: "Access & audit", visible: session.is_owner },
          ]).filter((area) => area.visible).map((area) => (
            <button
              key={area.id}
              type="button"
              aria-current={activeArea === area.id ? "page" : undefined}
              onClick={() => setActiveArea(area.id)}
              className={`whitespace-nowrap border-b-2 px-4 py-3 text-sm font-semibold ${activeArea === area.id ? "border-[#1f615d] text-[#1f615d]" : "border-transparent text-[#617065] hover:text-[#1c261f]"}`}
            >
              {area.label}
            </button>
          ))}
        </nav>

        {activeArea === "overview" && hasScope(session, "super_admin") ? (
          <section className="grid min-w-0 gap-6 lg:grid-cols-2">
            <PlatformMetricsPanel metrics={metrics} />
            <QueueDepthPanel queueDepth={queueDepth} />
          </section>
        ) : null}

        {activeArea === "reliability" && hasScope(session, "super_admin") ? (
          <RateLimitPanel
            disabled={isPending || session.requires_step_up}
            onLookup={(userId) => adminApi.getRateLimit(userId)}
            onSave={(userId, override) =>
              runAction(() => adminApi.setRateLimit(userId, override), "Rate limit overrides updated.")
            }
          />
        ) : null}

        {activeArea === "reliability" && hasScope(session, "super_admin") ? (
          <ReliabilityPanel
            operations={operations}
            quality={quality}
            margin={margin}
            executions={taskExecutions}
            incidents={incidents}
            disabled={isPending || session.requires_step_up}
            onRetry={(id, reason) => runAction(() => adminApi.retryTaskExecution(id, reason), "Task queued for retry.")}
            onDismiss={(id, reason) => runAction(() => adminApi.dismissTaskExecution(id, reason), "Task failure dismissed.")}
            onIncident={(body) => runAction(() => adminApi.createSupportIncident(body), "Support incident recorded.")}
            onResolve={(id, resolution) => runAction(() => adminApi.resolveSupportIncident(id, resolution), "Support incident resolved.")}
          />
        ) : null}

        {message ? <div className="rounded-lg border border-[#b8c7b8] bg-white px-4 py-3 text-sm">{message}</div> : null}

        {session.requires_step_up ? (
          <StepUpPanel onSubmit={(password) => runAction(() => adminApi.stepUp(password).then(() => adminApi.session().then(setSession)), "Admin verification complete.")} />
        ) : null}

        <section className="grid min-w-0 gap-6">
          {activeArea === "moderation" && hasScope(session, "moderation_admin") ? (
            <ModerationPanel
              publicShares={publicShares}
              reports={reports}
              disabled={isPending || session.requires_step_up}
              onReview={(bookId, approved, reason) =>
                runAction(() => adminApi.reviewPublicShare(bookId, { approved, reason }), "Public share reviewed.")
              }
              onBookAction={(bookId, action, reason) =>
                runAction(() => adminApi[action](bookId, reason), `Book ${action.replace("Book", "").toLowerCase()} action recorded.`)
              }
            />
          ) : null}

          {activeArea === "billing" && hasScope(session, "billing_admin") ? (
            <RefundPanel
              billingStatus={billingStatus}
              refunds={refunds}
              disabled={isPending || session.requires_step_up}
              onApprove={(reviewId, reason, providerFollowupOnly) =>
                runAction(
                  () => adminApi.approveRefund(reviewId, { reason, provider_followup_only: providerFollowupOnly }),
                  "Refund review approved.",
                )
              }
              onDeny={(reviewId, reason) => runAction(() => adminApi.denyRefund(reviewId, reason), "Refund review denied.")}
            />
          ) : null}
        </section>

        {activeArea === "moderation" && hasScope(session, "moderation_admin") && !session.requires_step_up ? (
          <div className="grid min-w-0 gap-3">
            <details className="border border-[#d9dfd6] bg-white">
              <summary className="cursor-pointer px-5 py-4 text-sm font-semibold">Creator enforcement action</summary>
              <div className="border-t border-[#d9dfd6]">
                <CreatorStrikePanel
                  disabled={isPending}
                  onSubmit={(userId, body) => runAction(() => adminApi.addStrike(userId, body), "Creator strike applied.")}
                />
              </div>
            </details>
            <details className="border border-[#d9dfd6] bg-white">
              <summary className="cursor-pointer px-5 py-4 text-sm font-semibold">Public demo book editor</summary>
              <div className="border-t border-[#d9dfd6]">
                <PublicDemoBookPanel
                  disabled={isPending}
                  onCreate={(body) => runAction(() => adminApi.createPublicDemoBook(body), "Public demo book created.")}
                  onAppend={(bookId, body) => runAction(() => adminApi.appendPublicDemoChapter(bookId, body), "Chapter appended to demo book.")}
                />
              </div>
            </details>
          </div>
        ) : null}

        {activeArea === "billing" && hasScope(session, "billing_admin") ? (
          <SubscriptionMetricsPanel
            metrics={subscriptionMetrics}
            disabled={isPending}
            onRefresh={(startDate, endDate, reactivationWindow) =>
              runAction(
                () => adminApi.subscriptionMetrics({ start_date: startDate, end_date: endDate, reactivation_window_days: reactivationWindow }).then(setSubscriptionMetrics),
                "Subscription metrics refreshed.",
              )
            }
          />
        ) : null}

        {activeArea === "access" && session.is_owner ? (
          <section className="grid min-w-0 gap-6 lg:grid-cols-2">
            <AccessPanel
              principals={principals}
              disabled={isPending || session.requires_step_up}
              onGrant={(payload) => runAction(() => adminApi.grantAccess(payload), "Admin access updated.")}
              onRevoke={(principalId, reason) => runAction(() => adminApi.revokeAccess(principalId, reason), "Admin access revoked.")}
            />
            <AuditPanel events={audit} />
          </section>
        ) : null}
      </div>
    </main>
  )
}

function StepUpPanel({ onSubmit }: { onSubmit: (password: string) => void }) {
  const [password, setPassword] = useState("")
  return (
    <form
      className="flex flex-col gap-3 rounded-lg border border-[#d9dfd6] bg-white p-4 md:flex-row md:items-end"
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit(password)
        setPassword("")
      }}
    >
      <label className="flex flex-1 flex-col gap-2 text-sm font-medium">
        Verify password
        <input className="rounded-md border border-[#c9d2c8] px-3 py-2" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
      </label>
      <button className="rounded-md border border-[#1f615d] bg-[#1f615d] px-4 py-2 text-sm font-semibold text-white" type="submit">
        Verify
      </button>
    </form>
  )
}

function ModerationPanel({
  publicShares,
  reports,
  disabled,
  onReview,
  onBookAction,
}: {
  publicShares: AdminPublicShare[]
  reports: AdminContentReport[]
  disabled: boolean
  onReview: (bookId: string, approved: boolean, reason?: string | null) => void
  onBookAction: (bookId: string, action: "hideBook" | "removeBook" | "restoreBook", reason: string) => void
}) {
  const [bookId, setBookId] = useState("")
  const [reason, setReason] = useState("")
  const [selectedShare, setSelectedShare] = useState<AdminPublicShare | null>(null)
  const [selectedReport, setSelectedReport] = useState<AdminContentReport | null>(null)
  const [showBookAction, setShowBookAction] = useState(false)
  return (
    <section className="min-w-0 overflow-hidden border border-[#d9dfd6] bg-white">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#d9dfd6] px-5 py-4">
        <div>
          <h2 className="text-xl font-semibold">Moderation</h2>
          <p className="mt-1 text-sm text-[#617065]">Select a queued item to review its evidence and actions.</p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge tone={publicShares.length || reports.length ? "warning" : "success"}>{publicShares.length + reports.length} queued</StatusBadge>
          <button type="button" className="border border-[#c9d2c8] px-3 py-2 text-sm font-semibold" onClick={() => setShowBookAction((value) => !value)}>
            {showBookAction ? "Close manual action" : "Manual book action"}
          </button>
        </div>
      </div>

      {showBookAction ? (
        <div className="grid gap-3 border-b border-[#d9dfd6] bg-[#fbfcfa] p-5 md:grid-cols-[1fr_2fr_auto] md:items-end">
          <label className="grid gap-1.5 text-sm font-medium text-[#46534a]">Book ID
            <input className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]" value={bookId} onChange={(event) => setBookId(event.target.value)} />
          </label>
          <label className="grid gap-1.5 text-sm font-medium text-[#46534a]">Required reason
            <input className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]" value={reason} onChange={(event) => setReason(event.target.value)} />
          </label>
          <div className="flex flex-wrap gap-2">
            {(["hideBook", "removeBook", "restoreBook"] as const).map((action) => (
              <button key={action} disabled={disabled || !bookId || !reason} className="border border-[#d9dfd6] px-3 py-2 text-sm disabled:opacity-50" onClick={() => onBookAction(bookId, action, reason)}>{action.replace("Book", "")}</button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="grid min-h-[20rem] lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-w-0">
          <h3 className="border-b border-[#edf0eb] px-5 py-3 text-sm font-semibold">Public share requests</h3>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[42rem] text-left text-sm">
              <thead className="bg-[#f8faf7] text-xs text-[#617065]"><tr><th className="px-5 py-2 font-semibold">Title</th><th className="px-3 py-2 font-semibold">Author</th><th className="px-3 py-2 font-semibold">Requested</th><th className="px-3 py-2 font-semibold">Risk</th><th className="px-5 py-2 text-right font-semibold">Action</th></tr></thead>
              <tbody className="divide-y divide-[#edf0eb]">
                {publicShares.slice(0, 20).map((share) => (
                  <tr key={share.book_id} className={selectedShare?.book_id === share.book_id ? "bg-[#f2f7f5]" : undefined}>
                    <td className="px-5 py-3 font-medium">{share.title}<span className="block text-xs font-normal text-[#7b877e]">{share.book_id}</span></td>
                    <td className="px-3 py-3 text-[#526056]">{share.author_username ?? share.user_id}</td>
                    <td className="px-3 py-3 text-[#526056]">{formatDate(share.requested_at)}</td>
                    <td className="px-3 py-3">{share.copyright_warning ? "Copyright warning" : "Standard review"}</td>
                    <td className="px-5 py-3 text-right"><button type="button" className="font-semibold text-[#1f615d] underline underline-offset-4" onClick={() => { setSelectedShare(share); setSelectedReport(null) }}>Review</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {publicShares.length === 0 ? <p className="px-5 py-5 text-sm text-[#617065]">No pending public shares.</p> : null}

          <h3 className="border-y border-[#edf0eb] px-5 py-3 text-sm font-semibold">Content reports</h3>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[42rem] text-left text-sm">
              <thead className="bg-[#f8faf7] text-xs text-[#617065]"><tr><th className="px-5 py-2 font-semibold">Report</th><th className="px-3 py-2 font-semibold">Book</th><th className="px-3 py-2 font-semibold">Reporter</th><th className="px-3 py-2 font-semibold">Status</th><th className="px-5 py-2 text-right font-semibold">Action</th></tr></thead>
              <tbody className="divide-y divide-[#edf0eb]">
                {reports.slice(0, 20).map((report) => (
                  <tr key={report.id} className={selectedReport?.id === report.id ? "bg-[#f2f7f5]" : undefined}>
                    <td className="px-5 py-3 font-medium">{report.report_type}: {report.reason}</td>
                    <td className="px-3 py-3 text-[#526056]">{report.reported_book_id}</td>
                    <td className="px-3 py-3 text-[#526056]">{report.reporter_email ?? report.reporter_user_id ?? "anonymous"}</td>
                    <td className="px-3 py-3">{report.status}</td>
                    <td className="px-5 py-3 text-right"><button type="button" className="font-semibold text-[#1f615d] underline underline-offset-4" onClick={() => { setSelectedReport(report); setSelectedShare(null) }}>View details</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {reports.length === 0 ? <p className="px-5 py-5 text-sm text-[#617065]">No open content reports.</p> : null}
        </div>

        <aside aria-label="Moderation review details" className="border-t border-[#d9dfd6] bg-[#fbfcfa] p-5 lg:border-l lg:border-t-0">
          {selectedShare ? (
            <div>
              <p className="text-xs font-semibold text-[#617065]">Public share review</p>
              <h3 className="mt-2 text-lg font-semibold">{selectedShare.title}</h3>
              <p className="mt-3 text-sm leading-6 text-[#617065]">{selectedShare.public_description || "No public description supplied."}</p>
              <dl className="mt-4 space-y-2 text-sm"><div><dt className="text-[#7b877e]">Author</dt><dd>{selectedShare.author_username ?? selectedShare.user_id}</dd></div><div><dt className="text-[#7b877e]">Book ID</dt><dd className="break-all">{selectedShare.book_id}</dd></div></dl>
              <div className="mt-5 flex gap-2"><button disabled={disabled} className="border border-[#bdd5c1] px-3 py-2 text-sm font-semibold text-[#1f6b3a]" onClick={() => onReview(selectedShare.book_id, true)}>Approve</button><button disabled={disabled} className="border border-[#e8c4c0] px-3 py-2 text-sm font-semibold text-[#a2382b]" onClick={() => onReview(selectedShare.book_id, false, "Rejected after moderation review.")}>Reject</button></div>
            </div>
          ) : selectedReport ? (
            <div>
              <p className="text-xs font-semibold text-[#617065]">Content report</p>
              <h3 className="mt-2 text-lg font-semibold">{selectedReport.reason}</h3>
              <p className="mt-3 text-sm leading-6 text-[#617065]">{selectedReport.details ?? "No further details supplied."}</p>
              <p className="mt-4 text-xs text-[#7b877e]">Filed {formatDate(selectedReport.created_at)}</p>
            </div>
          ) : (
            <div><h3 className="font-semibold">Review details</h3><p className="mt-2 text-sm leading-6 text-[#617065]">Select a share request or report from the table.</p></div>
          )}
        </aside>
      </div>
    </section>
  )
}

function RefundPanel({
  billingStatus,
  refunds,
  disabled,
  onApprove,
  onDeny,
}: {
  billingStatus: AdminBillingStatus | null
  refunds: AdminRefundReview[]
  disabled: boolean
  onApprove: (reviewId: string, reason: string, providerFollowupOnly: boolean) => void
  onDeny: (reviewId: string, reason: string) => void
}) {
  const [selectedReview, setSelectedReview] = useState<AdminRefundReview | null>(null)
  return (
    <section className="min-w-0 overflow-hidden border border-[#d9dfd6] bg-white">
      <div className="border-b border-[#d9dfd6] px-5 py-4">
        <h2 className="text-xl font-semibold">Refunds</h2>
        <p className="mt-1 text-sm text-[#617065]">Review transaction history before recording a decision.</p>
      </div>
      {billingStatus ? <BillingStatusPanel status={billingStatus} /> : null}
      <div className="grid min-h-[18rem] lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-w-0 overflow-x-auto">
          <table className="w-full min-w-[44rem] text-left text-sm">
            <thead className="bg-[#f8faf7] text-xs text-[#617065]"><tr><th className="px-5 py-2 font-semibold">Transaction</th><th className="px-3 py-2 font-semibold">Plan</th><th className="px-3 py-2 font-semibold">Charged</th><th className="px-3 py-2 font-semibold">Status</th><th className="px-5 py-2 text-right font-semibold">Action</th></tr></thead>
            <tbody className="divide-y divide-[#edf0eb]">
              {refunds.slice(0, 30).map((review) => (
                <tr key={review.id} className={selectedReview?.id === review.id ? "bg-[#f2f7f5]" : undefined}>
                  <td className="px-5 py-3 font-medium">{review.paddle_transaction_id}<span className="block text-xs font-normal text-[#7b877e]">{review.id}</span></td>
                  <td className="px-3 py-3 text-[#526056]">{review.plan_code} / {review.billing_interval}</td>
                  <td className="px-3 py-3 text-[#526056]">{formatDate(review.charge_at)}</td>
                  <td className="px-3 py-3">{review.status}</td>
                  <td className="px-5 py-3 text-right"><button type="button" className="font-semibold text-[#1f615d] underline underline-offset-4" onClick={() => setSelectedReview(review)}>Review</button></td>
                </tr>
              ))}
            </tbody>
          </table>
          {refunds.length === 0 ? <p className="px-5 py-5 text-sm text-[#617065]">No refund reviews.</p> : null}
        </div>
        <aside aria-label="Refund review details" className="border-t border-[#d9dfd6] bg-[#fbfcfa] p-5 lg:border-l lg:border-t-0">
          {selectedReview ? (
            <RefundRow review={selectedReview} disabled={disabled} onApprove={onApprove} onDeny={onDeny} />
          ) : (
            <div><h3 className="font-semibold">Decision details</h3><p className="mt-2 text-sm leading-6 text-[#617065]">Select a refund request from the table.</p></div>
          )}
        </aside>
      </div>
    </section>
  )
}

function BillingStatusPanel({ status }: { status: AdminBillingStatus }) {
  return (
    <details className="border-b border-[#d9dfd6] bg-[#fbfcfa] text-sm">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-3 font-semibold">
        <span>Billing configuration · {status.fully_configured_plan_count} plans</span>
        <StatusBadge tone={status.payments_ready ? "success" : "warning"}>{status.payments_ready ? "Ready" : "Action required"}</StatusBadge>
      </summary>
      <div className="border-t border-[#edf0eb] px-5 py-4">
        <p className="text-[#617065]">Recommended checkout URL: {status.recommended_default_checkout_url}</p>
        {status.missing_configuration.length > 0 ? <p className="mt-2 text-[#9a3412]">Missing: {status.missing_configuration.join(", ")}</p> : <p className="mt-2 text-[#1f6b3a]">All required billing configuration values are present.</p>}
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[36rem] text-left"><thead className="text-xs text-[#617065]"><tr><th className="py-2 pr-3">Plan</th><th className="px-3 py-2">Code</th><th className="px-3 py-2">Price</th><th className="py-2 pl-3">Configuration</th></tr></thead><tbody className="divide-y divide-[#e3e8e1]">{status.plans.map((plan) => <tr key={plan.code}><td className="py-2 pr-3 font-medium">{plan.display_name} {plan.billing_interval === "annual" ? "Annual" : "Monthly"}</td><td className="px-3 py-2 text-[#617065]">{plan.code}</td><td className="px-3 py-2">${plan.price_usd}/{plan.billing_interval === "annual" ? "year" : "mo"}</td><td className="py-2 pl-3">{plan.configured ? "Configured" : "Missing price ID"}</td></tr>)}</tbody></table>
        </div>
      </div>
    </details>
  )
}

function RefundRow({
  review,
  disabled,
  onApprove,
  onDeny,
}: {
  review: AdminRefundReview
  disabled: boolean
  onApprove: (reviewId: string, reason: string, providerFollowupOnly: boolean) => void
  onDeny: (reviewId: string, reason: string) => void
}) {
  const [reason, setReason] = useState("")
  const [providerFollowupOnly, setProviderFollowupOnly] = useState(false)
  return (
    <div>
      <p className="text-xs font-semibold text-[#617065]">Refund decision</p>
      <p className="font-medium">{review.paddle_transaction_id}</p>
      <p className="text-sm text-[#617065]">{review.status} / {review.billing_interval} / {formatDate(review.charge_at)}</p>
      <label className="mt-2 grid gap-1.5 text-sm font-medium text-[#46534a]">
        Required decision reason
        <textarea className="min-h-16 w-full rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]" value={reason} onChange={(event) => setReason(event.target.value)} />
      </label>
      <label className="mt-2 flex items-center gap-2 text-sm">
        <input type="checkbox" checked={providerFollowupOnly} onChange={(event) => setProviderFollowupOnly(event.target.checked)} />
        Provider follow-up only
      </label>
      <div className="mt-2 flex gap-2">
        <button disabled={disabled || !reason} className="rounded-md border border-[#bdd5c1] bg-[#eff8f0] px-3 py-1 text-sm text-[#1f6b3a]" onClick={() => onApprove(review.id, reason, providerFollowupOnly)}>Approve</button>
        <button disabled={disabled || !reason} className="rounded-md border border-[#e8c4c0] bg-[#fff3f1] px-3 py-1 text-sm text-[#a2382b]" onClick={() => onDeny(review.id, reason)}>Deny</button>
      </div>
    </div>
  )
}

function AccessPanel({
  principals,
  disabled,
  onGrant,
  onRevoke,
}: {
  principals: AdminPrincipal[]
  disabled: boolean
  onGrant: (payload: { user_id: string; scopes: AdminScope[]; is_owner: boolean; reason: string }) => void
  onRevoke: (principalId: string, reason: string) => void
}) {
  const [userId, setUserId] = useState("")
  const [reason, setReason] = useState("")
  const [isOwner, setIsOwner] = useState(false)
  const [scopes, setScopes] = useState<AdminScope[]>(["moderation_admin"])
  const [showGrantForm, setShowGrantForm] = useState(false)
  return (
    <section className="min-w-0 overflow-hidden border border-[#d9dfd6] bg-white">
      <div className="flex items-center justify-between gap-4 border-b border-[#d9dfd6] px-5 py-4">
        <div><h2 className="text-xl font-semibold">Admin Access</h2><p className="mt-1 text-sm text-[#617065]">Active principals and scoped operational permissions.</p></div>
        <button type="button" className="border border-[#1f615d] px-3 py-2 text-sm font-semibold text-[#1f615d]" onClick={() => setShowGrantForm((value) => !value)}>{showGrantForm ? "Close access form" : "Grant access"}</button>
      </div>
      {showGrantForm ? <div className="grid gap-3 border-b border-[#d9dfd6] bg-[#fbfcfa] p-5">
        <label className="grid gap-1.5 text-sm font-medium text-[#46534a]">
          User ID
          <input className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]" value={userId} onChange={(event) => setUserId(event.target.value)} />
        </label>
        <label className="grid gap-1.5 text-sm font-medium text-[#46534a]">
          Required owner reason
          <textarea className="min-h-16 rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]" value={reason} onChange={(event) => setReason(event.target.value)} />
        </label>
        <div className="flex flex-wrap gap-3 text-sm">
          {SCOPE_OPTIONS.map((scope) => (
            <label key={scope} className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={scopes.includes(scope)}
                onChange={(event) => setScopes((current) => event.target.checked ? [...current, scope] : current.filter((item) => item !== scope))}
              />
              {scope}
            </label>
          ))}
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={isOwner} onChange={(event) => setIsOwner(event.target.checked)} />
            owner
          </label>
        </div>
        <button disabled={disabled || !userId || !reason} className="rounded-md border border-[#1f615d] bg-[#1f615d] px-3 py-2 text-sm font-semibold text-white" onClick={() => onGrant({ user_id: userId, scopes, is_owner: isOwner, reason })}>
          Grant or update access
        </button>
      </div> : null}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[40rem] text-left text-sm"><thead className="bg-[#f8faf7] text-xs text-[#617065]"><tr><th className="px-5 py-2 font-semibold">Principal</th><th className="px-3 py-2 font-semibold">Access</th><th className="px-3 py-2 font-semibold">Status</th><th className="px-5 py-2 text-right font-semibold">Action</th></tr></thead><tbody className="divide-y divide-[#edf0eb]">{principals.map((principal) => <tr key={principal.id}><td className="px-5 py-3 font-medium">{principal.user_id}<span className="block text-xs font-normal text-[#7b877e]">{principal.id}</span></td><td className="px-3 py-3 text-[#526056]">{principal.is_owner ? "Owner" : principal.scopes.join(", ")}</td><td className="px-3 py-3">{principal.status}</td><td className="px-5 py-3 text-right">{principal.status === "active" ? <button disabled={disabled} className="font-semibold text-[#a2382b] underline underline-offset-4 disabled:opacity-50" onClick={() => onRevoke(principal.id, "Owner revoked admin access.")}>Revoke</button> : null}</td></tr>)}</tbody></table>
        {principals.length === 0 ? <p className="px-5 py-5 text-sm text-[#617065]">No admin principals.</p> : null}
      </div>
    </section>
  )
}

function AuditPanel({ events }: { events: AdminAuditEvent[] }) {
  return (
    <section className="min-w-0 overflow-hidden border border-[#d9dfd6] bg-white">
      <div className="border-b border-[#d9dfd6] px-5 py-4"><h2 className="text-xl font-semibold">Audit</h2><p className="mt-1 text-sm text-[#617065]">Recent protected operations and recorded reasons.</p></div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[40rem] text-left text-sm"><thead className="bg-[#f8faf7] text-xs text-[#617065]"><tr><th className="px-5 py-2 font-semibold">Action</th><th className="px-3 py-2 font-semibold">Result</th><th className="px-3 py-2 font-semibold">Reason</th><th className="px-5 py-2 font-semibold">Time</th></tr></thead><tbody className="divide-y divide-[#edf0eb]">{events.map((event) => <tr key={event.id}><td className="px-5 py-3 font-medium">{event.action_type}</td><td className="px-3 py-3">{event.result}</td><td className="px-3 py-3 text-[#526056]">{event.reason ?? "No reason"}</td><td className="px-5 py-3 text-[#526056]">{formatDate(event.created_at)}</td></tr>)}</tbody></table>
        {events.length === 0 ? <p className="px-5 py-5 text-sm text-[#617065]">No audit events.</p> : null}
      </div>
    </section>
  )
}

function RateLimitPanel({
  disabled,
  onLookup,
  onSave,
}: {
  disabled: boolean
  onLookup: (userId: string) => Promise<AdminRateLimitState>
  onSave: (userId: string, override: { search_per_hour: number | null; summary_per_hour: number | null; chat_per_day: number | null; api_per_minute: number | null }) => void
}) {
  const [lookupUserId, setLookupUserId] = useState("")
  const [result, setResult] = useState<AdminRateLimitState | null>(null)
  const [searchPerHour, setSearchPerHour] = useState("")
  const [summaryPerHour, setSummaryPerHour] = useState("")
  const [chatPerDay, setChatPerDay] = useState("")
  const [apiPerMinute, setApiPerMinute] = useState("")
  const [loading, setLoading] = useState(false)
  const [lookupError, setLookupError] = useState<string | null>(null)

  function selectResult(state: AdminRateLimitState) {
    setResult(state)
    setSearchPerHour(state.override.search_per_hour?.toString() ?? "")
    setSummaryPerHour(state.override.summary_per_hour?.toString() ?? "")
    setChatPerDay(state.override.chat_per_day?.toString() ?? "")
    setApiPerMinute(state.override.api_per_minute?.toString() ?? "")
    setLookupError(null)
  }

  function parseField(value: string): number | null {
    if (!value.trim()) return null
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }

  async function handleLookup() {
    if (!lookupUserId) return
    setLoading(true)
    setLookupError(null)
    try {
      const state = await onLookup(lookupUserId)
      selectResult(state)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Lookup failed."
      setLookupError(detail)
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="rounded-lg border border-[#d9dfd6] bg-white p-5">
      <h2 className="text-xl font-semibold">Rate Limits</h2>
      <div className="mt-4 flex flex-wrap gap-3">
        <label className="grid gap-1 text-sm font-medium text-[#46534a]">
          User ID
          <input
            className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]"
            value={lookupUserId}
            onChange={(event) => setLookupUserId(event.target.value)}
            placeholder="UUID"
          />
        </label>
        <button
          disabled={disabled || !lookupUserId || loading}
          className="self-end rounded-md border border-[#1f615d] bg-[#1f615d] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          onClick={() => { handleLookup().catch(() => {}) }}
        >
          {loading ? "Loading..." : "Lookup"}
        </button>
      </div>
      {lookupError ? <p className="mt-3 text-sm text-[#a2382b]">{lookupError}</p> : null}
      {result ? (
        <div className="mt-5">
          <p className="text-sm text-[#617065]">Email: <span className="font-medium text-[#1c261f]">{result.email}</span></p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1 text-sm font-medium text-[#46534a]">
              Search / hour
              <input
                type="number"
                className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]"
                value={searchPerHour}
                onChange={(event) => setSearchPerHour(event.target.value)}
                placeholder="Default"
              />
            </label>
            <label className="grid gap-1 text-sm font-medium text-[#46534a]">
              Summary / hour
              <input
                type="number"
                className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]"
                value={summaryPerHour}
                onChange={(event) => setSummaryPerHour(event.target.value)}
                placeholder="Default"
              />
            </label>
            <label className="grid gap-1 text-sm font-medium text-[#46534a]">
              Chat / day
              <input
                type="number"
                className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]"
                value={chatPerDay}
                onChange={(event) => setChatPerDay(event.target.value)}
                placeholder="Default"
              />
            </label>
            <label className="grid gap-1 text-sm font-medium text-[#46534a]">
              API / minute
              <input
                type="number"
                className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]"
                value={apiPerMinute}
                onChange={(event) => setApiPerMinute(event.target.value)}
                placeholder="Default"
              />
            </label>
          </div>
          <button
            disabled={disabled}
            className="mt-4 rounded-md border border-[#1f615d] bg-[#1f615d] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            onClick={() =>
              onSave(result.user_id, {
                search_per_hour: parseField(searchPerHour),
                summary_per_hour: parseField(summaryPerHour),
                chat_per_day: parseField(chatPerDay),
                api_per_minute: parseField(apiPerMinute),
              })
            }
          >
            Save overrides
          </button>
        </div>
      ) : null}
    </section>
  )
}

function CreatorStrikePanel({
  disabled,
  onSubmit,
}: {
  disabled: boolean
  onSubmit: (userId: string, body: {
    book_id?: string | null
    report_id?: string | null
    strike_type: string
    severity: string
    reason: string
  }) => void
}) {
  const [userId, setUserId] = useState("")
  const [strikeType, setStrikeType] = useState("")
  const [severity, setSeverity] = useState("medium")
  const [reason, setReason] = useState("")
  const [bookId, setBookId] = useState("")
  const [reportId, setReportId] = useState("")

  return (
    <section className="rounded-lg border border-[#d9dfd6] bg-white p-5">
      <h2 className="text-xl font-semibold">Creator Strikes</h2>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="grid gap-1 text-sm font-medium text-[#46534a]">
          User ID
          <input
            className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]"
            value={userId}
            onChange={(event) => setUserId(event.target.value)}
            placeholder="UUID"
          />
        </label>
        <label className="grid gap-1 text-sm font-medium text-[#46534a]">
          Severity
          <select
            className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]"
            value={severity}
            onChange={(event) => setSeverity(event.target.value)}
          >
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm font-medium text-[#46534a]">
          Strike type
          <input
            className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]"
            value={strikeType}
            onChange={(event) => setStrikeType(event.target.value)}
            placeholder="e.g. copyright, plagiarism"
          />
        </label>
        <label className="grid gap-1 text-sm font-medium text-[#46534a]">
          Book ID (optional)
          <input
            className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]"
            value={bookId}
            onChange={(event) => setBookId(event.target.value)}
            placeholder="UUID"
          />
        </label>
        <label className="grid gap-1 text-sm font-medium text-[#46534a]">
          Report ID (optional)
          <input
            className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]"
            value={reportId}
            onChange={(event) => setReportId(event.target.value)}
            placeholder="UUID"
          />
        </label>
      </div>
      <label className="mt-3 grid gap-1 text-sm font-medium text-[#46534a]">
        Required reason
        <textarea
          className="min-h-20 rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      </label>
      <button
        disabled={disabled || !userId || !strikeType || !reason}
        className="mt-4 rounded-md border border-[#e8c4c0] bg-[#fff3f1] px-4 py-2 text-sm font-semibold text-[#a2382b] disabled:opacity-50"
        onClick={() =>
          onSubmit(userId, {
            strike_type: strikeType,
            severity,
            reason,
            book_id: bookId || null,
            report_id: reportId || null,
          })
        }
      >
        Apply strike
      </button>
    </section>
  )
}

function PublicDemoBookPanel({
  disabled,
  onCreate,
  onAppend,
}: {
  disabled: boolean
  onCreate: (body: { title: string; author?: string | null; genre?: string | null; description?: string | null; chapters: { title: string; text: string; description?: string | null }[] }) => void
  onAppend: (bookId: string, body: { title: string; text: string; description?: string | null }) => void
}) {
  type ChapterDraft = { title: string; text: string; description: string }
  const [title, setTitle] = useState("")
  const [author, setAuthor] = useState("")
  const [genre, setGenre] = useState("")
  const [description, setDescription] = useState("")
  const [chapters, setChapters] = useState<ChapterDraft[]>([{ title: "", text: "", description: "" }])
  const [appendBookId, setAppendBookId] = useState("")
  const [appendTitle, setAppendTitle] = useState("")
  const [appendText, setAppendText] = useState("")
  const [appendDescription, setAppendDescription] = useState("")

  function updateChapter(index: number, field: keyof ChapterDraft, value: string) {
    setChapters((current) => {
      const next = [...current]
      next[index] = { ...next[index], [field]: value }
      return next
    })
  }

  function removeChapter(index: number) {
    if (chapters.length <= 1) return
    setChapters((current) => current.filter((_, i) => i !== index))
  }

  function addChapter() {
    setChapters((current) => [...current, { title: "", text: "", description: "" }])
  }

  function canCreate() {
    return title.trim() && chapters.length > 0 && chapters.some((c) => c.title.trim() && c.text.trim())
  }

  function handleCreate() {
    onCreate({
      title: title.trim(),
      author: author.trim() || null,
      genre: genre.trim() || null,
      description: description.trim() || null,
      chapters: chapters.map((c) => ({
        title: c.title.trim(),
        text: c.text,
        description: c.description.trim() || null,
      })),
    })
  }

  function canAppend() {
    return appendBookId.trim() && appendTitle.trim() && appendText.trim()
  }

  function handleAppend() {
    onAppend(appendBookId.trim(), {
      title: appendTitle.trim(),
      text: appendText,
      description: appendDescription.trim() || null,
    })
  }

  return (
    <section className="rounded-lg border border-[#d9dfd6] bg-white p-5">
      <h2 className="text-xl font-semibold">Public Demo Books</h2>

      <div className="mt-5 border-t border-[#edf0eb] pt-5">
        <h3 className="text-lg font-semibold">Create New Demo Book</h3>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="grid gap-1 text-sm font-medium text-[#46534a]">
            Title
            <input
              className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
          </label>
          <label className="grid gap-1 text-sm font-medium text-[#46534a]">
            Author (optional)
            <input
              className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]"
              value={author}
              onChange={(event) => setAuthor(event.target.value)}
            />
          </label>
          <label className="grid gap-1 text-sm font-medium text-[#46534a]">
            Genre (optional)
            <input
              className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]"
              value={genre}
              onChange={(event) => setGenre(event.target.value)}
            />
          </label>
          <label className="grid gap-1 text-sm font-medium text-[#46534a]">
            Description (optional)
            <input
              className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </label>
        </div>

        <div className="mt-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-[#46534a]">Chapters ({chapters.length})</p>
            <button
              type="button"
              className="rounded-md border border-[#bdd5c1] bg-[#eff8f0] px-3 py-1 text-sm text-[#1f6b3a]"
              onClick={addChapter}
            >
              + Add chapter
            </button>
          </div>
          <div className="mt-3 space-y-4">
            {chapters.map((chapter, index) => (
              <div key={index} className="rounded-md border border-[#edf0eb] bg-[#fbfcfa] p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#657166]">Chapter {index + 1}</p>
                  {chapters.length > 1 ? (
                    <button
                      type="button"
                      className="text-xs text-[#a2382b]"
                      onClick={() => removeChapter(index)}
                    >
                      Remove
                    </button>
                  ) : null}
                </div>
                <label className="mt-2 grid gap-1 text-sm font-medium text-[#46534a]">
                  Chapter title
                  <input
                    className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]"
                    value={chapter.title}
                    onChange={(event) => updateChapter(index, "title", event.target.value)}
                  />
                </label>
                <label className="mt-2 grid gap-1 text-sm font-medium text-[#46534a]">
                  Chapter text
                  <textarea
                    className="min-h-24 rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]"
                    value={chapter.text}
                    onChange={(event) => updateChapter(index, "text", event.target.value)}
                  />
                </label>
                <label className="mt-2 grid gap-1 text-sm font-medium text-[#46534a]">
                  Description (optional)
                  <input
                    className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]"
                    value={chapter.description}
                    onChange={(event) => updateChapter(index, "description", event.target.value)}
                  />
                </label>
              </div>
            ))}
          </div>
        </div>

        <button
          disabled={disabled || !canCreate()}
          className="mt-4 rounded-md border border-[#1f615d] bg-[#1f615d] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          onClick={handleCreate}
        >
          Create public demo book
        </button>
      </div>

      <div className="mt-6 border-t border-[#edf0eb] pt-5">
        <h3 className="text-lg font-semibold">Append Chapter to Demo Book</h3>
        <div className="mt-3 grid gap-3">
          <label className="grid gap-1 text-sm font-medium text-[#46534a]">
            Book ID
            <input
              className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]"
              value={appendBookId}
              onChange={(event) => setAppendBookId(event.target.value)}
              placeholder="UUID"
            />
          </label>
          <label className="grid gap-1 text-sm font-medium text-[#46534a]">
            Chapter title
            <input
              className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]"
              value={appendTitle}
              onChange={(event) => setAppendTitle(event.target.value)}
            />
          </label>
          <label className="grid gap-1 text-sm font-medium text-[#46534a]">
            Chapter text
            <textarea
              className="min-h-32 rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]"
              value={appendText}
              onChange={(event) => setAppendText(event.target.value)}
            />
          </label>
          <label className="grid gap-1 text-sm font-medium text-[#46534a]">
            Description (optional)
            <input
              className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]"
              value={appendDescription}
              onChange={(event) => setAppendDescription(event.target.value)}
            />
          </label>
        </div>
        <button
          disabled={disabled || !canAppend()}
          className="mt-4 rounded-md border border-[#1f615d] bg-[#1f615d] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          onClick={handleAppend}
        >
          Append chapter
        </button>
      </div>
    </section>
  )
}

function PlatformMetricsPanel({ metrics }: { metrics: AdminMetrics | null }) {
  if (!metrics) return null
  const redisPrefixCounts = Object.entries(metrics.redis_key_prefix_counts ?? {})
  const redisKeyCount = metrics.redis_key_count
  const redisClientCount = metrics.redis_connected_clients
  return (
    <section className="rounded-lg border border-[#d9dfd6] bg-white p-5">
      <h2 className="text-xl font-semibold">Platform Overview</h2>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <AdminMetric label="Users" value={metrics.users.toLocaleString()} />
        <AdminMetric label="Books" value={metrics.books.toLocaleString()} />
        <AdminMetric label="Characters" value={metrics.characters.toLocaleString()} />
        <AdminMetric label="Chunks Indexed" value={metrics.chunks_indexed.toLocaleString()} />
        <AdminMetric label="Summaries Cached" value={metrics.summaries_cached.toLocaleString()} />
        <AdminMetric label="Redis Memory" value={`${metrics.redis_memory_mb} MB`} />
        {typeof redisKeyCount === "number" ? <AdminMetric label="Redis Keys" value={redisKeyCount.toLocaleString()} /> : null}
        {typeof redisClientCount === "number" ? <AdminMetric label="Redis Clients" value={redisClientCount.toLocaleString()} /> : null}
      </div>
      {redisPrefixCounts.length > 0 ? (
        <div className="mt-4 rounded-md border border-[#d9dfd6] bg-[#f8faf7] p-3">
          <h3 className="text-sm font-semibold text-[#26352c]">Redis Key Prefixes</h3>
          <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {redisPrefixCounts.slice(0, 9).map(([prefix, count]) => (
              <div key={prefix} className="flex items-center justify-between rounded border border-[#e2e7df] bg-white px-3 py-2 text-sm">
                <span className="truncate text-[#566258]">{prefix}</span>
                <span className="font-semibold text-[#1f2d24]">{count.toLocaleString()}</span>
              </div>
            ))}
          </div>
          {metrics.redis_key_scan_truncated ? (
            <p className="mt-2 text-xs text-[#617065]">Prefix counts are sampled.</p>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}

function ReliabilityPanel({
  operations,
  quality,
  margin,
  executions,
  incidents,
  disabled,
  onRetry,
  onDismiss,
  onIncident,
  onResolve,
}: {
  operations: AdminOperationsMetrics | null
  quality: AdminAiQualityMetrics | null
  margin: AdminContributionMargin | null
  executions: AdminTaskExecution[]
  incidents: AdminSupportIncident[]
  disabled: boolean
  onRetry: (id: string, reason: string) => void
  onDismiss: (id: string, reason: string) => void
  onIncident: (body: { user_id?: string; book_id?: string; category: string; feature?: string; severity: string; summary: string }) => void
  onResolve: (id: string, resolution: string) => void
}) {
  const [taskReason, setTaskReason] = useState("Reviewed by operator")
  const [incident, setIncident] = useState({ user_id: "", book_id: "", category: "ai_accuracy", feature: "extraction", severity: "medium", summary: "" })
  const money = (value?: number) => `$${Number(value ?? 0).toFixed(2)}`
  return (
    <section className="space-y-6 rounded-lg border border-[#d9dfd6] bg-white p-5">
      <div>
        <h2 className="text-xl font-semibold">Reliability and Unit Economics</h2>
        <p className="mt-1 text-sm text-[#617065]">Durable jobs, review-confirmed quality, support load, and estimated contribution margin.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <AdminMetric label="Terminal failures" value={String(operations?.terminal_failures ?? 0)} />
        <AdminMetric label="Queue depth" value={String(operations?.queue_depth ?? 0)} />
        <AdminMetric label="Retries" value={String(operations?.retry_count ?? 0)} />
        <AdminMetric label="Oldest job" value={`${operations?.oldest_job_age_seconds ?? 0}s`} />
        <AdminMetric label="Paused runs" value={String(operations?.paused_runs ?? 0)} />
        <AdminMetric label="Contribution" value={money(margin?.contribution_margin)} />
        <AdminMetric label="Reviewed AI" value={String(quality?.reviewed ?? 0)} />
        <AdminMetric label="Accepted" value={String(quality?.accepted ?? 0)} />
        <AdminMetric label="Character corrections" value={String(quality?.character_corrections_after_promotion ?? 0)} />
        <AdminMetric label="Relationship corrections" value={String(quality?.relationship_corrections ?? 0)} />
        <AdminMetric label="LLM cost" value={money(margin?.llm_cost)} />
        <AdminMetric label="Recognized revenue" value={money(margin?.recognized_net_revenue)} />
      </div>
      {margin?.allocation_basis ? <p className="text-xs text-[#617065]">Allocation basis: {margin.allocation_basis}</p> : null}
      <div>
        <label className="grid gap-1 text-sm font-medium">Operator reason
          <input className="rounded-md border border-[#cdd5cc] px-3 py-2" value={taskReason} onChange={(event) => setTaskReason(event.target.value)} />
        </label>
        <div className="mt-3 space-y-2">
          {executions.map((execution) => (
            <div key={execution.id} className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-[#e3e7e1] p-3 text-sm">
              <div><strong>{execution.task_name}</strong> · chapter {execution.chapter_number ?? "—"}<p className="text-[#7a5047]">{execution.error_category}: {execution.error_detail}</p></div>
              <div className="flex gap-2">
                <button disabled={disabled || !taskReason.trim()} className="rounded border px-3 py-1 disabled:opacity-50" onClick={() => onRetry(execution.id, taskReason)}>Retry</button>
                <button disabled={disabled || !taskReason.trim()} className="rounded border border-[#e8c4c0] px-3 py-1 text-[#a2382b] disabled:opacity-50" onClick={() => onDismiss(execution.id, taskReason)}>Dismiss</button>
              </div>
            </div>
          ))}
          {executions.length === 0 ? <p className="text-sm text-[#617065]">No terminal pipeline failures.</p> : null}
        </div>
      </div>
      <form className="grid gap-3 md:grid-cols-2" onSubmit={(event) => { event.preventDefault(); onIncident({ ...incident, user_id: incident.user_id || undefined, book_id: incident.book_id || undefined }); setIncident((current) => ({ ...current, summary: "" })) }}>
        <h3 className="md:col-span-2 font-semibold">Record support incident</h3>
        {(["user_id", "book_id", "category", "feature", "summary"] as const).map((field) => (
          <label key={field} className={`grid gap-1 text-sm ${field === "summary" ? "md:col-span-2" : ""}`}>{field.replace("_", " ")}
            <input required={field === "category" || field === "summary"} className="rounded-md border border-[#cdd5cc] px-3 py-2" value={incident[field]} onChange={(event) => setIncident((current) => ({ ...current, [field]: event.target.value }))} />
          </label>
        ))}
        <button disabled={disabled || !incident.summary.trim()} className="rounded-md bg-[#1f615d] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Record incident</button>
      </form>
      <div className="space-y-2">
        {incidents.slice(0, 20).map((item) => (
          <div key={item.id} className="flex items-center justify-between gap-3 rounded-md border border-[#e3e7e1] p-3 text-sm">
            <span><strong>{item.category}</strong> · {item.summary} <StatusBadge tone={item.status === "resolved" ? "success" : "warning"}>{item.status}</StatusBadge></span>
            {item.status !== "resolved" ? <button disabled={disabled} className="rounded border px-3 py-1" onClick={() => onResolve(item.id, "Resolved by operator")}>Resolve</button> : null}
          </div>
        ))}
      </div>
    </section>
  )
}
