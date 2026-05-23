import { apiClient } from "./client"
import type { EmailPreferences, UpdateEmailPreferencesBody } from "@/types/email"

export const emailApi = {
  getPreferences: () => apiClient.get<EmailPreferences>("/email/preferences").then((r) => r.data),
  updatePreferences: (body: UpdateEmailPreferencesBody) =>
    apiClient.post<EmailPreferences>("/email/preferences", body).then((r) => r.data),
}
