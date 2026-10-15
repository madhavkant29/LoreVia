"use client"

import { useEffect, useRef, useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { booksApi } from "@/lib/api/books"
import { useBookDetail } from "@/lib/hooks/useBookDetail"
import { useAuthStore } from "@/lib/stores/authStore"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import { useConfirmDialog } from "@/components/ui/ConfirmDialog"
import type { BookCollaborator } from "@/types/book"
import { collaboratorDraft, collaboratorMatches, collaboratorPayload, validateCollaboratorDraft, type CollaboratorDraft } from "./collaborationPage.helpers"

export function useCollaborationPage(bookId: string) {
  const queryClient = useQueryClient()
  const confirm = useConfirmDialog()
  const bookQuery = useBookDetail(bookId)
  const user = useAuthStore(state => state.user)
  const owner = bookQuery.data?.access_class === "owner"
  const paid = canUseAuthorFeatures(user?.tier)
  const canManage = owner && paid
  const peopleKey = asQueryKey(bookCacheKey(bookId, "collaborators"))
  const peopleQuery = useQuery({ queryKey: peopleKey, queryFn: () => booksApi.listCollaborators(bookId), enabled: canManage, retry: false, staleTime: 20_000 })
  const people = peopleQuery.data ?? []
  const [query, setQuery] = useState("")
  const [filter, setFilter] = useState("all")
  const [limit, setLimit] = useState(25)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const selected = people.find(person => person.id === selectedId) ?? null
  const activityQuery = useQuery({ queryKey: asQueryKey(bookCacheKey(bookId, `collaborator-activity:${selectedId ?? "idle"}`)), queryFn: () => booksApi.getCollaboratorActivity(bookId, selectedId!), enabled: canManage && Boolean(selected), retry: false, staleTime: 20_000 })
  const [draft, setDraft] = useState<CollaboratorDraft | null>(null)
  const originalDraft = useRef("")
  const [status, setStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const busyRef = useRef(false)
  const dirty = Boolean(draft && JSON.stringify(draft) !== originalDraft.current)
  const dirtyRef = useRef(dirty)
  dirtyRef.current = dirty
  const filtered = [...people].sort((a, b) => (a.display_name || a.email).localeCompare(b.display_name || b.email)).filter(person => collaboratorMatches(person, query, filter))

  useEffect(() => {
    const unload = (event: BeforeUnloadEvent) => { if (dirtyRef.current || busyRef.current) { event.preventDefault(); event.returnValue = "" } }
    const navigate = (event: MouseEvent) => {
      const link = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>("a[href]") : null
      if (!link || link.target === "_blank" || event.ctrlKey || event.metaKey || event.shiftKey || link.href === window.location.href) return
      if (busyRef.current || (dirtyRef.current && !window.confirm("Discard the unsaved collaborator access changes?"))) { event.preventDefault(); event.stopPropagation() }
    }
    window.addEventListener("beforeunload", unload); document.addEventListener("click", navigate, true)
    return () => { window.removeEventListener("beforeunload", unload); document.removeEventListener("click", navigate, true) }
  }, [])

  const closeDraft = async () => {
    if (busyRef.current) return false
    if (dirtyRef.current && !await confirm({ title: "Discard access changes?", body: "Your unsaved email, role, permissions, and chapter scope will be discarded.", confirmLabel: "Discard changes", cancelLabel: "Keep editing", tone: "danger" })) return false
    setDraft(null); setError(null); return true
  }
  const openDraft = async (person?: BookCollaborator) => {
    if (!canManage || busyRef.current || (draft && !await closeDraft())) return
    const next = collaboratorDraft(person)
    originalDraft.current = JSON.stringify(next); setDraft(next); setError(null); setStatus(null)
  }
  const commitPerson = async (person: BookCollaborator) => {
    await queryClient.cancelQueries({ queryKey: peopleKey })
    queryClient.setQueryData<BookCollaborator[]>(peopleKey, current => [person, ...(current ?? []).filter(row => row.id !== person.id)])
    void queryClient.invalidateQueries({ queryKey: asQueryKey(bookCacheKey(bookId, `collaborator-activity:${person.id}`)) })
  }
  const save = async () => {
    if (!draft || busyRef.current || !canManage || peopleQuery.isError || !peopleQuery.data) return
    const validation = validateCollaboratorDraft(draft, people)
    if (validation) { setError(validation); return }
    busyRef.current = true; setBusy(true); setError(null); setStatus(null)
    try {
      await queryClient.cancelQueries({ queryKey: peopleKey })
      const payload = collaboratorPayload(draft)
      const person = draft.id
        ? await booksApi.updateCollaborator(bookId, draft.id, { ...payload, ...(draft.restoring ? { inviteStatus: "active" as const } : {}) })
        : await booksApi.createCollaborator(bookId, payload)
      await commitPerson(person)
      setDraft(null); setStatus(draft.restoring ? "Access restored." : draft.id ? "Access changes saved." : "Access granted.")
      setQuery(""); setFilter("all"); setLimit(25)
    } catch { setError("Could not confirm the access change. Your draft is still here. Refresh the people list to check the current access before retrying.") }
    finally { busyRef.current = false; setBusy(false) }
  }
  const revoke = async (person: BookCollaborator) => {
    if (!canManage || busyRef.current) return
    const agreed = await confirm({ title: `Revoke access for ${person.display_name || person.email}?`, body: "Their collaborator access to this project will be revoked. Existing comments and activity remain. Review separate beta assignments and public visibility if they also provide access.", confirmLabel: "Revoke access", cancelLabel: "Keep access", tone: "danger" })
    if (!agreed || busyRef.current) return
    busyRef.current = true; setBusy(true); setStatus(null); setError(null)
    try {
      await queryClient.cancelQueries({ queryKey: peopleKey })
      const updated = await booksApi.updateCollaborator(bookId, person.id, { inviteStatus: "revoked" })
      await commitPerson(updated); setStatus("Collaborator access revoked.")
    } catch { setError("Could not confirm that access was revoked. Refresh the people list to check its current state.") }
    finally { busyRef.current = false; setBusy(false) }
  }

  return { bookQuery, owner, paid, canManage, peopleQuery, people, filtered, visible: filtered.slice(0, limit), limit, setLimit,
    query, setQuery, filter, setFilter, selected, selectedId, setSelectedId, activityQuery, draft, setDraft,
    status, error, busy, openDraft, closeDraft, save, revoke }
}
