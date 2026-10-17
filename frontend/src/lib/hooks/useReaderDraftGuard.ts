import { useEffect, useRef } from "react"

export function useReaderDraftGuard(dirty: boolean, busy: boolean) {
  const state = useRef({ dirty, busy })
  state.current = { dirty, busy }
  const canLeave = useRef(() => !state.current.busy && (!state.current.dirty || window.confirm("Discard the unsaved reading notes?"))).current
  useEffect(() => {
    const unload = (event: BeforeUnloadEvent) => {
      if (state.current.dirty || state.current.busy) { event.preventDefault(); event.returnValue = "" }
    }
    const navigate = (event: MouseEvent) => {
      if (!(event.target instanceof Element)) return
      const link = event.target.closest<HTMLAnchorElement>("a[href]")
      if (!link || link.target === "_blank" || event.ctrlKey || event.metaKey || event.shiftKey || link.href === window.location.href) return
      if (!canLeave()) { event.preventDefault(); event.stopPropagation() }
    }
    window.addEventListener("beforeunload", unload)
    document.addEventListener("click", navigate, true)
    return () => { window.removeEventListener("beforeunload", unload); document.removeEventListener("click", navigate, true) }
  }, [canLeave])
  return canLeave
}
