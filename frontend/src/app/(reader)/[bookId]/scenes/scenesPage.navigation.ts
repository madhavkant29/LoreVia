import { useEffect, type RefObject } from "react"
import { useRouter } from "next/navigation"
import type { Route } from "next"
import type { useConfirmDialog } from "@/components/ui/ConfirmDialog"

export function useSceneNavigationGuard(dirtyRef: RefObject<boolean>, confirm: ReturnType<typeof useConfirmDialog>) {
  const router = useRouter()
  useEffect(() => {
    const warnBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!dirtyRef.current) return
      event.preventDefault()
      event.returnValue = ""
    }
    window.addEventListener("beforeunload", warnBeforeUnload)
    return () => window.removeEventListener("beforeunload", warnBeforeUnload)
  }, [dirtyRef])

  useEffect(() => {
    const guardNavigation = (event: MouseEvent) => {
      if (!dirtyRef.current || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
      const link = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>("a[href]") : null
      if (!link || link.target === "_blank" || link.hasAttribute("download") || link.getAttribute("href")?.startsWith("#")) return
      const destination = new URL(link.href, window.location.href)
      if (destination.href === window.location.href || destination.origin !== window.location.origin) return
      event.preventDefault()
      event.stopPropagation()
      void confirm({ title: "Leave with unsaved scene changes?", body: "Save your scene before leaving to keep these edits.", confirmLabel: "Discard and leave", cancelLabel: "Keep editing", tone: "danger" }).then((leave) => {
        if (leave) router.push(`${destination.pathname}${destination.search}${destination.hash}` as Route)
      })
    }
    document.addEventListener("click", guardNavigation, true)
    return () => document.removeEventListener("click", guardNavigation, true)
  }, [confirm, dirtyRef, router])

}
