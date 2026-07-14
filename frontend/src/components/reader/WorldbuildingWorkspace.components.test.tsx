import { describe, expect, it, vi } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

import {
  BacklogColumn,
  EmptyState,
  EvidencePanel,
  LoadingState,
  MetricCard,
  NoteCard,
  SectionPanel,
  WorkspaceCard,
} from "./WorldbuildingWorkspace.components"
import type { WorldNote } from "@/types/world-building"

const note = {
  id: "note-1",
  book_id: "book-1",
  title: "Clarify the moon gate",
  body: "The moon gate rules conflict with chapter five.",
  context_label: "World gap",
  chapter_number: 5,
  suggested_fix: "Choose one moon-cycle rule.",
  status: "open",
  created_at: "2026-06-01T00:00:00Z",
  updated_at: "2026-06-01T00:00:00Z",
} as WorldNote

describe("WorldbuildingWorkspace components", () => {
  it("renders shared panels, loading states, backlog columns, and notes", () => {
    const workspaceMarkup = renderToStaticMarkup(
      <WorkspaceCard number="01" sectionLabel="Corpus" title="World bible" description="Keep references stable." isDark>
        <span>Body</span>
      </WorkspaceCard>
    )
    const metricMarkup = renderToStaticMarkup(
      <MetricCard label="Active Docs" value="3" note="Separate from chapters" accent="teal" isDark={false} />
    )
    const sectionMarkup = renderToStaticMarkup(
      <SectionPanel title="Continuity" meta="2 issues" description="Check gaps" isDark={false}>
        <EvidencePanel title="World evidence" body="The archive is sealed." isDark={false} />
      </SectionPanel>
    )
    const emptyMarkup = renderToStaticMarkup(
      <EmptyState title="Nothing yet" description="Add a world document." isDark compact />
    )
    const loadingMarkup = renderToStaticMarkup(<LoadingState label="Loading world notes..." isDark={false} />)
    const noteMarkup = renderToStaticMarkup(
      <BacklogColumn
        label="Open Notes"
        count={1}
        emptyTitle="No notes"
        isDark={false}
        items={[
          <NoteCard
            key={note.id}
            note={note}
            isDark={false}
            noteStatusId={null}
            onPrimaryAction={vi.fn()}
            onDelete={vi.fn()}
            primaryLabel="Resolve"
          />,
        ]}
      />
    )

    expect(workspaceMarkup).toContain("World bible")
    expect(metricMarkup).toContain("Active Docs")
    expect(sectionMarkup).toContain("World evidence")
    expect(emptyMarkup).toContain("Nothing yet")
    expect(loadingMarkup).toContain("Loading world notes")
    expect(noteMarkup).toContain("Clarify the moon gate")
    expect(noteMarkup).toContain("Suggested fix")
  })
})
