import { useEffect, useRef } from "react"
import { useRouter } from "next/navigation"
import type { Route } from "next"
import type { Character } from "@/types/character"
import type { ConfirmDialogConfig } from "@/types/ux"
import { buildCreateDraft, buildDraft, type CreateDraft, type EditDraft } from "./charactersPage.helpers"

export function useCharacterDraftProtection({ editing, creating, draft, createDraft, character, busy, confirm, onDiscard, initialChapter = 1 }: {
  editing: boolean
  creating: boolean
  draft: EditDraft
  createDraft: CreateDraft
  character: Character | null
  busy: boolean
  initialChapter?: number
  confirm: (config: ConfirmDialogConfig) => Promise<boolean>
  onDiscard: () => void
}) {
  const router = useRouter()
  const dirty = editing && JSON.stringify(draft) !== JSON.stringify(buildDraft(character))
    || creating && JSON.stringify(createDraft) !== JSON.stringify(buildCreateDraft(initialChapter))
  const dirtyRef = useRef(dirty)
  dirtyRef.current = dirty
  useEffect(() => {
    function beforeUnload(event: BeforeUnloadEvent) {
      if (!dirtyRef.current) return
      event.preventDefault()
      event.returnValue = ""
    }
    window.addEventListener("beforeunload", beforeUnload)
    return () => window.removeEventListener("beforeunload", beforeUnload)
  }, [])

  useEffect(() => {
    function guardLink(event: MouseEvent) {
      if (!dirtyRef.current || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
      const link = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>("a[href]") : null
      if (!link || link.target === "_blank" || link.hasAttribute("download") || link.getAttribute("href")?.startsWith("#")) return
      const destination = new URL(link.href, window.location.href)
      if (destination.href === window.location.href || destination.origin !== window.location.origin) return
      event.preventDefault()
      event.stopPropagation()
      if (busy) return
      void confirm({ title: "Leave with unsaved character changes?", body: "Save your profile before leaving to keep these edits.", confirmLabel: "Discard and leave", cancelLabel: "Keep editing", tone: "danger" }).then((leave) => {
        if (leave) {
          onDiscard()
          router.push(`${destination.pathname}${destination.search}${destination.hash}` as Route)
        }
      })
    }
    document.addEventListener("click", guardLink, true)
    return () => document.removeEventListener("click", guardLink, true)
  }, [busy, confirm, onDiscard, router])

  return async (action: () => void) => {
    if (busy) return false
    if (dirty && !await confirm({ title: "Discard character changes?", body: "Your unsaved profile changes will be lost.", confirmLabel: "Discard changes", tone: "danger" })) return false
    onDiscard()
    action()
    return true
  }
}
