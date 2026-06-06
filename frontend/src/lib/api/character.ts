import { apiClient } from "./client"
import type { Character, CharacterState } from "@/types/character"

export const charactersApi = {
  get: (characterId: string, include?: string) =>
    apiClient.get<Character>(`/characters/${characterId}`, {
      params: include ? { include } : undefined,
    }).then((r) => r.data),

  getState: (characterId: string, chapter: number) =>
    apiClient.get<CharacterState>(`/characters/${characterId}/state`, {
      params: { chapter },
    }).then((r) => r.data),
}
