import { Suspense } from "react"

import { Skeleton } from "@/components/ui/Skeleton"
import type { BookNote, EmotionalArcOverview, VaultNote } from "@/types/book"
import type { Character } from "@/types/character"
import type { AdvisorSuggestion, EditorialReview } from "@/types/intelligence"
import type { PlotThread } from "@/types/reader"

import type { RightPane } from "./manuscriptPage.constants"
import { ManuscriptWriteRightRail } from "./manuscriptPage.dynamic"

type ContextCharacter = {
  id: string
  name: string
  role?: string | null
}

type ActiveThreadItem = {
  title: string
}

type RecentEventItem = {
  chapter_number: number
  detail: string
}

type WarningItem = {
  title: string
}

type ManuscriptWriteRailProps = {
  activeChapterContextCharacters: ContextCharacter[]
  activeChapterNumber: number
  activeRightPane: RightPane
  activeThreadSummary: ActiveThreadItem[]
  arcSummaryCharacter: EmotionalArcOverview["characters"][number] | null
  bookId: string
  chapterAnnotationsCount: number
  chapterManualNotes: BookNote[]
  characters: Character[]
  generalNotes: BookNote[]
  isDark: boolean
  plotThreads: PlotThread[]
  recentEventSummary: RecentEventItem[]
  review: EditorialReview | null
  selectedCharCard: Character | null
  suggestions: AdvisorSuggestion[]
  totalChapters: number | null
  vaultNotes: VaultNote[]
  warningSummary: WarningItem[]
  onBookNoteSaved: (note: BookNote) => void
  onClearSelectedCharCard: () => void
  onOpenCharCard: (character: Character) => void
  onOpenRightPane: (pane: RightPane) => void
  onTightenSelectedText: () => void
  onVaultNoteSaved: () => void
}

export function ManuscriptWriteRail({
  activeChapterContextCharacters,
  activeChapterNumber,
  activeRightPane,
  activeThreadSummary,
  arcSummaryCharacter,
  bookId,
  chapterAnnotationsCount,
  chapterManualNotes,
  characters,
  generalNotes,
  isDark,
  plotThreads,
  recentEventSummary,
  review,
  selectedCharCard,
  suggestions,
  totalChapters,
  vaultNotes,
  warningSummary,
  onBookNoteSaved,
  onClearSelectedCharCard,
  onOpenCharCard,
  onOpenRightPane,
  onTightenSelectedText,
  onVaultNoteSaved,
}: ManuscriptWriteRailProps) {
  return (
    <Suspense fallback={<Skeleton variant="card" className="min-h-96 rounded-md" />}>
      <ManuscriptWriteRightRail
        isDark={isDark}
        bookId={bookId}
        totalChapters={totalChapters}
        activeRightPane={activeRightPane}
        onOpenRightPane={onOpenRightPane}
        selectedCharCard={selectedCharCard}
        onClearSelectedCharCard={onClearSelectedCharCard}
        activeChapterContextCharacters={activeChapterContextCharacters}
        characters={characters}
        onOpenCharCard={onOpenCharCard}
        activeThreadSummary={activeThreadSummary}
        plotThreads={plotThreads}
        recentEventSummary={recentEventSummary}
        warningSummary={warningSummary}
        review={review}
        onTightenSelectedText={onTightenSelectedText}
        suggestions={suggestions}
        chapterAnnotationsCount={chapterAnnotationsCount}
        chapterManualNotes={chapterManualNotes}
        generalNotes={generalNotes}
        vaultNotes={vaultNotes}
        activeChapterNumber={activeChapterNumber}
        arcSummaryCharacter={arcSummaryCharacter}
        onBookNoteSaved={onBookNoteSaved}
        onVaultNoteSaved={onVaultNoteSaved}
      />
    </Suspense>
  )
}
