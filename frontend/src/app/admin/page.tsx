"use client"

import { useEffect, useState, useTransition } from "react"
import type { ReactNode } from "react"
import { adminApi } from "@/lib/api/admin"
import type {
  AdminAuditEvent,
  AdminBillingStatus,
  AdminContentReport,
  AdminPrincipal,
  AdminPublicShare,
  AdminRefundReview,
  AdminScope,
  AdminSession,
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

        {message ? <div className="rounded-lg border border-[#b8c7b8] bg-white px-4 py-3 text-sm">{message}</div> : null}

        {session.requires_step_up ? (
          <StepUpPanel onSubmit={(password) => runAction(() => adminApi.stepUp(password).then(() => adminApi.session().then(setSession)), "Admin verification complete.")} />
        ) : null}

        <section className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          {hasScope(session, "moderation_admin") ? (
            <ModerationPanel
              publicShares={publicShares}
              reports={reports}
              disabled={isPending}
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
              disabled={isPending}
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

        {session.is_owner ? (
          <section className="grid gap-6 lg:grid-cols-2">
            <AccessPanel
              principals={principals}
              disabled={isPending}
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
        <input className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm" placeholder="Book ID" value={bookId} onChange={(event) => setBookId(event.target.value)} />
        <textarea className="min-h-20 rounded-md border border-[#c9d2c8] px-3 py-2 text-sm" placeholder="Required reason" value={reason} onChange={(event) => setReason(event.target.value)} />
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
      <textarea className="mt-2 min-h-16 w-full rounded-md border border-[#c9d2c8] px-3 py-2 text-sm" placeholder="Required decision reason" value={reason} onChange={(event) => setReason(event.target.value)} />
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
        <input className="rounded-md border border-[#c9d2c8] px-3 py-2 text-sm" placeholder="User ID" value={userId} onChange={(event) => setUserId(event.target.value)} />
        <textarea className="min-h-16 rounded-md border border-[#c9d2c8] px-3 py-2 text-sm" placeholder="Required owner reason" value={reason} onChange={(event) => setReason(event.target.value)} />
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
