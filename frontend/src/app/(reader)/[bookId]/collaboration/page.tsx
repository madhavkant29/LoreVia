"use client"

import { useMemo, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import dynamic from "next/dynamic"
import { useParams } from "next/navigation"

import { betaReadsApi } from "@/lib/api/betaReads"
import { booksApi } from "@/lib/api/books"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { parseQuestionLines } from "@/lib/utils/betaRead"
import type { BetaReadAssignment } from "@/types/betaRead"
import type { Book, BookCollaborator, CollaborationPermissions, CollaborationRole, CollaborationScope } from "@/types/book"
import type { BetaReadAssignmentCreateInput } from "@/types/reader"

const AuthorToolsNav = dynamic(
  () => import("@/components/layout/AuthorToolsNav").then((module) => module.AuthorToolsNav),
  {
    ssr: false,
    loading: () => <div className="rounded-md border border-white/[0.065] bg-[#0d141c] p-4" />,
  }
)

const ROLE_OPTIONS: Array<{ value: CollaborationRole; label: string; detail: string }> = [
  { value: "viewer", label: "Viewer", detail: "Read-only access to the shared draft." },
  { value: "reader_only", label: "Reader-only", detail: "A lighter studio role for pure read access." },
  { value: "commenter", label: "Commenter", detail: "Can read and leave feedback without editing." },
  { value: "beta_reader", label: "Beta Reader", detail: "Feedback-focused role for reader response." },
  { value: "editor", label: "Editor", detail: "Hands-on manuscript editing access." },
  { value: "developmental_editor", label: "Developmental editor", detail: "Structure, continuity, and arc partner." },
  { value: "coauthor", label: "Coauthor", detail: "Full creative collaborator across the manuscript." },
  { value: "co_writer", label: "Co-writer", detail: "Studio-ready writing partner role." },
]

const ROLE_PRESETS: Record<CollaborationRole, CollaborationPermissions> = {
  viewer: {
    can_edit_manuscript: false,
    can_view_story_bible: true,
    can_run_ai_scans: true,
    can_export: false,
    can_comment: false,
    can_view_selected_chapters_only: true,
  },
  reader_only: {
    can_edit_manuscript: false,
    can_view_story_bible: true,
    can_run_ai_scans: true,
    can_export: false,
    can_comment: false,
    can_view_selected_chapters_only: true,
  },
  commenter: {
    can_edit_manuscript: false,
    can_view_story_bible: true,
    can_run_ai_scans: true,
    can_export: false,
    can_comment: true,
    can_view_selected_chapters_only: true,
  },
  beta_reader: {
    can_edit_manuscript: false,
    can_view_story_bible: false,
    can_run_ai_scans: false,
    can_export: false,
    can_comment: true,
    can_view_selected_chapters_only: true,
  },
  editor: {
    can_edit_manuscript: true,
    can_view_story_bible: true,
    can_run_ai_scans: true,
    can_export: true,
    can_comment: true,
    can_view_selected_chapters_only: false,
  },
  developmental_editor: {
    can_edit_manuscript: true,
    can_view_story_bible: true,
    can_run_ai_scans: true,
    can_export: true,
    can_comment: true,
    can_view_selected_chapters_only: false,
  },
  coauthor: {
    can_edit_manuscript: true,
    can_view_story_bible: true,
    can_run_ai_scans: true,
    can_export: true,
    can_comment: true,
    can_view_selected_chapters_only: false,
  },
  co_writer: {
    can_edit_manuscript: true,
    can_view_story_bible: true,
    can_run_ai_scans: true,
    can_export: true,
    can_comment: true,
    can_view_selected_chapters_only: false,
  },
}

const PERMISSION_OPTIONS: Array<{ key: keyof CollaborationPermissions; label: string; detail: string }> = [
  { key: "can_edit_manuscript", label: "Can edit manuscript", detail: "Scenes, chapter versions, and drafting workspace." },
  { key: "can_view_story_bible", label: "Can view story bible", detail: "Character bible and story reference surfaces." },
  { key: "can_run_ai_scans", label: "Can run AI scans", detail: "Continuity, revision, and confusion analysis." },
  { key: "can_export", label: "Can export", detail: "Manuscript and story-bible exports." },
  { key: "can_comment", label: "Can comment only", detail: "Leave notes without needing edit access." },
  { key: "can_view_selected_chapters_only", label: "Can view selected chapters only", detail: "Restrict access to a chapter range instead of the whole draft." },
]

const BETA_SCOPE_OPTIONS: Array<{ value: "full_book" | "chapter_range" | "section"; label: string }> = [
  { value: "full_book", label: "Full manuscript" },
  { value: "chapter_range", label: "Chapter range" },
  { value: "section", label: "Section" },
]

const DEFAULT_SCOPE: CollaborationScope = {
  chapter_start: 1,
  chapter_end: 10,
  character_bible: true,
  continuity_report: true,
  reader_confusion_report: true,
}

function roleMeta(role: CollaborationRole | string) {
  return ROLE_OPTIONS.find((option) => option.value === role)
}

function roleLabel(role: CollaborationRole | string) {
  return roleMeta(role)?.label ?? role.replace(/_/g, " ")
}

function scopeSummary(scope: CollaborationScope, permissions: CollaborationPermissions) {
  const chapterSummary = permissions.can_view_selected_chapters_only
    ? `Chapters ${scope.chapter_start ?? 1}-${scope.chapter_end ?? "end"}`
    : "All chapters"
  const extras = [
    scope.character_bible ? "character bible" : null,
    scope.continuity_report ? "continuity report" : null,
    scope.reader_confusion_report ? "reader confusion report" : null,
  ].filter(Boolean)
  return [chapterSummary, ...extras].join(" / ")
}

function permissionSummary(permissions: CollaborationPermissions) {
  const labels = [
    permissions.can_edit_manuscript ? "edit manuscript" : null,
    permissions.can_view_story_bible ? "story bible" : null,
    permissions.can_run_ai_scans ? "AI scans" : null,
    permissions.can_export ? "export" : null,
    permissions.can_comment ? "comment" : null,
  ].filter(Boolean)
  return labels.length > 0 ? labels.join(" / ") : "Scoped read access"
}

function betaScopeSummary(assignment: BetaReadAssignment) {
  if (assignment.scope_kind === "full_book") return "Full manuscript beta read"
  if (assignment.scope_kind === "section") {
    return assignment.section_label || "Section beta read"
  }
  return `Chapters ${assignment.chapter_start ?? 1}-${assignment.chapter_end ?? assignment.chapter_start ?? "end"}`
}

export default function CollaborationPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const { data: book = null } = useQuery<Book | null>({
    queryKey: asQueryKey(bookCacheKey(bookId, "detail")),
    queryFn: () => booksApi.get(bookId),
  })
  const {
    data: collaborators = [],
    refetch: refetchCollaborators,
  } = useQuery<BookCollaborator[]>({
    queryKey: asQueryKey(`collaboration:${bookId}:collaborators`),
    queryFn: () => booksApi.listCollaborators(bookId).catch(() => []),
  })
  const {
    data: betaAssignments = [],
    refetch: refetchBetaAssignments,
  } = useQuery<BetaReadAssignment[]>({
    queryKey: asQueryKey(`collaboration:${bookId}:beta-assignments`),
    queryFn: () => betaReadsApi.listBookAssignments(bookId).catch(() => []),
  })
  const [email, setEmail] = useState("")
  const [displayName, setDisplayName] = useState("")
  const [role, setRole] = useState<CollaborationRole>("beta_reader")
  const [scope, setScope] = useState<CollaborationScope>(DEFAULT_SCOPE)
  const [permissions, setPermissions] = useState<CollaborationPermissions>({ ...ROLE_PRESETS.beta_reader })
  const [betaForm, setBetaForm] = useState<BetaReadAssignmentCreateInput>({
    readerEmail: "",
    taskLabel: "Full manuscript beta read",
    scopeKind: "full_book",
    sectionLabel: null,
    chapterStart: null,
    chapterEnd: null,
    windowDays: 3,
    requiredProgressPct: 100,
    requiredCommentCount: 3,
    requiredFeedbackItemCount: 1,
    requireFinalFeedback: true,
    authorQuestions: ["What confused you most?", "Which moment landed best?"],
  })
  const [authorQuestionsText, setAuthorQuestionsText] = useState("What confused you most?\nWhich moment landed best?")
  const [status, setStatus] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const emailInputRef = useRef<HTMLInputElement | null>(null)
  const displayNameInputRef = useRef<HTMLInputElement | null>(null)

  const sortedCollaborators = useMemo(
    () => [...collaborators].sort((left, right) => left.email.localeCompare(right.email)),
    [collaborators]
  )

  const activeRoleDetail = roleMeta(role)?.detail ?? ""

  const updateScope = (patch: Partial<CollaborationScope>) => {
    setScope((current) => ({ ...current, ...patch }))
  }

  const updatePermission = (key: keyof CollaborationPermissions, value: boolean) => {
    setPermissions((current) => ({ ...current, [key]: value }))
  }

  const onRoleChange = (nextRole: CollaborationRole) => {
    setRole(nextRole)
    setPermissions({ ...ROLE_PRESETS[nextRole] })
  }

  const submit = async () => {
    const nextEmail = email.trim() || emailInputRef.current?.value.trim() || ""
    const nextDisplayName = displayName.trim() || displayNameInputRef.current?.value.trim() || ""
    if (!nextEmail) {
      setStatus("Collaborator email is required.")
      return
    }
    setSaving(true)
    setStatus(null)
    try {
      await booksApi.createCollaborator(bookId, {
        email: nextEmail,
        displayName: nextDisplayName || null,
        role,
        scope,
        permissions,
      })
      await refetchCollaborators()
      setEmail("")
      setDisplayName("")
      setStatus("Share saved.")
    } catch {
      setStatus("Could not save this share.")
    } finally {
      setSaving(false)
    }
  }

  const submitBetaAssignment = async () => {
    if (!betaForm.readerEmail.trim() || !betaForm.taskLabel.trim()) return
    setSaving(true)
    setStatus(null)
    try {
      await betaReadsApi.createAssignment(bookId, betaForm)
      await refetchBetaAssignments()
      const defaultQuestions = ["What confused you most?", "Which moment landed best?"]
      setBetaForm((current) => ({
        ...current,
        readerEmail: "",
        authorQuestions: defaultQuestions,
      }))
      setAuthorQuestionsText(defaultQuestions.join("\n"))
      setStatus("Beta read assigned.")
    } catch {
      setStatus("Could not assign this beta read.")
    } finally {
      setSaving(false)
    }
  }

  const revoke = async (collaborator: BookCollaborator) => {
    setStatus(null)
    try {
      await booksApi.updateCollaborator(bookId, collaborator.id, { inviteStatus: "revoked" })
      await refetchCollaborators()
      setStatus("Share revoked.")
    } catch {
      setStatus("Could not revoke this share.")
    }
  }

  const revokeBetaAssignment = async (assignment: BetaReadAssignment) => {
    setStatus(null)
    try {
      await betaReadsApi.revokeAssignment(bookId, assignment.id)
      await refetchBetaAssignments()
      setStatus("Beta read revoked.")
    } catch {
      setStatus("Could not revoke this beta read.")
    }
  }

  return (
    <div className={`min-h-screen ${isDark ? "bg-[#070b10] text-slate-100" : "bg-[#f7f7fb] text-slate-950"}`}>
      <div className="mx-auto grid max-w-[94rem] gap-5 px-4 pb-28 pt-5 sm:px-6 lg:grid-cols-[18rem_minmax(0,1fr)] lg:px-8">
        <div className="hidden lg:block lg:sticky lg:top-5 lg:self-start">
          <AuthorToolsNav
            bookId={bookId}
            active="collaboration"
            isDark={isDark}
            bookData={book}
            title="Author workspace"
            description="Invite readers, editors, and co-writers into the right slices of the story."
            mode={book?.mode ?? "author"}
            variant="rail"
          />
        </div>

        <main className="min-w-0 space-y-5">
          <section className={`rounded-md border p-5 ${isDark ? "border-white/[0.065] bg-[#0d141c]" : "border-slate-200/70 bg-white"}`}>
            <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-violet-300" : "text-violet-700"}`}>Collaboration</p>
            <div className="mt-3 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <h1 className={`text-3xl font-semibold tracking-normal ${isDark ? "text-white" : "text-slate-950"}`}>
                  {book?.title ?? "Story"} sharing
                </h1>
                <p className={`mt-2 max-w-3xl text-sm leading-6 ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                  Share exact chapters, story-bible surfaces, and editing powers with beta readers, editors, and coauthors without opening the entire draft.
                </p>
              </div>
              {status ? <p className={`text-sm font-semibold ${status.includes("Could") ? "text-rose-400" : "text-emerald-400"}`}>{status}</p> : null}
            </div>
          </section>

          <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <div className={`rounded-md border p-5 ${isDark ? "border-white/[0.065] bg-[#0d141c]" : "border-slate-200/70 bg-white"}`}>
              <h2 className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Invite collaborator</h2>
              <div className="mt-5 grid gap-3">
                <input
                  ref={emailInputRef}
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="reader@example.com"
                  className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 placeholder:text-slate-600 focus:border-violet-400" : "border-slate-200 bg-white text-slate-900 placeholder:text-slate-400 focus:border-violet-400"}`}
                />
                <input
                  ref={displayNameInputRef}
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  placeholder="Display name"
                  className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 placeholder:text-slate-600 focus:border-violet-400" : "border-slate-200 bg-white text-slate-900 placeholder:text-slate-400 focus:border-violet-400"}`}
                />
                <select
                  value={role}
                  onChange={(event) => onRoleChange(event.target.value as CollaborationRole)}
                  className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-violet-400" : "border-slate-200 bg-white text-slate-900 focus:border-violet-400"}`}
                >
                  {ROLE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
                <p className={`text-sm font-semibold ${isDark ? "text-slate-200" : "text-slate-800"}`}>
                  {roleMeta(role)?.label}
                </p>
                <p className={`text-xs leading-5 ${isDark ? "text-slate-500" : "text-slate-500"}`}>{activeRoleDetail}</p>
              </div>

              <div className="mt-6">
                <div className="flex items-center justify-between gap-3">
                  <h3 className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Permissions</h3>
                  <span className={`text-[11px] ${isDark ? "text-slate-500" : "text-slate-400"}`}>{permissionSummary(permissions)}</span>
                </div>
                <div className="mt-3 grid gap-2">
                  {PERMISSION_OPTIONS.map((option) => (
                    <label key={option.key} className={`flex items-start justify-between gap-3 rounded-md border p-3 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-slate-50"}`}>
                      <div className="min-w-0">
                        <p className={`text-sm font-medium ${isDark ? "text-slate-100" : "text-slate-800"}`}>{option.label}</p>
                        <p className={`mt-1 text-xs leading-5 ${isDark ? "text-slate-500" : "text-slate-500"}`}>{option.detail}</p>
                      </div>
                      <input
                        type="checkbox"
                        checked={Boolean(permissions[option.key])}
                        onChange={(event) => updatePermission(option.key, event.target.checked)}
                        className="mt-0.5 h-4 w-4 rounded border-slate-300 text-violet-600 focus:ring-violet-500"
                      />
                    </label>
                  ))}
                </div>
              </div>

              <div className="mt-6">
                <div className="flex items-center justify-between gap-3">
                  <h3 className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Story scope</h3>
                  <span className={`text-[11px] ${isDark ? "text-slate-500" : "text-slate-400"}`}>{scopeSummary(scope, permissions)}</span>
                </div>

                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <label className="text-xs font-semibold">
                    <span className={isDark ? "text-slate-400" : "text-slate-500"}>From chapter</span>
                    <input
                      type="number"
                      min="1"
                      disabled={!permissions.can_view_selected_chapters_only}
                      value={scope.chapter_start ?? ""}
                      onChange={(event) => updateScope({ chapter_start: event.target.value ? Number(event.target.value) : null })}
                      className={`mt-2 h-11 w-full rounded-md border px-3 text-sm outline-none transition disabled:cursor-not-allowed disabled:opacity-50 ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-violet-400" : "border-slate-200 bg-white text-slate-900 focus:border-violet-400"}`}
                    />
                  </label>
                  <label className="text-xs font-semibold">
                    <span className={isDark ? "text-slate-400" : "text-slate-500"}>Through chapter</span>
                    <input
                      type="number"
                      min="1"
                      disabled={!permissions.can_view_selected_chapters_only}
                      value={scope.chapter_end ?? ""}
                      onChange={(event) => updateScope({ chapter_end: event.target.value ? Number(event.target.value) : null })}
                      className={`mt-2 h-11 w-full rounded-md border px-3 text-sm outline-none transition disabled:cursor-not-allowed disabled:opacity-50 ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-violet-400" : "border-slate-200 bg-white text-slate-900 focus:border-violet-400"}`}
                    />
                  </label>
                </div>

                <div className="mt-3 grid gap-2">
                  {[
                    ["character_bible", "Character bible"],
                    ["continuity_report", "Continuity report"],
                    ["reader_confusion_report", "Reader confusion report"],
                  ].map(([key, label]) => (
                    <label key={key} className={`flex items-center justify-between rounded-md border p-3 text-sm ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-slate-50"}`}>
                      <span className={isDark ? "text-slate-200" : "text-slate-700"}>{label}</span>
                      <input
                        type="checkbox"
                        checked={Boolean(scope[key as keyof CollaborationScope])}
                        onChange={(event) => updateScope({ [key]: event.target.checked } as Partial<CollaborationScope>)}
                        className="h-4 w-4 rounded border-slate-300 text-violet-600 focus:ring-violet-500"
                      />
                    </label>
                  ))}
                </div>
              </div>

              <button
                onClick={() => void submit()}
                disabled={saving || !(email.trim() || emailInputRef.current?.value.trim())}
                className={`mt-6 inline-flex h-11 w-full items-center justify-center rounded-md px-4 text-sm font-semibold transition ${isDark ? "bg-violet-500 text-white hover:bg-violet-400 disabled:bg-violet-500/40" : "bg-violet-600 text-white hover:bg-violet-500 disabled:bg-violet-300"}`}
              >
                {saving ? "Saving..." : "Save share"}
              </button>
            </div>

            <div className={`rounded-md border p-5 ${isDark ? "border-white/[0.065] bg-[#0d141c]" : "border-slate-200/70 bg-white"}`}>
              <div className="flex items-center justify-between gap-3">
                <h2 className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Active shares</h2>
                <span className={`text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>{sortedCollaborators.length} total</span>
              </div>
              <div className="mt-5 space-y-3">
                {sortedCollaborators.length > 0 ? sortedCollaborators.map((collaborator) => (
                  <div key={collaborator.id} className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-slate-50"}`}>
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <p className={`truncate text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{collaborator.display_name || collaborator.email}</p>
                        <p className={`mt-1 truncate text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>{collaborator.email}</p>
                      </div>
                      <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${collaborator.invite_status === "active" ? "bg-emerald-500/10 text-emerald-400" : "bg-slate-500/10 text-slate-400"}`}>
                        {collaborator.invite_status}
                      </span>
                    </div>
                    <div className="mt-4 grid gap-2 text-sm">
                      <p className={isDark ? "text-slate-300" : "text-slate-700"}>Role · {roleLabel(collaborator.role)}</p>
                      <p className={isDark ? "text-slate-400" : "text-slate-600"}>{permissionSummary(collaborator.permissions)}</p>
                      <p className={isDark ? "text-slate-500" : "text-slate-500"}>{scopeSummary(collaborator.scope, collaborator.permissions)}</p>
                    </div>
                    {collaborator.invite_status === "active" ? (
                      <button onClick={() => void revoke(collaborator)} className="mt-4 text-xs font-semibold text-rose-400">
                        Revoke
                      </button>
                    ) : null}
                  </div>
                )) : (
                  <div className={`rounded-md border border-dashed p-5 text-sm ${isDark ? "border-white/[0.08] text-slate-500" : "border-slate-200 text-slate-400"}`}>
                    No collaborators yet.
                  </div>
                )}
              </div>
            </div>
          </section>

          <section className={`rounded-md border p-5 ${isDark ? "border-white/[0.065] bg-[#0d141c]" : "border-slate-200/70 bg-white"}`}>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <h2 className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Beta read assignments</h2>
                <p className={`mt-2 max-w-3xl text-sm leading-6 ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                  Grant a reader a strict 3 to 7 day beta-reading window with feedback requirements and revocation controls.
                </p>
              </div>
              <span className={`text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>{betaAssignments.length} assignments</span>
            </div>

            <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
              <div className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-slate-50"}`}>
                <h3 className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Assign beta reader</h3>
                <div className="mt-4 grid gap-3">
                  <input
                    value={betaForm.readerEmail}
                    onChange={(event) => setBetaForm((current) => ({ ...current, readerEmail: event.target.value }))}
                    placeholder="beta.invitee@example.net"
                    className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#0d141c] text-slate-100 placeholder:text-slate-600 focus:border-violet-400" : "border-slate-200 bg-white text-slate-900 placeholder:text-slate-400 focus:border-violet-400"}`}
                  />
                  <input
                    value={betaForm.taskLabel}
                    onChange={(event) => setBetaForm((current) => ({ ...current, taskLabel: event.target.value }))}
                    placeholder="Full manuscript beta read"
                    className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#0d141c] text-slate-100 placeholder:text-slate-600 focus:border-violet-400" : "border-slate-200 bg-white text-slate-900 placeholder:text-slate-400 focus:border-violet-400"}`}
                  />
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div
                      className={`grid h-11 grid-cols-3 rounded-md border p-1 text-sm ${isDark ? "border-white/[0.08] bg-[#0d141c]" : "border-slate-200 bg-white"}`}
                      role="group"
                      aria-label="Beta read scope"
                    >
                      {BETA_SCOPE_OPTIONS.map((option) => {
                        const isActive = (betaForm.scopeKind ?? "full_book") === option.value
                        return (
                          <button
                            key={option.value}
                            type="button"
                            onClick={() => setBetaForm((current) => ({ ...current, scopeKind: option.value }))}
                            className={`rounded-md px-3 text-sm font-medium transition ${
                              isActive
                                ? isDark
                                  ? "bg-violet-500 text-white"
                                  : "bg-violet-600 text-white"
                                : isDark
                                  ? "text-slate-300 hover:bg-white/[0.04]"
                                  : "text-slate-700 hover:bg-slate-50"
                            }`}
                            aria-pressed={isActive}
                          >
                            {option.label}
                          </button>
                        )
                      })}
                    </div>
                    <input
                      type="number"
                      min="3"
                      max="7"
                      value={betaForm.windowDays}
                      onChange={(event) => setBetaForm((current) => ({ ...current, windowDays: Number(event.target.value || 3) }))}
                      className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#0d141c] text-slate-100 focus:border-violet-400" : "border-slate-200 bg-white text-slate-900 focus:border-violet-400"}`}
                    />
                  </div>

                  {betaForm.scopeKind !== "full_book" ? (
                    <div className="grid gap-3 sm:grid-cols-2">
                      <input
                        type="number"
                        min="1"
                        value={betaForm.chapterStart ?? ""}
                        onChange={(event) => setBetaForm((current) => ({ ...current, chapterStart: event.target.value ? Number(event.target.value) : null }))}
                        placeholder="Start chapter"
                        className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#0d141c] text-slate-100 placeholder:text-slate-600 focus:border-violet-400" : "border-slate-200 bg-white text-slate-900 placeholder:text-slate-400 focus:border-violet-400"}`}
                      />
                      <input
                        type="number"
                        min="1"
                        value={betaForm.chapterEnd ?? ""}
                        onChange={(event) => setBetaForm((current) => ({ ...current, chapterEnd: event.target.value ? Number(event.target.value) : null }))}
                        placeholder="End chapter"
                        className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#0d141c] text-slate-100 placeholder:text-slate-600 focus:border-violet-400" : "border-slate-200 bg-white text-slate-900 placeholder:text-slate-400 focus:border-violet-400"}`}
                      />
                    </div>
                  ) : null}

                  {betaForm.scopeKind === "section" ? (
                    <input
                      value={betaForm.sectionLabel ?? ""}
                      onChange={(event) => setBetaForm((current) => ({ ...current, sectionLabel: event.target.value }))}
                      placeholder="Section label"
                      className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#0d141c] text-slate-100 placeholder:text-slate-600 focus:border-violet-400" : "border-slate-200 bg-white text-slate-900 placeholder:text-slate-400 focus:border-violet-400"}`}
                    />
                  ) : null}

                  <div className="grid gap-3 sm:grid-cols-3">
                    <input
                      type="number"
                      min="1"
                      max="100"
                      value={betaForm.requiredProgressPct ?? 100}
                      onChange={(event) => setBetaForm((current) => ({ ...current, requiredProgressPct: Number(event.target.value || 100) }))}
                      placeholder="Progress %"
                      className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#0d141c] text-slate-100 placeholder:text-slate-600 focus:border-violet-400" : "border-slate-200 bg-white text-slate-900 placeholder:text-slate-400 focus:border-violet-400"}`}
                    />
                    <input
                      type="number"
                      min="0"
                      value={betaForm.requiredCommentCount ?? 0}
                      onChange={(event) => setBetaForm((current) => ({ ...current, requiredCommentCount: Number(event.target.value || 0) }))}
                      placeholder="Comments"
                      className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#0d141c] text-slate-100 placeholder:text-slate-600 focus:border-violet-400" : "border-slate-200 bg-white text-slate-900 placeholder:text-slate-400 focus:border-violet-400"}`}
                    />
                    <input
                      type="number"
                      min="1"
                      value={betaForm.requiredFeedbackItemCount ?? 1}
                      onChange={(event) => setBetaForm((current) => ({ ...current, requiredFeedbackItemCount: Number(event.target.value || 1) }))}
                      placeholder="Feedback items"
                      className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#0d141c] text-slate-100 placeholder:text-slate-600 focus:border-violet-400" : "border-slate-200 bg-white text-slate-900 placeholder:text-slate-400 focus:border-violet-400"}`}
                    />
                  </div>

                  <textarea
                    value={authorQuestionsText}
                    onChange={(event) => {
                      const nextValue = event.target.value
                      const questions = parseQuestionLines(nextValue)
                      setAuthorQuestionsText(nextValue)
                      setBetaForm((current) => ({ ...current, authorQuestions: questions }))
                    }}
                    rows={4}
                    placeholder="One author question per line"
                    className={`rounded-md border px-3 py-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#0d141c] text-slate-100 placeholder:text-slate-600 focus:border-violet-400" : "border-slate-200 bg-white text-slate-900 placeholder:text-slate-400 focus:border-violet-400"}`}
                  />

                  <label className={`flex items-center justify-between rounded-md border p-3 text-sm ${isDark ? "border-white/[0.06] bg-[#0d141c] text-slate-200" : "border-slate-200 bg-white text-slate-700"}`}>
                    <span>Require final feedback before completion</span>
                    <input
                      type="checkbox"
                      checked={betaForm.requireFinalFeedback ?? true}
                      onChange={(event) => setBetaForm((current) => ({ ...current, requireFinalFeedback: event.target.checked }))}
                      className="h-4 w-4 rounded border-slate-300 text-violet-600 focus:ring-violet-500"
                    />
                  </label>
                </div>

                <button
                  onClick={() => void submitBetaAssignment()}
                  disabled={saving || !betaForm.readerEmail.trim() || !betaForm.taskLabel.trim()}
                  className={`mt-5 inline-flex h-11 w-full items-center justify-center rounded-md px-4 text-sm font-semibold transition ${isDark ? "bg-amber-500 text-slate-950 hover:bg-amber-400 disabled:bg-amber-500/40" : "bg-amber-500 text-slate-950 hover:bg-amber-400 disabled:bg-amber-200"}`}
                >
                  {saving ? "Saving..." : "Grant beta read"}
                </button>
              </div>

              <div className="space-y-3">
                {betaAssignments.length > 0 ? betaAssignments.map((assignment) => (
                  <div key={assignment.id} className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-slate-50"}`}>
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <p className={`truncate text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{assignment.reader_email}</p>
                        <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>{assignment.task_label}</p>
                      </div>
                      <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${assignment.view_bucket === "missed" ? "bg-rose-500/10 text-rose-300" : assignment.view_bucket === "completed" ? "bg-emerald-500/10 text-emerald-400" : "bg-amber-500/10 text-amber-300"}`}>
                        {assignment.status_label}
                      </span>
                    </div>
                    <div className="mt-4 grid gap-2 text-sm">
                      <p className={isDark ? "text-slate-300" : "text-slate-700"}>{betaScopeSummary(assignment)}</p>
                      <p className={isDark ? "text-slate-400" : "text-slate-600"}>{assignment.required_comment_count} required comments - {assignment.required_feedback_item_count} feedback item minimum - {assignment.required_progress_pct}% progress</p>
                      <p className={isDark ? "text-slate-500" : "text-slate-500"}>Window: {assignment.window_days} days - Due {new Date(assignment.expires_at).toLocaleString()}</p>
                      <p className={isDark ? "text-slate-500" : "text-slate-500"}>Progress: {Math.round(assignment.progress_pct)}% - Submission: {assignment.submitted_at ? "Submitted" : "Pending"} - Questions: {assignment.question_count}</p>
                    </div>
                    {assignment.penalty_warning ? (
                      <p className="mt-3 text-xs text-amber-400">{assignment.penalty_warning}</p>
                    ) : null}
                    {["active", "in_progress", "ready_to_submit"].includes(assignment.state) ? (
                      <button onClick={() => void revokeBetaAssignment(assignment)} className="mt-4 text-xs font-semibold text-rose-400">
                        Revoke beta read
                      </button>
                    ) : null}
                  </div>
                )) : (
                  <div className={`rounded-md border border-dashed p-5 text-sm ${isDark ? "border-white/[0.08] text-slate-500" : "border-slate-200 text-slate-400"}`}>
                    No beta read assignments yet.
                  </div>
                )}
              </div>
            </div>
          </section>
        </main>
      </div>
    </div>
  )
}
