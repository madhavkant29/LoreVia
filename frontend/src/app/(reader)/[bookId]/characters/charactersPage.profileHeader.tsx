import { CharacterProfileTabs, type CharacterProfileTab } from "@/components/reader/CharacterProfileTabs"
import type { Character } from "@/types/character"
import {
  actionButtonClasses,
  OverflowMenu,
  type MenuAction,
} from "./charactersPage.components"
import {
  flagClasses,
  formatRole,
  formatStatus,
  isCuratedCharacter,
  isProtectedCharacter,
} from "./charactersPage.helpers"

type CharacterProfileHeaderProps = {
  activeTab: CharacterProfileTab
  character: Character
  characterMenuActions: MenuAction[]
  characterMenuOpen: boolean
  flags: string[]
  isDark: boolean
  relationshipCount: number
  shareState: "idle" | "copied" | "error"
  onShareCharacter: () => void
  onTabSelect: (tab: CharacterProfileTab) => void
  onToggleCharacterMenu: () => void
}

export function CharacterProfileHeader({
  activeTab,
  character,
  characterMenuActions,
  characterMenuOpen,
  flags,
  isDark,
  relationshipCount,
  shareState,
  onShareCharacter,
  onTabSelect,
  onToggleCharacterMenu,
}: CharacterProfileHeaderProps) {
  return (
    <>
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className={`text-[2.4rem] font-semibold tracking-tight ${isDark ? "text-white" : "text-stone-950"}`}>{character.name}</h2>
            <span className={`rounded-full px-2.5 py-1 text-3xs font-semibold uppercase tracking-[0.16em] ${character.status === "deceased"
              ? isDark ? "bg-amber-500/15 text-amber-100" : "bg-amber-50 text-amber-700"
              : isDark ? "bg-teal-500/15 text-teal-100" : "bg-teal-50 text-teal-700"
            }`}>
              {formatStatus(character.status)}
            </span>
            {character.is_manual ? (
              <span className={`rounded-full px-2.5 py-1 text-3xs font-semibold uppercase tracking-[0.16em] ${isDark ? "bg-violet-500/15 text-violet-100" : "bg-violet-100 text-violet-700"}`}>
                Manual profile
              </span>
            ) : null}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {[
              formatRole(character.role),
              `Chapter ${character.first_chapter}`,
              `Last seen: Chapter ${character.last_seen_chapter ?? character.first_chapter}`,
              `${character.mention_count ?? 0} mentions`,
              `${relationshipCount} relationships`,
            ].map((item) => (
              <span key={item} className={`rounded-full px-3 py-1 text-xs ${isDark ? "border border-[#202a38] bg-white/[0.03] text-slate-300" : "border border-stone-200 bg-white text-stone-600"}`}>
                {item}
              </span>
            ))}
          </div>
          {flags.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {flags.map((flag) => (
                <span key={flag} className={`rounded-full px-2.5 py-1 text-xs font-medium ${flagClasses(isDark, flag)}`}>
                  {flag}
                </span>
              ))}
            </div>
          ) : null}
          {isProtectedCharacter(character) || isCuratedCharacter(character) ? (
            <div className={`mt-3 rounded-sm border px-3 py-2 text-xs ${isDark ? "border-amber-500/25 bg-amber-500/10 text-amber-100" : "border-amber-200 bg-amber-50 text-amber-800"}`}>
              {isProtectedCharacter(character)
                ? "This record is protected from automated repair. Review actions can still touch it manually."
                : "This record has been curated by an author edit and should be reviewed carefully before merging."}
            </div>
          ) : null}
        </div>

        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={onShareCharacter} className={actionButtonClasses(isDark)}>
            <span className="mr-2 inline-flex h-4 w-4 items-center justify-center">
              <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path d="M15 8a3 3 0 1 0-2.83-4H12a3 3 0 0 0 .17 1L7.91 7.14a3 3 0 0 0-3.55.34A3 3 0 1 0 5 13.05l4.36 2.18a3 3 0 1 0 .64-1.28L5.63 11.8a3 3 0 0 0 0-1.6l4.37-2.16A3 3 0 0 0 15 8Z" />
              </svg>
            </span>
            {shareState === "copied" ? "Link copied" : shareState === "error" ? "Share failed" : "Share"}
          </button>
          <OverflowMenu isDark={isDark} open={characterMenuOpen} onToggle={onToggleCharacterMenu} actions={characterMenuActions} />
        </div>
      </div>

      <CharacterProfileTabs active={activeTab} isDark={isDark} onSelect={onTabSelect} />
    </>
  )
}
