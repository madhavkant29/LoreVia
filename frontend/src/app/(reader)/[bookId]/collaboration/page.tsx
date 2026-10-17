"use client"

import Link from "next/link"
import { useParams } from "next/navigation"
import { useRef } from "react"
import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"
import { useCollaborationPage } from "./collaborationPage.state"
import { CollaborationForm } from "./collaborationPage.form"
import { CollaborationActivity } from "./collaborationPage.activity"
import { permissionSummary, roleLabel, scopeSummary } from "./collaborationPage.helpers"

export default function CollaborationPage() {
  const { bookId } = useParams<{ bookId: string }>()
  return <CollaborationWorkspace key={bookId} bookId={bookId} />
}

function CollaborationWorkspace({ bookId }: { bookId: string }) {
  const state = useCollaborationPage(bookId)
  const activityTrigger = useRef<HTMLButtonElement | null>(null)
  const inviteTrigger = useRef<HTMLButtonElement | null>(null)
  const { bookQuery, peopleQuery, people, draft } = state
  const book = bookQuery.data
  const closeDraft = async () => {
    const closed = await state.closeDraft()
    if (closed) inviteTrigger.current?.focus()
    return closed
  }
  if (bookQuery.isLoading) return <div className="p-6" role="status">Loading collaboration workspace…</div>
  if (!book || bookQuery.isError) return <div className="p-6"><h1 className="text-2xl font-semibold">Collaborators</h1><p role="alert" className="my-4">Could not load this project.</p><button className="app-button-secondary" disabled={bookQuery.isFetching} onClick={() => void bookQuery.refetch()}>Retry project</button></div>
  if (!state.owner) return <div className="p-6"><h1 className="text-2xl font-semibold">Collaborators</h1><p className="my-4">Only the project owner can manage collaborator access.</p><Link className="app-button-secondary" href={`/${bookId}`}>Return to project</Link></div>
  if (!state.paid) return <div className="p-6"><h1 className="text-2xl font-semibold">Collaborators</h1><p className="my-4">Managing collaborators requires an Author or Architect plan.</p><Link className="app-button-secondary" href="/upgrade">View plans</Link></div>
  const active = people.filter(person => person.invite_status === "active").length
  return <main data-collaboration-workspace className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
    <WorkspaceFamilyHeader active="collaboration" bookId={bookId} family="publish-export" title="Collaborators" description={`Manage who can read, comment on, and edit ${book.title}. Review each person’s chapter and story access before saving.`} actions={<><Link className="app-button-secondary" href={`/${bookId}/beta-feedback`}>Beta reader assignments</Link><button type="button" className="app-button-secondary" onClick={() => window.dispatchEvent(new CustomEvent(SUPPORT_HELP_EVENT))}>Help</button></>} />
    <div className="mt-6 flex flex-wrap items-start justify-between gap-4">
      <div><h2 className="text-xl font-semibold">People with access</h2>{peopleQuery.data ? <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">{active} active · {people.length - active} revoked</p> : null}</div>
      <div className="flex flex-wrap gap-2"><button className="app-button-secondary" disabled={state.busy || peopleQuery.isFetching} onClick={() => void peopleQuery.refetch()}>{peopleQuery.isFetching ? "Refreshing…" : "Refresh people"}</button><button ref={inviteTrigger} className="app-button-primary" disabled={state.busy || !peopleQuery.data || peopleQuery.isError} onClick={() => void state.openDraft()}>Invite collaborator</button></div>
    </div>
    {state.status ? <p role="status" className="mt-4 border-l-2 border-[rgb(var(--accent))] pl-3 text-sm leading-6">{state.status}</p> : null}
    {state.error && !draft ? <p role="alert" className="mt-4 text-sm leading-6">{state.error}</p> : null}
    {peopleQuery.isLoading ? <p role="status" className="py-8 text-sm">Loading people and access…</p> : null}
    {peopleQuery.isError ? <div role="alert" className="my-5 border-y py-4 text-sm leading-6"><p>Could not refresh the people list.{peopleQuery.data ? " The last loaded access is shown below." : " Access details are unavailable."}</p><button className="app-button-secondary mt-3" disabled={peopleQuery.isFetching} onClick={() => void peopleQuery.refetch()}>Retry people</button></div> : null}
    {draft ? <CollaborationForm draft={draft} setDraft={state.setDraft} busy={state.busy} canSave={Boolean(peopleQuery.data) && !peopleQuery.isError} error={state.error} onSave={state.save} onClose={closeDraft} /> : null}
    {peopleQuery.data ? <>
      {people.length ? <div className="mt-6 grid gap-4 sm:grid-cols-[minmax(0,1fr)_12rem]">
        <label className="grid gap-2 text-sm">Search collaborators<input type="search" className="app-input" placeholder="Name, email, or role" value={state.query} onChange={event => { state.setQuery(event.target.value); state.setLimit(25) }} /></label>
        <label className="grid gap-2 text-sm">Access status<select className="app-input" value={state.filter} onChange={event => { state.setFilter(event.target.value); state.setLimit(25) }}><option value="all">All people</option><option value="active">Active</option><option value="revoked">Revoked</option></select></label>
      </div> : null}
      {!people.length ? <div className="border-y py-8 mt-6"><h3 className="font-semibold">No collaborators yet</h3><p className="mt-2 max-w-2xl text-sm leading-6 text-[rgb(var(--muted-foreground))]">Grant access to an editor, coauthor, or reader using their LoreVia email address. Choose a role and chapter range before saving.</p></div> : !state.filtered.length ? <div className="border-y py-6 mt-6"><p>No collaborators match these filters.</p><button className="app-button-secondary mt-3" onClick={() => { state.setQuery(""); state.setFilter("all") }}>Clear filters</button></div> : <>
        <p role="status" className="mt-5 text-sm text-[rgb(var(--muted-foreground))]">Showing {state.visible.length} of {state.filtered.length} people</p>
        <table className="collaboration-table mt-3 w-full text-left text-sm"><caption className="sr-only">Collaborator roles, access, status, and actions</caption><thead><tr>{["Person", "Role", "Access", "Status", "Actions"].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead><tbody>
          {state.visible.map(person => <tr key={person.id}>
            <th scope="row" data-label="Person"><span className="font-semibold">{person.display_name || person.email}</span>{person.display_name ? <span className="mt-1 block font-normal text-[rgb(var(--muted-foreground))]">{person.email}</span> : null}</th>
            <td data-label="Role">{roleLabel(person.role)}</td>
            <td data-label="Access">{person.invite_status === "revoked" ? <p>No active collaborator access</p> : <><p>{permissionSummary(person.permissions)}</p><p className="mt-1 text-[rgb(var(--muted-foreground))]">{scopeSummary(person.scope, person.permissions)}</p><p className="mt-1 text-[rgb(var(--muted-foreground))]">{[person.permissions.can_view_story_bible && person.scope.character_bible && "Character bible", person.permissions.can_run_ai_scans && person.scope.continuity_report && "Continuity report", person.permissions.can_run_ai_scans && person.scope.reader_confusion_report && "Reader confusion report"].filter(Boolean).join(" · ")}</p></>}</td>
            <td data-label="Status">{person.invite_status === "active" ? "Active" : "Revoked"}</td>
            <td data-label="Actions"><div className="flex flex-wrap gap-2"><button className="app-button-secondary" onClick={event => { activityTrigger.current = event.currentTarget; state.setSelectedId(person.id) }}>View activity</button><button className="app-button-secondary" disabled={state.busy} onClick={() => void state.openDraft(person)}>{person.invite_status === "active" ? "Edit access" : "Restore access"}</button>{person.invite_status === "active" ? <button className="app-button-secondary" disabled={state.busy || Boolean(draft)} onClick={() => void state.revoke(person)}>Revoke</button> : null}</div></td>
          </tr>)}
        </tbody></table>
        {state.visible.length < state.filtered.length ? <button className="app-button-secondary mt-4" onClick={() => state.setLimit(value => value + 25)}>Show more people ({state.filtered.length - state.visible.length} remaining)</button> : null}
      </>}
    </> : null}
    {state.selectedId ? <CollaborationActivity state={state} bookId={bookId} onClose={() => { state.setSelectedId(null); activityTrigger.current?.focus() }} /> : null}
  </main>
}
