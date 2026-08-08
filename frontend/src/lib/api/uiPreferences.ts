import { apiClient } from "./client"
import { normalizeBookRouteId } from "@/lib/utils/bookRoutes"
import type {
  BookVisibilitySummary,
  UiPreferenceImportMode,
  UiPreferenceImportResult,
  UiPreferenceOperation,
  UserBookUiPreference,
  UserUiPreference,
  UserUiPreferenceExport,
} from "@/types/uiPreferences"

export const uiPreferencesApi = {
  getGlobal: () =>
    apiClient.get<UserUiPreference>("/auth/me/ui-preferences").then((response) => response.data),
  patchGlobal: (baseRevision: number, operations: UiPreferenceOperation[]) =>
    apiClient
      .patch<UserUiPreference>("/auth/me/ui-preferences", {
        base_revision: baseRevision,
        operations,
      })
      .then((response) => response.data),
  getBook: (bookId: string) =>
    apiClient
      .get<UserBookUiPreference>(`/auth/me/ui-preferences/books/${normalizeBookRouteId(bookId)}`)
      .then((response) => response.data),
  patchBook: (bookId: string, baseRevision: number, operations: UiPreferenceOperation[]) =>
    apiClient
      .patch<UserBookUiPreference>(`/auth/me/ui-preferences/books/${normalizeBookRouteId(bookId)}`, {
        base_revision: baseRevision,
        operations,
      })
      .then((response) => response.data),
  exportPreferences: () =>
    apiClient
      .get<UserUiPreferenceExport>("/auth/me/ui-preferences/export")
      .then((response) => response.data),
  importPreferences: (
    payload: {
      mode?: UiPreferenceImportMode
      confirm_replace?: boolean
      global_preferences?: Partial<UserUiPreference>
      book_preferences?: Array<Partial<UserBookUiPreference> & { book_id: string }>
    },
  ) =>
    apiClient
      .post<UiPreferenceImportResult>("/auth/me/ui-preferences/import", payload)
      .then((response) => response.data),
  getBookVisibilitySummary: (bookId: string) =>
    apiClient
      .get<BookVisibilitySummary>(`/books/${normalizeBookRouteId(bookId)}/visibility-summary`)
      .then((response) => response.data),
}
