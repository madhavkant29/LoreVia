import type { Character } from "@/types/character"

import type {
  buildManuscriptInspectorClasses,
  ManuscriptCharacterCardDraft,
} from "./manuscriptPage.helpers"

type InspectorClasses = ReturnType<typeof buildManuscriptInspectorClasses>

type ManuscriptCharacterPaneProps = {
  characterCardDraft: ManuscriptCharacterCardDraft
  characterCardEditing: boolean
  characterCardSaving: boolean
  characters: Character[]
  inspectorClasses: InspectorClasses
  isDark: boolean
  selectedCharacter: Character | null
  onBackToCharacters: () => void
  onCancelEdit: () => void
  onDraftFieldChange: (field: keyof ManuscriptCharacterCardDraft, value: string) => void
  onEditCard: () => void
  onOpenCharacter: (character: Character) => void
  onSaveCard: () => void
  onSaveCharacterNote: (character: Character) => void
}

export function ManuscriptCharacterPane({
  characterCardDraft,
  characterCardEditing,
  characterCardSaving,
  characters,
  inspectorClasses,
  isDark,
  selectedCharacter,
  onBackToCharacters,
  onCancelEdit,
  onDraftFieldChange,
  onEditCard,
  onOpenCharacter,
  onSaveCard,
  onSaveCharacterNote,
}: ManuscriptCharacterPaneProps) {
  return (
    <div className={inspectorClasses.section}>
      {selectedCharacter ? (
        <>
          <div className="flex items-center justify-between gap-3">
            <div>
              <button
                onClick={onBackToCharacters}
                className={`mb-1 ${inspectorClasses.label} transition hover:text-teal-300`}
              >
                ← All characters
              </button>
              <p className={`text-base font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{selectedCharacter.name}</p>
              {selectedCharacter.aliases.length > 0 ? (
                <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>aka {selectedCharacter.aliases.join(", ")}</p>
              ) : null}
            </div>
            <div className="flex items-center gap-2">
              {characterCardEditing ? (
                <>
                  <button
                    onClick={onSaveCard}
                    disabled={characterCardSaving}
                    className={inspectorClasses.primaryButton}
                  >
                    {characterCardSaving ? "Saving..." : "Save"}
                  </button>
                  <button
                    onClick={onCancelEdit}
                    className={inspectorClasses.secondaryButton}
                  >
                    Cancel
                  </button>
                </>
              ) : (
                <button
                  onClick={onEditCard}
                  className={inspectorClasses.secondaryButton}
                >
                  Edit card
                </button>
              )}
            </div>
          </div>

          <div className="mt-4 space-y-4">
            <div className="flex flex-wrap gap-2">
              {selectedCharacter.role ? (
                <span className={inspectorClasses.chip}>{selectedCharacter.role === "mc" ? "Main" : selectedCharacter.role === "sc" ? "Supporting" : "Background"}</span>
              ) : null}
              <span className={inspectorClasses.chip}>
                Ch. {selectedCharacter.first_chapter}{selectedCharacter.last_seen_chapter ? ` to ${selectedCharacter.last_seen_chapter}` : ""}
              </span>
              {selectedCharacter.archetype ? (
                <span className={inspectorClasses.chip}>{selectedCharacter.archetype}</span>
              ) : null}
              {selectedCharacter.character_type === "gag" ? (
                <span className={`rounded-sm border px-2 py-0.5 text-3xs font-semibold ${isDark ? "border-amber-400/20 bg-amber-500/10 text-amber-300" : "border-amber-200 bg-amber-50 text-amber-700"}`}>🎭 Gag</span>
              ) : null}
            </div>

            <div>
              <p className={`mb-1 text-3xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Description</p>
              {characterCardEditing ? (
                <textarea
                  rows={3}
                  value={characterCardDraft.description}
                  onChange={(event) => onDraftFieldChange("description", event.target.value)}
                  className={`w-full resize-none rounded-sm border px-3 py-2 text-sm leading-6 outline-none ${isDark ? "border-white/10 bg-black/30 text-slate-200" : "border-stone-200 bg-stone-50 text-stone-800"}`}
                />
              ) : (
                <p className={`text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{selectedCharacter.description || <span className="opacity-40">No description yet.</span>}</p>
              )}
            </div>

            <div>
              <p className={`mb-1 text-3xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Arc summary</p>
              {characterCardEditing ? (
                <textarea
                  rows={4}
                  value={characterCardDraft.arcSummary}
                  onChange={(event) => onDraftFieldChange("arcSummary", event.target.value)}
                  className={`w-full resize-none rounded-sm border px-3 py-2 text-sm leading-6 outline-none ${isDark ? "border-white/10 bg-black/30 text-slate-200" : "border-stone-200 bg-stone-50 text-stone-800"}`}
                />
              ) : (
                <p className={`text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{selectedCharacter.arc_summary || <span className="opacity-40">No arc summary yet.</span>}</p>
              )}
            </div>

            <div>
              <p className={`mb-1 text-3xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Personality</p>
              {characterCardEditing ? (
                <>
                  <input
                    value={characterCardDraft.personalityTags}
                    onChange={(event) => onDraftFieldChange("personalityTags", event.target.value)}
                    className={`w-full rounded-sm border px-3 py-2 text-sm outline-none ${isDark ? "border-white/10 bg-black/30 text-slate-200" : "border-stone-200 bg-stone-50 text-stone-800"}`}
                  />
                  <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Separate multiple traits with commas.</p>
                </>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {(selectedCharacter.personality_tags ?? []).length > 0 ? selectedCharacter.personality_tags.map((tag) => (
                    <span key={tag} className={inspectorClasses.chip}>{tag}</span>
                  )) : <span className={`text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>None recorded.</span>}
                </div>
              )}
            </div>

            <div>
              <p className={`mb-1 text-3xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Motivations</p>
              {characterCardEditing ? (
                <>
                  <input
                    value={characterCardDraft.motivations}
                    onChange={(event) => onDraftFieldChange("motivations", event.target.value)}
                    className={`w-full rounded-sm border px-3 py-2 text-sm outline-none ${isDark ? "border-white/10 bg-black/30 text-slate-200" : "border-stone-200 bg-stone-50 text-stone-800"}`}
                  />
                  <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Separate multiple motivations with commas.</p>
                </>
              ) : (
                <ul className="space-y-1">
                  {(selectedCharacter.motivations ?? []).length > 0 ? selectedCharacter.motivations.map((motivation) => (
                    <li key={motivation} className={`text-sm leading-5 ${isDark ? "text-slate-300" : "text-stone-600"}`}>· {motivation}</li>
                  )) : <li className={`text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>None recorded.</li>}
                </ul>
              )}
            </div>

            <div>
              <p className={`mb-1 text-3xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Fears</p>
              {characterCardEditing ? (
                <>
                  <input
                    value={characterCardDraft.fears}
                    onChange={(event) => onDraftFieldChange("fears", event.target.value)}
                    className={`w-full rounded-sm border px-3 py-2 text-sm outline-none ${isDark ? "border-white/10 bg-black/30 text-slate-200" : "border-stone-200 bg-stone-50 text-stone-800"}`}
                  />
                  <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Separate multiple fears with commas.</p>
                </>
              ) : (
                <ul className="space-y-1">
                  {(selectedCharacter.fears ?? []).length > 0 ? selectedCharacter.fears.map((fear) => (
                    <li key={fear} className={`text-sm leading-5 ${isDark ? "text-slate-300" : "text-stone-600"}`}>· {fear}</li>
                  )) : <li className={`text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>None recorded.</li>}
                </ul>
              )}
            </div>

            {(selectedCharacter.growth_events ?? []).length > 0 ? (
              <div>
                <p className={`mb-1 text-3xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Growth events</p>
                <div className="space-y-2">
                  {selectedCharacter.growth_events!
                    .slice()
                    .sort((left, right) => (right.chapter_number ?? right.chapter ?? 0) - (left.chapter_number ?? left.chapter ?? 0))
                    .map((event, index) => (
                      <div key={index} className={`rounded-sm border px-3 py-2 text-xs ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                        {(event.chapter_number ?? event.chapter) ? (
                          <span className={`font-semibold ${isDark ? "text-teal-300" : "text-teal-700"}`}>
                            Ch. {event.chapter_number ?? event.chapter} ·{" "}
                          </span>
                        ) : null}
                        <span className={isDark ? "text-slate-300" : "text-stone-700"}>{event.event_title || event.event || "Untitled event"}</span>
                        {(event.description || event.impact) ? (
                          <p className={`mt-1 leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>{event.description || event.impact}</p>
                        ) : null}
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {typeof event.impact_score === "number" ? (
                            <span className={inspectorClasses.chip}>
                              impact {event.impact_score}/10
                            </span>
                          ) : null}
                          {event.growth_direction ? (
                            <span className={`${inspectorClasses.chip} capitalize`}>
                              {event.growth_direction}
                            </span>
                          ) : null}
                          {typeof event.growth_magnitude === "number" ? (
                            <span className={inspectorClasses.chip}>
                              growth {event.growth_magnitude}/10
                            </span>
                          ) : null}
                          {event.is_major ? (
                            <span className={`rounded-sm border px-2 py-0.5 ${isDark ? "border-amber-400/20 bg-amber-500/10 text-amber-300" : "border-amber-200 bg-amber-50 text-amber-700"}`}>
                              major
                            </span>
                          ) : null}
                        </div>
                        {event.accomplishments?.length ? (
                          <p className={`mt-2 leading-5 ${isDark ? "text-slate-500" : "text-stone-500"}`}>
                            Accomplishments: {event.accomplishments.join(", ")}
                          </p>
                        ) : null}
                      </div>
                    ))}
                </div>
              </div>
            ) : null}

            <button
              onClick={() => onSaveCharacterNote(selectedCharacter)}
              className={`${inspectorClasses.secondaryButton} w-full`}
            >
              Save as note
            </button>
          </div>
        </>
      ) : (
        <div>
          <p className={inspectorClasses.label}>Characters</p>
          <p className={`mt-1 text-xs ${inspectorClasses.mutedText}`}>Click a name to open their card.</p>
          <div className="mt-3 space-y-2">
            {characters.length === 0 ? (
              <div className={`rounded-md border border-dashed px-3 py-3 text-sm ${isDark ? "border-white/10 text-slate-400" : "border-stone-200 text-stone-500"}`}>
                <p className="font-medium">No characters extracted yet.</p>
                <p className="mt-1 text-xs leading-5">Profiles appear after processing has enough manuscript evidence. Keep writing, or retry processing from the header if extraction failed.</p>
              </div>
            ) : characters.map((character) => (
              <button
                key={character.id}
                onClick={() => onOpenCharacter(character)}
                className={`${inspectorClasses.record} w-full text-left transition hover:border-teal-400/40`}
              >
                <div className="flex items-center justify-between gap-2">
                  <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{character.name}</p>
                  {character.role ? (
                    <span className={inspectorClasses.chip}>{character.role}</span>
                  ) : null}
                </div>
                {character.arc_summary ? (
                  <p className={`mt-1 line-clamp-2 text-xs ${inspectorClasses.mutedText}`}>{character.arc_summary}</p>
                ) : null}
                {character.personality_tags && character.personality_tags.length > 0 ? (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {character.personality_tags.slice(0, 3).map((tag) => (
                      <span key={tag} className={inspectorClasses.chip}>{tag}</span>
                    ))}
                  </div>
                ) : null}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
