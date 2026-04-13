import { apiClient } from "./client"
import type { ChatMessage, CrossBookIntelligence, GroundedAnswer } from "@/types/intelligence"

export const intelligenceApi = {
  answer: (bookId: string, question: string, currentChapter: number) =>
    apiClient.post<GroundedAnswer>(`/intelligence/${bookId}/qa`, {
      question, current_chapter: currentChapter,
    }).then(r => r.data),
  chat: (bookId: string, characterId: string, messages: ChatMessage[], currentChapter: number, contextSummary = "") =>
    apiClient.post<{ reply: string; character: string; grounded_hint?: string | null }>(
      `/intelligence/${bookId}/chat/${characterId}`,
      { messages, current_chapter: currentChapter, context_summary: contextSummary }
    ).then(r => r.data),
  getCrossBookIntelligence: (bookId: string) =>
    apiClient.get<CrossBookIntelligence>(`/intelligence/${bookId}/cross-book-intelligence`).then(r => r.data),
}
