import { apiClient } from "./client"
import type { EmailPreferences, EmailUnsubscribeResponse, UpdateEmailPreferencesBody } from "@/types/email"

export const emailApi = {
  getPreferences: () => apiClient.get<EmailPreferences>("/email/preferences").then((r) => r.data),
  updatePreferences: (body: UpdateEmailPreferencesBody) =>
    apiClient.post<EmailPreferences>("/email/preferences", body).then((r) => r.data),
  unsubscribe: (token: string) =>
    apiClient.post<EmailUnsubscribeResponse>("/email/unsubscribe", { token }).then((r) => r.data),
}
