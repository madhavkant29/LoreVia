import { describe, expect, it, vi } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

import {
  FolderList,
  InfoLine,
  MiniGraphPreview,
  PanelCard,
  PanelLink,
  RelationStack,
} from "./VaultNotesEditor.components"
import { buildFolderTree } from "./VaultNotesEditor.helpers"

describe("VaultNotesEditor components", () => {
  it("renders folder navigation and side-panel primitives", () => {
    const folderTree = buildFolderTree(
      ["Characters/Ava.md", "Worldbuilding/Cities/Harbor.md"],
      ["Characters", "Worldbuilding/Cities"]
    )
    const folderMarkup = renderToStaticMarkup(
      <FolderList
        node={folderTree}
        activePath="Characters"
        collapsed={{}}
        onToggleFolder={vi.fn()}
        onSelect={vi.fn()}
        onCreateFolder={vi.fn()}
        onDropNote={vi.fn()}
        dropTargetPath="Worldbuilding/Cities"
        onDropTargetChange={vi.fn()}
        isDark
      />
    )
    const panelMarkup = renderToStaticMarkup(
      <PanelCard title="Backlinks" count={2} isDark={false} action={<span>Action</span>}>
        <PanelLink isDark={false}>View all backlinks</PanelLink>
      </PanelCard>
    )
    const infoMarkup = renderToStaticMarkup(
      <InfoLine label="Status" value="Active" isDark activeDot tone />
    )
    const relationMarkup = renderToStaticMarkup(
      <RelationStack
        items={[{ id: "rel-1", label: "Ava", secondary: "Character", reference: "Characters/Ava.md" }]}
        emptyLabel="No relations"
        onOpen={vi.fn()}
        isDark={false}
      />
    )
    const graphMarkup = renderToStaticMarkup(
      <MiniGraphPreview
        currentLabel="Current note"
        nodes={[{ id: "node-1", label: "Linked note" }]}
        isDark
      />
    )

    expect(folderMarkup).toContain("Characters")
    expect(folderMarkup).toContain("Cities")
    expect(folderMarkup).toContain("ring-sky-400/60")
    expect(panelMarkup).toContain("Backlinks")
    expect(infoMarkup).toContain("Active")
    expect(relationMarkup).toContain("Ava")
    expect(graphMarkup).toContain("Current note")
    expect(graphMarkup).toContain("Linked note")
  })
})
