import { useManuscriptAutosaveEffects } from "./manuscriptPage.autosaveEffects"
import { useManuscriptProcessingPoll } from "./manuscriptPage.processingPoll"
import { useManuscriptPageSyncEffects } from "./manuscriptPage.syncEffects"
import { useManuscriptUiEffects } from "./manuscriptPage.uiEffects"

type ManuscriptRuntimeEffectsArgs =
  Parameters<typeof useManuscriptProcessingPoll>[0] &
  Parameters<typeof useManuscriptPageSyncEffects>[0] &
  Parameters<typeof useManuscriptAutosaveEffects>[0] &
  Parameters<typeof useManuscriptUiEffects>[0]

export function useManuscriptRuntimeEffects(args: ManuscriptRuntimeEffectsArgs) {
  useManuscriptProcessingPoll(args)
  useManuscriptPageSyncEffects(args)
  useManuscriptAutosaveEffects(args)
  useManuscriptUiEffects(args)
}
