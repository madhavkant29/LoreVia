import type { BookCollaborator, CollaborationPermissions, CollaborationRole, CollaborationScope } from "@/types/book"

export const ROLE_OPTIONS: Array<{ value: CollaborationRole; label: string; detail: string }> = [
  { value: "viewer", label: "Viewer", detail: "Read-only access to selected chapters." },
  { value: "reader_only", label: "Reader-only", detail: "Read-only access without comments." },
  { value: "commenter", label: "Commenter", detail: "Can read and leave notes without editing." },
  { value: "beta_reader", label: "Beta reader", detail: "Scoped reading and feedback access." },
  { value: "editor", label: "Editor", detail: "Can edit the manuscript and review story data." },
  { value: "developmental_editor", label: "Developmental editor", detail: "Can edit structure, continuity, and story arcs." },
  { value: "coauthor", label: "Coauthor", detail: "Full creative access across the manuscript." },
  { value: "co_writer", label: "Co-writer", detail: "Full drafting access across the manuscript." },
]

export const ROLE_PRESETS: Record<CollaborationRole, CollaborationPermissions> = {
  viewer: readPermissions(false),
  reader_only: readPermissions(false),
  commenter: readPermissions(true),
  beta_reader: readPermissions(true),
  editor: editPermissions(),
  developmental_editor: editPermissions(),
  coauthor: editPermissions(),
  co_writer: editPermissions(),
}

export const PERMISSION_OPTIONS: Array<{ key: keyof CollaborationPermissions; label: string }> = [
  { key: "can_edit_manuscript", label: "Edit manuscript" },
  { key: "can_view_story_bible", label: "View story bible" },
  { key: "can_run_ai_scans", label: "Run review tools" },
  { key: "can_export", label: "Export files" },
  { key: "can_comment", label: "Leave comments" },
  { key: "can_view_selected_chapters_only", label: "Limit to selected chapters" },
]

export const DEFAULT_SCOPE: CollaborationScope = {
  chapter_start: 1,
  chapter_end: null,
  character_bible: false,
  continuity_report: false,
  reader_confusion_report: false,
}

function readPermissions(canComment: boolean): CollaborationPermissions {
  return {
    can_edit_manuscript: false,
    can_view_story_bible: false,
    can_run_ai_scans: false,
    can_export: false,
    can_comment: canComment,
    can_view_selected_chapters_only: true,
  }
}

function editPermissions(): CollaborationPermissions {
  return {
    can_edit_manuscript: true,
    can_view_story_bible: true,
    can_run_ai_scans: true,
    can_export: true,
    can_comment: true,
    can_view_selected_chapters_only: false,
  }
}

export function roleLabel(role: CollaborationRole | string) {
  return ROLE_OPTIONS.find((option) => option.value === role)?.label ?? role.replaceAll("_", " ")
}

export function permissionSummary(permissions: CollaborationPermissions) {
  const labels = [
    permissions.can_edit_manuscript ? "Edit" : null,
    permissions.can_view_story_bible ? "Story bible" : null,
    permissions.can_run_ai_scans ? "Reviews" : null,
    permissions.can_export ? "Export" : null,
    permissions.can_comment ? "Comments" : null,
  ].filter(Boolean)
  return labels.length ? labels.join(" · ") : "Read only"
}

export function scopeSummary(scope: CollaborationScope, permissions: CollaborationPermissions) {
  if (!permissions.can_view_selected_chapters_only) return "All chapters"
  const start = scope.chapter_start ?? 1
  const end = scope.chapter_end
  if (!Number.isSafeInteger(start) || start < 1 || (end != null && (!Number.isSafeInteger(end) || end < start))) return "Enter a valid chapter range"
  return `Chapters ${scope.chapter_start ?? 1}–${scope.chapter_end ?? "end"}`
}

export type CollaboratorDraft = {
  id: string | null
  restoring: boolean
  email: string
  displayName: string
  role: CollaborationRole
  permissions: CollaborationPermissions
  scope: CollaborationScope
  from: string
  through: string
}

export function collaboratorDraft(person?: BookCollaborator): CollaboratorDraft {
  return {
    id: person?.id ?? null,
    restoring: person?.invite_status === "revoked",
    email: person?.email ?? "",
    displayName: person?.display_name ?? "",
    role: person?.role ?? "commenter",
    permissions: { ...(person?.permissions ?? ROLE_PRESETS.commenter) },
    scope: { ...(person?.scope ?? DEFAULT_SCOPE) },
    from: String(person?.scope.chapter_start ?? 1),
    through: person?.scope.chapter_end == null ? "" : String(person.scope.chapter_end),
  }
}

export function applyCollaboratorRole(draft: CollaboratorDraft, role: CollaborationRole): CollaboratorDraft {
  const permissions = { ...ROLE_PRESETS[role] }
  return { ...draft, role, permissions, scope: { ...draft.scope,
    character_bible: permissions.can_view_story_bible,
    continuity_report: permissions.can_run_ai_scans,
    reader_confusion_report: permissions.can_run_ai_scans,
  } }
}

export function validateCollaboratorDraft(draft: CollaboratorDraft, people: BookCollaborator[]): string | null {
  const email = draft.email.trim()
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length > 320) return "Enter a valid email address of no more than 320 characters."
  if (draft.displayName.trim().length > 120) return "Keep the display name within 120 characters."
  if (people.some(person => person.id !== draft.id && person.email.toLowerCase() === email.toLowerCase())) return "This email is already listed. Edit or restore that person’s existing access."
  if (draft.permissions.can_view_selected_chapters_only) {
    for (const value of [draft.from, draft.through]) {
      if (value.trim() && (!/^\d+$/.test(value.trim()) || !Number.isSafeInteger(Number(value)) || Number(value) < 1)) return "Chapter boundaries must be positive whole numbers."
    }
    if (draft.through.trim() && Number(draft.through) < Number(draft.from.trim() || 1)) return "Through chapter must be the same as or later than From chapter."
  }
  return null
}

export function collaboratorPayload(draft: CollaboratorDraft) {
  const limited = draft.permissions.can_view_selected_chapters_only
  return { email: draft.email.trim().toLowerCase(), displayName: draft.displayName.trim() || null, role: draft.role,
    permissions: { ...draft.permissions },
    scope: { ...draft.scope,
      chapter_start: limited && draft.from.trim() ? Number(draft.from) : null,
      chapter_end: limited && draft.through.trim() ? Number(draft.through) : null,
      character_bible: draft.permissions.can_view_story_bible && draft.scope.character_bible,
      continuity_report: draft.permissions.can_run_ai_scans && draft.scope.continuity_report,
      reader_confusion_report: draft.permissions.can_run_ai_scans && draft.scope.reader_confusion_report,
    } }
}

export function collaboratorMatches(person: BookCollaborator, query: string, filter: string): boolean {
  return (filter === "all" || person.invite_status === filter)
    && `${person.display_name ?? ""} ${person.email} ${roleLabel(person.role)}`.toLowerCase().includes(query.trim().toLowerCase())
}

export function collaborationDate(value: string | null | undefined): string {
  if (!value || !Number.isFinite(Date.parse(value))) return "Date unavailable"
  return new Date(value).toLocaleString()
}


