import type { VaultGraphEdge, VaultNote, VaultNoteLink, VaultNoteRelations } from "@/types/book"

import { MiniGraphPreview, PanelCard, PanelLink, RelationStack } from "./VaultNotesEditor.components"
import { formatRelativeTime, noteTitle } from "./VaultNotesEditor.helpers"
import { IconArrowUpRight, IconPlus } from "./VaultNotesEditor.icons"
import { Tooltip } from "@/components/ui/Tooltip"

export function VaultNoteRelatedPanels({
  isDark,
  previewNodes,
  recentMentions,
  relations,
  selectedNote,
  selectedOutgoingLinks,
  onOpenGraph,
  onOpenNote,
}: {
  isDark: boolean
  previewNodes: { id: string; label: string }[]
  recentMentions: VaultNoteLink[]
  relations: VaultNoteRelations | null
  selectedNote: VaultNote | null
  selectedOutgoingLinks: VaultGraphEdge[]
  onOpenGraph: () => void
  onOpenNote: (reference: string) => void
}) {
  return (
    <>
      <PanelCard isDark={isDark} title="Backlinks" count={relations?.backlinks.length ?? 0}>
        <RelationStack
          items={(relations?.backlinks ?? []).map((link) => ({ id: link.id, label: noteTitle(link.source_note_path), secondary: "Mentions", reference: link.source_note_path }))}
          onOpen={onOpenNote}
          emptyLabel="No backlinks yet."
          isDark={isDark}
        />
        {Boolean(relations?.backlinks.length) ? <PanelLink isDark={isDark}>View all backlinks</PanelLink> : null}
      </PanelCard>

      <PanelCard isDark={isDark} title="Outgoing links" count={selectedOutgoingLinks.length}>
        <RelationStack
          items={selectedOutgoingLinks.map((link, index) => ({ id: `${link.source}-${link.target}-${index}`, label: noteTitle(link.target), secondary: "Linked", reference: link.target }))}
          onOpen={onOpenNote}
          emptyLabel="No outgoing links yet."
          isDark={isDark}
        />
        {selectedOutgoingLinks.length ? <PanelLink isDark={isDark}>View all outgoing links</PanelLink> : null}
      </PanelCard>

      <PanelCard isDark={isDark} title="Tags">
        {relations?.tags.length ? (
          <div className="flex flex-wrap items-center gap-2">
            {relations.tags.map((tag) => (
              <span key={tag.id} className={`rounded-xl px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/[0.05] text-slate-200" : "bg-stone-100 text-stone-700"}`}>
                {tag.tag_name}
              </span>
            ))}
            <Tooltip content="Add tag">
              <button type="button" aria-label="Add tag" className={`inline-flex h-8 w-8 items-center justify-center rounded-xl ${isDark ? "bg-white/[0.05] text-slate-300" : "bg-stone-100 text-stone-700"}`}>
                <IconPlus />
              </button>
            </Tooltip>
          </div>
        ) : (
          <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>No tags found for this note.</p>
        )}
      </PanelCard>

      <PanelCard isDark={isDark} title="Recent mentions" count={recentMentions.length}>
        <RelationStack
          items={recentMentions.map((link) => ({
            id: link.id,
            label: noteTitle(link.source_note_path),
            secondary: formatRelativeTime(link.created_at),
            reference: link.source_note_path,
          }))}
          onOpen={onOpenNote}
          emptyLabel="No recent mentions."
          isDark={isDark}
        />
      </PanelCard>

      <PanelCard
        isDark={isDark}
        title="Graph preview"
        action={(
          <button
            type="button"
            onClick={onOpenGraph}
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold ${isDark ? "border-white/[0.08] bg-white/[0.03] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}
          >
            Open full graph
            <IconArrowUpRight />
          </button>
        )}
      >
        <MiniGraphPreview
          currentLabel={selectedNote ? noteTitle(selectedNote.path) : "Current note"}
          nodes={previewNodes}
          isDark={isDark}
        />
      </PanelCard>
    </>
  )
}
