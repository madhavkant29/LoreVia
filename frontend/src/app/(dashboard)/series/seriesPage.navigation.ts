import { useEffect, useRef } from "react"

export function useSeriesNavigationGuard(dirty: boolean, busy: boolean) {
  const current = useRef({ dirty, busy })
  current.current = { dirty, busy }
  useEffect(() => {
    const unload = (event: BeforeUnloadEvent) => { if (current.current.dirty || current.current.busy) { event.preventDefault(); event.returnValue = "" } }
    const click = (event: MouseEvent) => {
      const anchor = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>("a[href]") : null
      if (!anchor || anchor.target === "_blank" || anchor.download || anchor.getAttribute("href")?.startsWith("#")) return
      if (current.current.busy || (current.current.dirty && !window.confirm("Leave this page and discard unsaved series forms and the continuity passage?"))) { event.preventDefault(); event.stopPropagation() }
    }
    window.addEventListener("beforeunload", unload); document.addEventListener("click", click, true)
    return () => { window.removeEventListener("beforeunload", unload); document.removeEventListener("click", click, true) }
  }, [])
}
