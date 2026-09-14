import { apiClient } from "./client"
import type {
  SupportAnswer,
  SupportConfig,
  SupportGuideSummary,
  SupportIncident,
  SupportRecentMessage,
  SupportUiContext,
} from "@/types/support"

export const supportApi = {
  config: () => apiClient.get<SupportConfig>("/support/config").then((response) => response.data),
  guides: () => apiClient.get<{ guides: SupportGuideSummary[] }>("/support/guides").then((response) => response.data.guides),
  ask: (message: string, context: SupportUiContext, recentMessages: SupportRecentMessage[] = []) =>
    apiClient.post<SupportAnswer>("/support/chat", {
      message,
      context,
      recent_messages: recentMessages,
    }).then((response) => response.data),
  createIncident: (payload: {
    category: "navigation" | "chapter_save" | "upload" | "processing" | "billing" | "permissions" | "account" | "other"
    feature?: string | null
    summary: string
    context: SupportUiContext
  }) =>
    apiClient.post<SupportIncident>("/support/incidents", { ...payload, confirmed: true }).then((response) => response.data),
}
