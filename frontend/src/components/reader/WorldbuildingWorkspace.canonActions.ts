import { useRef, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { worldBuildingApi } from "@/lib/api/worldBuilding"
import { getApiErrorDetail } from "@/lib/utils/apiErrors"
import type { CanonOverride, WorldIntegrationResult, WorldQueryResponse } from "@/types/world-building"

export function useWorldbuildingCanonActions(bookId: string, setStatusMessage: (message: string | null) => void, onCanonSaved: () => void) {
  const client = useQueryClient()
  const lock = useRef(false)
  const revision = useRef(0)
  const [integration, setIntegration] = useState<WorldIntegrationResult | null>(null)
  const [loadingIntegration, setLoadingIntegration] = useState(false)
  const [canonName, setCanonName] = useState("")
  const [canonAliases, setCanonAliases] = useState("")
  const [savingCanon, setSavingCanon] = useState(false)
  const [wikiGenerating, setWikiGenerating] = useState(false)
  const [logicQuery, setLogicQuery] = useState("")
  const [logicResult, setLogicResult] = useState<WorldQueryResponse | null>(null)
  const [logicLoading, setLogicLoading] = useState(false)
  const [submittedQuery, setSubmittedQuery] = useState("")
  const [logicStale, setLogicStale] = useState(false)

  function markSourcesChanged() {
    revision.current++
    setIntegration((current) => current ? { ...current, is_stale: true } : null)
    setLogicStale(true)
  }

  async function runIntegration() {
    if (lock.current) return
    lock.current = true; setLoadingIntegration(true); setStatusMessage(null)
    const version = revision.current
    try {
      const payload = await worldBuildingApi.getIntegration(bookId)
      setIntegration({ ...payload, is_stale: payload.is_stale || version !== revision.current })
    } catch (error) { setStatusMessage(`${getApiErrorDetail(error) ?? "Could not refresh opportunities."} The previous result is retained. Try again.`) }
    finally { lock.current = false; setLoadingIntegration(false) }
  }

  async function saveCanonOverride() {
    if (lock.current || !canonName.trim()) return
    lock.current = true; setSavingCanon(true); setStatusMessage(null)
    try {
      const saved = await worldBuildingApi.saveCanonOverride(bookId, { canonical_name: canonName.trim(), aliases: [...new Set(canonAliases.split(",").map((item) => item.trim()).filter(Boolean))] })
      client.setQueryData<CanonOverride[]>([`worldbuilding:${bookId}:canon-overrides`], (current = []) => [saved, ...current.filter((item) => item.id !== saved.id)])
      setCanonName(""); setCanonAliases(""); markSourcesChanged()
      onCanonSaved()
      setStatusMessage(`Saved canon override for ${saved.canonical_name}. Refresh the comparison after canon changes.`)
    } catch (error) { setStatusMessage(`${getApiErrorDetail(error) ?? "Could not confirm the canon override save."} Your entries are retained. Refresh aliases before retrying.`) }
    finally { lock.current = false; setSavingCanon(false) }
  }

  async function generateWiki() {
    if (lock.current) return
    lock.current = true; setWikiGenerating(true); setStatusMessage(null)
    try {
      const payload = await worldBuildingApi.generateWiki(bookId)
      if (payload.entries) client.setQueryData([`worldbuilding:${bookId}:wiki`], payload.entries)
      setStatusMessage(`Generated or refreshed ${payload.generated_count} wiki entries from the manuscript.`)
    } catch (error) { setStatusMessage(`${getApiErrorDetail(error) ?? "Could not confirm wiki generation."} Existing entries are retained. Refresh the wiki before trying again.`) }
    finally { lock.current = false; setWikiGenerating(false) }
  }

  async function runLogicQuery(mode = "story_integration") {
    if (lock.current || !logicQuery.trim()) return
    lock.current = true; setLogicLoading(true); setStatusMessage(null)
    const query = logicQuery.trim(); const version = revision.current
    try {
      const payload = await worldBuildingApi.query(bookId, { query, mode })
      setLogicResult(payload); setSubmittedQuery(query); setLogicStale(version !== revision.current)
      setStatusMessage("Canon query complete. Review the answer and its source evidence below.")
    } catch (error) { setStatusMessage(`${getApiErrorDetail(error) ?? "Could not complete the canon query."} Your question and any previous answer are retained. Try again.`) }
    finally { lock.current = false; setLogicLoading(false) }
  }

  return { integration, setIntegration, loadingIntegration, canonName, setCanonName, canonAliases, setCanonAliases, savingCanon, wikiGenerating, logicQuery, setLogicQuery, logicResult, logicLoading, submittedQuery, logicStale,
    busy: loadingIntegration || savingCanon || wikiGenerating || logicLoading, markSourcesChanged, runIntegration, saveCanonOverride, generateWiki, runLogicQuery }
}
