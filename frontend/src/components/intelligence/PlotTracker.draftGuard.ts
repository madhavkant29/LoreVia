import { useEffect, useRef } from "react"

export function usePlotThreadDraftGuard(dirty: boolean, busy: boolean) {
  const current = useRef({ dirty, busy })
  current.current = { dirty, busy }
  const canLeave = useRef(() => !current.current.busy && (!current.current.dirty || window.confirm("Discard the unsaved plot thread changes?"))).current
  useEffect(() => {
    const unload = (event: BeforeUnloadEvent) => { if (current.current.dirty || current.current.busy) { event.preventDefault(); event.returnValue = "" } }
    const navigate = (event: MouseEvent) => {
      if (event.target instanceof Element && event.target.closest("a[href]") && !canLeave()) { event.preventDefault(); event.stopPropagation() }
    }
    window.addEventListener("beforeunload", unload)
    document.addEventListener("click", navigate, true)
    return () => { window.removeEventListener("beforeunload", unload); document.removeEventListener("click", navigate, true) }
  }, [canLeave])
  return canLeave
}
