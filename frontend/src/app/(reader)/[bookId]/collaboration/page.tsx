"use client"

import { useEffect, useMemo, useState } from "react"
import { useParams } from "next/navigation"

import { AuthorToolsNav } from "@/components/layout/AuthorToolsNav"
import { booksApi } from "@/lib/api/books"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { Book, BookCollaborator, CollaborationRole, CollaborationScope } from "@/types/book"

const ROLE_OPTIONS: Array<{ value: CollaborationRole; label: string; detail: string }> = [
  { value: "viewer", label: "Viewer", detail: "Read-only access" },
  { value: "commenter", label: "Commenter", detail: "Read and leave notes" },
  { value: "editor", label: "Editor", detail: "Editing partner" },
  { value: "beta_reader", label: "Beta reader", detail: "Reader feedback" },
  { value: "developmental_editor", label: "Developmental editor", detail: "Structure and arc review" },
  { value: "coauthor", label: "Coauthor", detail: "Full creative partner" },
]

const EMPTY_SCOPE: CollaborationScope = {
  chapter_start: 1,
  chapter_end: 10,
  character_bible: true,
  continuity_report: true,
  reader_confusion_report: true,
}

function roleLabel(role: string) {
  return ROLE_OPTIONS.find((option) => option.value === role)?.label ?? role.replace(/_/g, " ")
}

function scopeSummary(scope: CollaborationScope) {
  const chapterStart = scope.chapter_start ?? 1
  const chapterEnd = scope.chapter_end ?? "end"
  const extras = [
    scope.character_bible ? "character bible" : null,
    scope.continuity_report ? "continuity report" : null,
    scope.reader_confusion_report ? "reader confusion report" : null,
  ].filter(Boolean)
  return [`Chapters ${chapterStart}-${chapterEnd}`, ...extras].join(" / ")
}

export default function CollaborationPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const [book, setBook] = useState<Book | null>(null)
  const [collaborators, setCollaborators] = useState<BookCollaborator[]>([])
  const [email, setEmail] = useState("")
  const [displayName, setDisplayName] = useState("")
  const [role, setRole] = useState<CollaborationRole>("beta_reader")
  const [scope, setScope] = useState<CollaborationScope>(EMPTY_SCOPE)
  const [status, setStatus] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let active = true
    Promise.all([
      booksApi.get(bookId),
      booksApi.listCollaborators(bookId).catch(() => []),
    ]).then(([bookValue, collaboratorValue]) => {
      if (!active) return
      setBook(bookValue)
      setCollaborators(collaboratorValue)
    })
    return () => {
      active = false
    }
  }, [bookId])

  const sortedCollaborators = useMemo(
    () => [...collaborators].sort((left, right) => left.email.localeCompare(right.email)),
    [collaborators]
  )

  const updateScope = (patch: Partial<CollaborationScope>) => {
    setScope((current) => ({ ...current, ...patch }))
  }

  const submit = async () => {
    if (!email.trim()) return
    setSaving(true)
    setStatus(null)
    try {
      const created = await booksApi.createCollaborator(bookId, {
        email,
        displayName: displayName || null,
        role,
        scope,
      })
      setCollaborators((current) => [created, ...current.filter((item) => item.id !== created.id)])
      setEmail("")
      setDisplayName("")
      setStatus("Share saved.")
    } catch {
      setStatus("Could not save this share.")
    } finally {
      setSaving(false)
    }
  }

  const revoke = async (collaborator: BookCollaborator) => {
    setStatus(null)
    try {
      const updated = await booksApi.updateCollaborator(bookId, collaborator.id, { inviteStatus: "revoked" })
      setCollaborators((current) => current.map((item) => (item.id === updated.id ? updated : item)))
      setStatus("Share revoked.")
    } catch {
      setStatus("Could not revoke this share.")
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
            title="Author workspace"
            description="Invite readers and editors into scoped parts of the story."
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
                <p className={`mt-2 max-w-2xl text-sm leading-6 ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                  Scope each invite to exact chapters and story intelligence surfaces before sending the draft out.
                </p>
              </div>
              {status ? <p className={`text-sm font-semibold ${status.includes("Could") ? "text-rose-400" : "text-emerald-400"}`}>{status}</p> : null}
            </div>
          </section>

          <section className="grid gap-5 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
            <div className={`rounded-md border p-5 ${isDark ? "border-white/[0.065] bg-[#0d141c]" : "border-slate-200/70 bg-white"}`}>
              <h2 className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Invite collaborator</h2>
              <div className="mt-5 grid gap-3">
                <input
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="reader@example.com"
                  className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 placeholder:text-slate-600 focus:border-violet-400" : "border-slate-200 bg-white text-slate-900 placeholder:text-slate-400 focus:border-violet-400"}`}
                />
                <input
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  placeholder="Display name"
                  className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 placeholder:text-slate-600 focus:border-violet-400" : "border-slate-200 bg-white text-slate-900 placeholder:text-slate-400 focus:border-violet-400"}`}
                />
                <select
                  value={role}
                  onChange={(event) => setRole(event.target.value as CollaborationRole)}
                  className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-violet-400" : "border-slate-200 bg-white text-slate-900 focus:border-violet-400"}`}
                >
                  {ROLE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                <label className="text-xs font-semibold">
                  <span className={isDark ? "text-slate-400" : "text-slate-500"}>From chapter</span>
                  <input
                    type="number"
                    min="1"
                    value={scope.chapter_start ?? ""}
                    onChange={(event) => updateScope({ chapter_start: event.target.value ? Number(event.target.value) : null })}
                    className={`mt-2 h-11 w-full rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-violet-400" : "border-slate-200 bg-white text-slate-900 focus:border-violet-400"}`}
                  />
                </label>
                <label className="text-xs font-semibold">
                  <span className={isDark ? "text-slate-400" : "text-slate-500"}>Through chapter</span>
                  <input
                    type="number"
                    min="1"
                    value={scope.chapter_end ?? ""}
                    onChange={(event) => updateScope({ chapter_end: event.target.value ? Number(event.target.value) : null })}
                    className={`mt-2 h-11 w-full rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-violet-400" : "border-slate-200 bg-white text-slate-900 focus:border-violet-400"}`}
                  />
                </label>
              </div>

              <div className="mt-5 grid gap-2">
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

              <button
                onClick={() => void submit()}
                disabled={saving || !email.trim()}
                className={`mt-5 inline-flex h-11 w-full items-center justify-center rounded-md px-4 text-sm font-semibold transition ${isDark ? "bg-violet-500 text-white hover:bg-violet-400 disabled:bg-violet-500/40" : "bg-violet-600 text-white hover:bg-violet-500 disabled:bg-violet-300"}`}
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
                      <p className={isDark ? "text-slate-300" : "text-slate-700"}>{roleLabel(collaborator.role)}</p>
                      <p className={isDark ? "text-slate-500" : "text-slate-500"}>{scopeSummary(collaborator.scope)}</p>
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
        </main>
      </div>
    </div>
  )
}
