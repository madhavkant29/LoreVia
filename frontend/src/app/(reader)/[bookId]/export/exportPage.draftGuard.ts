import { useEffect, useRef } from "react"

export function useExportDraftGuard(dirty: boolean, busy: boolean) {
  const latest = useRef({ dirty, busy })
  latest.current = { dirty, busy }
  useEffect(() => {
    const unload = (event: BeforeUnloadEvent) => { if (latest.current.dirty || latest.current.busy) { event.preventDefault(); event.returnValue = "" } }
    const navigate = (event: MouseEvent) => {
      const anchor = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>("a[href]") : null
      if (!anchor || anchor.download || anchor.target === "_blank" || anchor.getAttribute("href")?.startsWith("#")) return
      if (latest.current.busy || (latest.current.dirty && !window.confirm("Leave this page and discard unsaved publishing details, vault edits, or selected files?"))) { event.preventDefault(); event.stopPropagation() }
    }
    window.addEventListener("beforeunload", unload)
    document.addEventListener("click", navigate, true)
    return () => { window.removeEventListener("beforeunload", unload); document.removeEventListener("click", navigate, true) }
  }, [])
}
