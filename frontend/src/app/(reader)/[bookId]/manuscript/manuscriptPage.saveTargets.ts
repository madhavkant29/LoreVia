import { useState } from "react"

import type { SaveState } from "@/types/book"
import type { SaveTarget } from "./manuscriptPage.constants"

export function useManuscriptSaveTargets() {
  const [saveStateByTarget, setSaveStateByTarget] = useState<Partial<Record<SaveTarget, SaveState>>>({})
  const [failedSaveByTarget, setFailedSaveByTarget] = useState<Partial<Record<SaveTarget, () => Promise<void>>>>({})

  function setTargetSaveState(target: SaveTarget, state: SaveState) {
    setSaveStateByTarget((current) => ({ ...current, [target]: state }))
  }

  function setTargetRetry(target: SaveTarget, retry: (() => Promise<void>) | null) {
    setFailedSaveByTarget((current) => {
      const next = { ...current }
      if (retry) next[target] = retry
      else delete next[target]
      return next
    })
  }

  return {
    failedSaveByTarget,
    saveStateByTarget,
    setTargetRetry,
    setTargetSaveState,
  }
}
