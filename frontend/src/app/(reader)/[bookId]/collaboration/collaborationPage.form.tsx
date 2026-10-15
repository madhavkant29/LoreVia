"use client"

import { useEffect, useRef, type Dispatch, type SetStateAction } from "react"
import type { CollaborationRole } from "@/types/book"
import { applyCollaboratorRole, collaboratorPayload, permissionSummary, scopeSummary, PERMISSION_OPTIONS, ROLE_OPTIONS, type CollaboratorDraft } from "./collaborationPage.helpers"

export function CollaborationForm({ draft, setDraft, busy, canSave, error, onSave, onClose }: {
  draft: CollaboratorDraft
  setDraft: Dispatch<SetStateAction<CollaboratorDraft | null>>
  busy: boolean
  canSave: boolean
  error: string | null
  onSave: () => Promise<void>
  onClose: () => Promise<boolean>
}) {
  const firstField = useRef<HTMLInputElement>(null)
  useEffect(() => { firstField.current?.focus(); firstField.current?.scrollIntoView({ block: "center", behavior: "smooth" }) }, [draft.id])
  const patch = (values: Partial<CollaboratorDraft>) => setDraft(current => current ? { ...current, ...values } : current)
  const payload = collaboratorPayload(draft)
  return <form aria-labelledby="access-editor-heading" noValidate className="collaboration-form mt-6 border-y py-6" onSubmit={event => { event.preventDefault(); void onSave() }}>
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0"><h2 id="access-editor-heading" className="text-xl font-semibold">{draft.restoring ? "Restore collaborator access" : draft.id ? "Edit collaborator access" : "Grant collaborator access"}</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-[rgb(var(--muted-foreground))]">Access is tied to this email address. The collaborator signs in to LoreVia with the same address. Saving applies access immediately.</p></div>
      <button type="button" disabled={busy} onClick={() => void onClose()} className="app-button-secondary">Cancel</button>
    </div>
    <fieldset disabled={busy} className="mt-5 space-y-6">
      <legend className="sr-only">Collaborator access details</legend>
      <div className="grid gap-4 md:grid-cols-2">
        <label className="grid gap-2 text-sm" htmlFor="collaborator-email">Email<input ref={firstField} id="collaborator-email" type="email" autoComplete="email" readOnly={Boolean(draft.id)} value={draft.email} onChange={event => patch({ email: event.target.value })} aria-describedby="access-editor-error" className="app-input" /></label>
        <label className="grid gap-2 text-sm" htmlFor="collaborator-display-name">Display name · Optional<input id="collaborator-display-name" autoComplete="name" value={draft.displayName} onChange={event => patch({ displayName: event.target.value })} className="app-input" /></label>
        <label className="grid gap-2 text-sm" htmlFor="collaborator-role">Role<select id="collaborator-role" value={draft.role} onChange={event => setDraft(applyCollaboratorRole(draft, event.target.value as CollaborationRole))} className="app-input">{ROLE_OPTIONS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
        <div className="self-end text-sm leading-6 text-[rgb(var(--muted-foreground))]"><p>{ROLE_OPTIONS.find(option => option.value === draft.role)?.detail}</p><p>Changing the role applies its permission preset. Customize it below.</p></div>
      </div>
      <fieldset className="border-y py-5">
        <legend className="px-1 text-base font-semibold">Chapter access</legend>
        <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={draft.permissions.can_view_selected_chapters_only} onChange={event => patch({ permissions: { ...draft.permissions, can_view_selected_chapters_only: event.target.checked } })} />Limit to selected chapters</label>
        {draft.permissions.can_view_selected_chapters_only ? <><div className="mt-3 grid gap-4 sm:grid-cols-2">
          <label className="grid gap-2 text-sm" htmlFor="collaborator-start-chapter">From chapter<input id="collaborator-start-chapter" inputMode="numeric" value={draft.from} onChange={event => patch({ from: event.target.value })} className="app-input" aria-describedby="chapter-range-help" /></label>
          <label className="grid gap-2 text-sm" htmlFor="collaborator-end-chapter">Through chapter<input id="collaborator-end-chapter" inputMode="numeric" value={draft.through} onChange={event => patch({ through: event.target.value })} className="app-input" aria-describedby="chapter-range-help" /></label>
        </div><p id="chapter-range-help" className="mt-3 text-sm leading-6 text-[rgb(var(--muted-foreground))]">An empty start means the first chapter. An empty end includes all later chapters, including chapters added in the future.</p></> : <p className="text-sm leading-6 text-[rgb(var(--muted-foreground))]">All current and future chapters are included.</p>}
      </fieldset>
      <details>
        <summary className="min-h-11 cursor-pointer text-sm font-semibold">Advanced permissions and scope</summary>
        <div className="mt-3 grid gap-6 lg:grid-cols-2">
          <fieldset><legend className="text-sm font-semibold">Permissions</legend><div className="mt-2 divide-y">
            {PERMISSION_OPTIONS.filter(option => option.key !== "can_view_selected_chapters_only").map(option => <label key={option.key} className="flex min-h-11 items-center justify-between gap-4 py-2 text-sm"><span>{option.label}</span><input type="checkbox" checked={draft.permissions[option.key]} onChange={event => patch({ permissions: { ...draft.permissions, [option.key]: event.target.checked } })} /></label>)}
          </div></fieldset>
          <fieldset><legend className="text-sm font-semibold">Shared story resources</legend><p className="mt-2 text-sm leading-6 text-[rgb(var(--muted-foreground))]">Story bible permission enables the character bible. Review-tool permission enables the reports selected here.</p>
            {([{ key: "character_bible", label: "Character bible", enabled: draft.permissions.can_view_story_bible }, { key: "continuity_report", label: "Continuity report", enabled: draft.permissions.can_run_ai_scans }, { key: "reader_confusion_report", label: "Reader confusion report", enabled: draft.permissions.can_run_ai_scans }] as const).map(option => <label key={option.key} className="flex min-h-11 items-center justify-between gap-4 py-2 text-sm"><span>{option.label}</span><input type="checkbox" disabled={!option.enabled} checked={option.enabled && draft.scope[option.key]} onChange={event => patch({ scope: { ...draft.scope, [option.key]: event.target.checked } })} /></label>)}
          </fieldset>
        </div>
      </details>
      <div className="border-l-2 border-[rgb(var(--accent))] pl-4 text-sm leading-6"><p className="font-semibold">Access to be applied</p><p>{permissionSummary(payload.permissions)}</p><p>{scopeSummary(payload.scope, payload.permissions)}</p></div>
      {error ? <p id="access-editor-error" role="alert" className="text-sm leading-6 text-[rgb(var(--destructive))]">{error}</p> : <span id="access-editor-error" />}
      {!canSave ? <p className="text-sm leading-6">Load or refresh the people list before saving so existing access can be checked.</p> : null}
      <div className="flex flex-wrap justify-end gap-3"><button type="button" className="app-button-secondary" onClick={() => void onClose()}>Cancel</button><button type="submit" disabled={!canSave} className="app-button-primary">{busy ? "Saving…" : draft.restoring ? "Restore access" : draft.id ? "Save access changes" : "Grant access"}</button></div>
    </fieldset>
  </form>
}
