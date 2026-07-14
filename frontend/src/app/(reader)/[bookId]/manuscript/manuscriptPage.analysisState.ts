import { useState } from "react"

import type { Character } from "@/types/character"
import type { EmotionalArcOverview, ReadabilityMetrics } from "@/types/book"
import type { ManuscriptSynopsis } from "@/types/intelligence"
import type { SearchResult } from "@/types/reader"

export function useManuscriptAnalysisState() {
  const [readability, setReadability] = useState<ReadabilityMetrics | null>(null)
  const [readabilityLoading, setReadabilityLoading] = useState(false)
  const [emotionalArc, setEmotionalArc] = useState<EmotionalArcOverview | null>(null)
  const [logicSelectionText, setLogicSelectionText] = useState("")
  const [tighteningSelection, setTighteningSelection] = useState(false)
  const [continuityLoading, setContinuityLoading] = useState(false)
  const [recallQuery, setRecallQuery] = useState("")
  const [recallResults, setRecallResults] = useState<SearchResult[]>([])
  const [recallCharacter, setRecallCharacter] = useState<Character | null>(null)
  const [recallLoading, setRecallLoading] = useState(false)
  const [synopsis, setSynopsis] = useState<ManuscriptSynopsis | null>(null)

  return {
    continuityLoading,
    emotionalArc,
    logicSelectionText,
    readability,
    readabilityLoading,
    recallCharacter,
    recallLoading,
    recallQuery,
    recallResults,
    setContinuityLoading,
    setEmotionalArc,
    setLogicSelectionText,
    setReadability,
    setReadabilityLoading,
    setRecallCharacter,
    setRecallLoading,
    setRecallQuery,
    setRecallResults,
    setSynopsis,
    setTighteningSelection,
    synopsis,
    tighteningSelection,
  }
}
