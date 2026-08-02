import type {
  EmotionalArcOverview,
  ReadabilityMetrics,
  WriterWorkspace,
  WritingTemplate,
} from "@/types/book"

import { ManuscriptPlanWorkspace } from "./manuscriptPage.dynamic"

type GoalField = "chapter_target" | "book_target" | "session_target"
type CorkboardLane = "ideas" | "drafting" | "revised"
type TemplateDestination = "chapter_note" | "corkboard" | "manuscript_outline"

type ManuscriptPlanWorkspaceSectionProps = {
  bookGoalProgress: number | null
  chapterApproxPages: number
  chapterGoalProgress: number | null
  chapterVersionsCount: number
  chapterWordCount: number
  editorMode: "chapter" | "book"
  emotionalArc: EmotionalArcOverview | null
  fullBookApproxPages: number
  fullBookWordCount: number
  isDark: boolean
  newCorkboardTitle: string
  readability: ReadabilityMetrics | null
  readabilityLoading: boolean
  tighteningSelection: boolean
  workspaceSaving: boolean
  writerWorkspace: WriterWorkspace | null
  onAddCorkboardCard: () => void
  onApplyTemplate: (template: WritingTemplate, destination: TemplateDestination) => Promise<void> | void
  onNewCorkboardTitleChange: (value: string) => void
  onSaveGoals: () => void
  onSaveTemplates: (templates: WritingTemplate[]) => Promise<void> | void
  onTightenSelectedText: () => void
  onUpdateCardLane: (cardId: string, lane: CorkboardLane) => void
  onWordCountGoalChange: (field: GoalField, value: number | null) => void
}

export function ManuscriptPlanWorkspaceSection({
  bookGoalProgress,
  chapterApproxPages,
  chapterGoalProgress,
  chapterVersionsCount,
  chapterWordCount,
  editorMode,
  emotionalArc,
  fullBookApproxPages,
  fullBookWordCount,
  isDark,
  newCorkboardTitle,
  readability,
  readabilityLoading,
  tighteningSelection,
  workspaceSaving,
  writerWorkspace,
  onAddCorkboardCard,
  onApplyTemplate,
  onNewCorkboardTitleChange,
  onSaveGoals,
  onSaveTemplates,
  onTightenSelectedText,
  onUpdateCardLane,
  onWordCountGoalChange,
}: ManuscriptPlanWorkspaceSectionProps) {
  return (
    <ManuscriptPlanWorkspace
      isDark={isDark}
      editorMode={editorMode}
      writerWorkspace={writerWorkspace}
      tighteningSelection={tighteningSelection}
      onTightenSelectedText={onTightenSelectedText}
      chapterWordCount={chapterWordCount}
      fullBookWordCount={fullBookWordCount}
      chapterGoalProgress={chapterGoalProgress}
      bookGoalProgress={bookGoalProgress}
      readabilityLoading={readabilityLoading}
      readability={readability}
      chapterApproxPages={chapterApproxPages}
      fullBookApproxPages={fullBookApproxPages}
      chapterVersionsCount={chapterVersionsCount}
      workspaceSaving={workspaceSaving}
      onWordCountGoalChange={onWordCountGoalChange}
      onSaveGoals={onSaveGoals}
      onApplyTemplate={onApplyTemplate}
      onSaveTemplates={onSaveTemplates}
      newCorkboardTitle={newCorkboardTitle}
      onNewCorkboardTitleChange={onNewCorkboardTitleChange}
      onAddCorkboardCard={onAddCorkboardCard}
      onUpdateCardLane={onUpdateCardLane}
      emotionalArc={emotionalArc}
    />
  )
}
