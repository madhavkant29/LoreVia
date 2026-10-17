import { useCallback, useEffect, useRef, useState } from "react"

export function useSettingsResource<T>(account: string | undefined, load: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null)
  const [owner, setOwner] = useState<string | undefined>(undefined)
  const [loading, setLoading] = useState(false)
  const [failed, setFailed] = useState(false)
  const [version, setVersion] = useState(0)
  useEffect(() => {
    if (!account) return
    let cancelled = false
    setLoading(true); setFailed(false)
    void load().then((value) => { if (!cancelled) { setOwner(account); setData(value) } }).catch(() => { if (!cancelled) setFailed(true) }).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [account, load, version])
  return { data: owner === account ? data : null, setData, loading, failed, retry: () => setVersion((value) => value + 1) }
}

export function useSettingsDraftGuard(dirty: boolean, busy: boolean) {
  const state = useRef({ dirty, busy })
  const bypass = useRef(false)
  state.current = { dirty, busy }
  const allowLeave = useCallback(() => {
    if (state.current.busy) return false
    if (state.current.dirty && !window.confirm("Leave settings and discard your unsaved username and daily goal?")) return false
    bypass.current = true
    return true
  }, [])
  useEffect(() => {
    const unload = (event: BeforeUnloadEvent) => { if (!bypass.current && (state.current.dirty || state.current.busy)) { event.preventDefault(); event.returnValue = "" } }
    const click = (event: MouseEvent) => {
      const anchor = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>("a[href]") : null
      const href = anchor?.getAttribute("href") ?? ""
      if (!anchor || anchor.target === "_blank" || anchor.hasAttribute("download") || href.startsWith("#") || href.startsWith("mailto:")) return
      if (!allowLeave()) { event.preventDefault(); event.stopPropagation() }
    }
    window.addEventListener("beforeunload", unload); document.addEventListener("click", click, true)
    return () => { window.removeEventListener("beforeunload", unload); document.removeEventListener("click", click, true) }
  }, [allowLeave])
  useEffect(() => { bypass.current = false }, [dirty, busy])
  return allowLeave
}
