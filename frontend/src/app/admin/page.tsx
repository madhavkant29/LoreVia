"use client"

import { useEffect, useState, useTransition } from "react"
import type { ReactNode } from "react"
import { adminApi } from "@/lib/api/admin"
import type {
  AdminAuditEvent,
  AdminBillingStatus,
  AdminContentReport,
  AdminCreatorStrike,
  AdminMetrics,
  AdminPrincipal,
  AdminPublicBookCreateOut,
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

const SCOPE_OPTIONS: AdminScope[] = ["moderation_admin", "billing_admin", "super_admin"]

function hasScope(session: AdminSession | null, scope: AdminScope) {
  return Boolean(session?.is_owner || session?.scopes.includes(scope))
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
  const [isPending, startTransition] = useTransition()

  async function refreshAdminData(currentSession: AdminSession) {
    const tasks: Promise<unknown>[] = []
    if (hasScope(currentSession, "moderation_admin")) {
      tasks.push(adminApi.publicShares().then(setPublicShares))
      tasks.push(adminApi.reports().then(setReports))
    }
    if (hasScope(currentSession, "billing_admin")) {
      tasks.push(adminApi.billingStatus().then(setBillingStatus))
      tasks.push(adminApi.refunds().then(setRefunds))
      tasks.push(adminApi.subscriptionMetrics().then(setSubscriptionMetrics))
    }
    if (hasScope(currentSession, "super_admin")) {
      tasks.push(adminApi.metrics().then(setMetrics))
      tasks.push(adminApi.queueDepth().then(setQueueDepth))
      tasks.push(adminApi.taskExecutions().then(setTaskExecutions))
      tasks.push(adminApi.operationsMetrics().then(setOperations))
      tasks.push(adminApi.aiQuality().then(setQuality))
      tasks.push(adminApi.contributionMargin().then(setMargin))
      tasks.push(adminApi.supportIncidents().then(setIncidents))
    }
    if (currentSession.is_owner) {
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
        await refreshAdminData(nextSession)
      })
      .catch(() => {
        if (!cancelled) setNotFound(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  function runAction(action: () => Promise<unknown>, success: string) {
    startTransition(() => {
      action()
        .then(async () => {
          setMessage(success)
          if (session) await refreshAdminData(session)
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
      <div className="mx-auto flex max-w-7xl flex-col gap-8 px-5 py-8">
        <header className="flex flex-col gap-3 border-b border-[#d9dfd6] pb-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#657166]">LoreVia Admin</p>
            <h1 className="mt-2 text-3xl font-semibold">Operations Console</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[#617065]">Moderation, billing, access, and audit review for protected operational workflows.</p>
          </div>
          <div className="text-sm text-[#526056]">
            {session.is_owner ? "Owner" : session.scopes.join(", ")}
            {session.requires_step_up ? " / verification required" : " / recently verified"}
          </div>
        </header>

        <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <AdminMetric label="Publish reviews" value={String(publicShares.length)} />
          <AdminMetric label="Content reports" value={String(reports.length)} />
          <AdminMetric label="Refund reviews" value={String(refunds.length)} />
          <AdminMetric label="Admin principals" value={String(principals.length)} />
        </section>

        {hasScope(session, "super_admin") ? (
          <section className="grid gap-6 lg:grid-cols-2">
            <PlatformMetricsPanel metrics={metrics} />
            <QueueDepthPanel queueDepth={queueDepth} />
          </section>
        ) : null}

        {hasScope(session, "super_admin") ? (
          <RateLimitPanel
            disabled={isPending || session.requires_step_up}
            onLookup={(userId) => adminApi.getRateLimit(userId)}
            onSave={(userId, override) =>
              runAction(() => adminApi.setRateLimit(userId, override), "Rate limit overrides updated.")
            }
          />
        ) : null}

        {hasScope(session, "super_admin") ? (
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

        {hasScope(session, "moderation_admin") && !session.requires_step_up ? (
          <CreatorStrikePanel
            disabled={isPending}
            onSubmit={(userId, body) =>
              runAction(() => adminApi.addStrike(userId, body), "Creator strike applied.")
            }
          />
        ) : null}

        {hasScope(session, "moderation_admin") && !session.requires_step_up ? (
          <PublicDemoBookPanel
            disabled={isPending}
            onCreate={(body) =>
              runAction(() => adminApi.createPublicDemoBook(body), "Public demo book created.")
            }
            onAppend={(bookId, body) =>
              runAction(() => adminApi.appendPublicDemoChapter(bookId, body), "Chapter appended to demo book.")
            }
          />
        ) : null}

        <section className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          {hasScope(session, "moderation_admin") ? (
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

          {hasScope(session, "billing_admin") ? (
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

        {hasScope(session, "billing_admin") ? (
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

        {session.is_owner ? (
          <section className="grid gap-6 lg:grid-cols-2">
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

function AdminMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[#d9dfd6] bg-white px-4 py-4">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#657166]">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-[#1c261f]">{value}</p>
    </div>
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
  return (
    <section className="rounded-lg border border-[#d9dfd6] bg-white p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">Moderation</h2>
        <StatusBadge tone={publicShares.length || reports.length ? "warning" : "success"}>
          {publicShares.length + reports.length} queued
        </StatusBadge>
      </div>
      <div className="mt-4 space-y-3">
        {publicShares.slice(0, 6).map((share) => (
          <div key={share.book_id} className="rounded-md border border-[#edf0eb] bg-[#fbfcfa] p-3">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <p className="font-medium">{share.title}</p>
              <StatusBadge tone={share.copyright_warning ? "warning" : "neutral"}>
                {share.copyright_warning ? "Copyright warning" : "Pending review"}
              </StatusBadge>
            </div>
            <p className="mt-1 text-sm text-[#617065]">{share.author_username ?? share.user_id} / {formatDate(share.requested_at)}</p>
            <p className="mt-1 text-xs text-[#7b877e]">Book ID: {share.book_id}</p>
            <div className="mt-2 flex gap-2">
              <button disabled={disabled} className="rounded-md border border-[#bdd5c1] bg-[#eff8f0] px-3 py-1 text-sm text-[#1f6b3a]" onClick={() => onReview(share.book_id, true)}>Approve</button>
              <button disabled={disabled} className="rounded-md border border-[#e8c4c0] bg-[#fff3f1] px-3 py-1 text-sm text-[#a2382b]" onClick={() => onReview(share.book_id, false, "Rejected after moderation review.")}>Reject</button>
            </div>
          </div>
        ))}
        {publicShares.length === 0 ? <p className="text-sm text-[#617065]">No pending public shares.</p> : null}
      </div>
      <div className="mt-6 grid gap-3">
        <label className="grid gap-1.5 text-sm font-medium text-[#46534a]">
          Book ID
          <input className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]" value={bookId} onChange={(event) => setBookId(event.target.value)} />
        </label>
        <label className="grid gap-1.5 text-sm font-medium text-[#46534a]">
          Required reason
          <textarea className="min-h-20 rounded-md border border-[#c9d2c8] px-3 py-2 text-sm font-normal text-[#1f2a22]" value={reason} onChange={(event) => setReason(event.target.value)} />
        </label>
        <div className="flex flex-wrap gap-2">
          {(["hideBook", "removeBook", "restoreBook"] as const).map((action) => (
            <button key={action} disabled={disabled || !bookId || !reason} className="rounded-md border border-[#d9dfd6] px-3 py-2 text-sm disabled:opacity-50" onClick={() => onBookAction(bookId, action, reason)}>
              {action.replace("Book", "")}
            </button>
          ))}
        </div>
      </div>
      <div className="mt-6">
        <h3 className="text-sm font-semibold uppercase tracking-[0.12em] text-[#617065]">Reports</h3>
        {reports.slice(0, 6).map((report) => (
          <article key={report.id} className="mt-3 rounded-md border border-[#edf0eb] bg-[#fbfcfa] p-3 text-sm">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <p className="font-medium">{report.report_type}: {report.reason}</p>
              <StatusBadge tone={report.status === "open" ? "warning" : "neutral"}>{report.status}</StatusBadge>
            </div>
            {report.details ? <p className="mt-2 leading-6 text-[#617065]">{report.details}</p> : null}
            <p className="mt-2 text-xs text-[#7b877e]">
              Book ID: {report.reported_book_id} / Reporter: {report.reporter_email ?? report.reporter_user_id ?? "anonymous"} / {formatDate(report.created_at)}
            </p>
          </article>
        ))}
        {reports.length === 0 ? <p className="mt-2 text-sm text-[#617065]">No open content reports.</p> : null}
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
  return (
    <section className="rounded-lg border border-[#d9dfd6] bg-white p-5">
      <h2 className="text-xl font-semibold">Refunds</h2>
      {billingStatus ? <BillingStatusPanel status={billingStatus} /> : null}
      <div className="mt-4 space-y-4">
        {refunds.slice(0, 8).map((review) => (
          <RefundRow key={review.id} review={review} disabled={disabled} onApprove={onApprove} onDeny={onDeny} />
        ))}
        {refunds.length === 0 ? <p className="text-sm text-[#617065]">No refund reviews.</p> : null}
      </div>
    </section>
  )
}

function BillingStatusPanel({ status }: { status: AdminBillingStatus }) {
  return (
    <div className="mt-4 rounded-md border border-[#edf0eb] bg-[#f8faf7] p-4 text-sm">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="font-semibold">Billing setup</h3>
        <StatusBadge tone={status.payments_ready ? "success" : "warning"}>{status.payments_ready ? "Ready" : "Action required"}</StatusBadge>
      </div>
      <p className="mt-2 text-[#617065]">
        {status.fully_configured_plan_count} configured plans. Recommended checkout URL: {status.recommended_default_checkout_url}
      </p>
      {status.missing_configuration.length > 0 ? (
        <p className="mt-2 text-[#9a3412]">Missing: {status.missing_configuration.join(", ")}</p>
      ) : (
        <p className="mt-2 text-[#1f6b3a]">All required billing configuration values are present.</p>
      )}
    </div>
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
    <div className="border-t border-[#edf0eb] pt-3">
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
  return (
    <section className="rounded-lg border border-[#d9dfd6] bg-white p-5">
      <h2 className="text-xl font-semibold">Admin Access</h2>
      <div className="mt-4 grid gap-3">
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
      </div>
      <div className="mt-5 space-y-3">
        {principals.map((principal) => (
          <div key={principal.id} className="border-t border-[#edf0eb] pt-3 text-sm">
            <p className="font-medium">{principal.user_id}</p>
            <p className="text-[#617065]">{principal.status} / {principal.is_owner ? "owner" : principal.scopes.join(", ")}</p>
            {principal.status === "active" ? (
              <button disabled={disabled} className="mt-2 rounded-md border border-[#e8c4c0] bg-[#fff3f1] px-3 py-1 text-[#a2382b]" onClick={() => onRevoke(principal.id, "Owner revoked admin access.")}>Revoke</button>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  )
}

function AuditPanel({ events }: { events: AdminAuditEvent[] }) {
  return (
    <section className="rounded-lg border border-[#d9dfd6] bg-white p-5">
      <h2 className="text-xl font-semibold">Audit</h2>
      <div className="mt-4 space-y-3">
        {events.map((event) => (
          <div key={event.id} className="border-t border-[#edf0eb] pt-3 text-sm">
            <p className="font-medium">{event.action_type} / {event.result}</p>
            <p className="text-[#617065]">{event.reason ?? "No reason"} / {formatDate(event.created_at)}</p>
          </div>
        ))}
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

function QueueDepthPanel({ queueDepth }: { queueDepth: AdminQueueDepth | null }) {
  if (!queueDepth) return null
  const queues: { label: string; value: number }[] = [
    { label: "Extraction", value: queueDepth.extraction },
    { label: "Analysis", value: queueDepth.analysis },
    { label: "Embedding", value: queueDepth.embedding },
    { label: "Intelligence", value: queueDepth.intelligence },
  ]
  const max = Math.max(...queues.map((q) => q.value), 1)
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

function SubscriptionMetricsPanel({
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
