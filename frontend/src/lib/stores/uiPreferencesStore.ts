"use client"

import axios from "axios"
import { create } from "zustand"

import { uiPreferencesApi } from "@/lib/api/uiPreferences"
import { normalizeBookRouteId } from "@/lib/utils/bookRoutes"
import type {
  BookPreset,
  ComplexityMode,
  PreferenceConflictResponse,
  ToolVisibility,
  UiPreferenceOperation,
  UserBookUiPreference,
  UserUiPreference,
} from "@/types/uiPreferences"

export const UI_PREFERENCES_CACHE_PREFIX = "lorevia-ui-preferences:v1"
const UI_PREFERENCES_BROADCAST_CHANNEL = "lorevia-ui-preferences:v1"
const MAX_CACHED_OPERATIONS = 500
const WRITE_DEBOUNCE_MS = 250

export type UiPreferenceSyncState =
  | "idle"
  | "loading"
  | "syncing"
  | "sync_pending"
  | "api_unavailable"

interface CachedUiPreferenceState {
  preferences: UserUiPreference
  bookPreferences: Record<string, UserBookUiPreference>
  pendingGlobalOperations: UiPreferenceOperation[]
  pendingBookOperations: Record<string, UiPreferenceOperation[]>
}

type PreferenceBroadcast =
  | { type: "ui-preferences-confirmed"; userId: string; resource: "global"; preference: UserUiPreference }
  | { type: "ui-preferences-confirmed"; userId: string; resource: "book"; bookId: string; preference: UserBookUiPreference }

interface UiPreferencesStore {
  activeUserId: string | null
  preferences: UserUiPreference
  bookPreferences: Record<string, UserBookUiPreference>
  syncState: UiPreferenceSyncState
  syncMessage: string | null
  pendingGlobalOperations: UiPreferenceOperation[]
  pendingBookOperations: Record<string, UiPreferenceOperation[]>
  hydrateForUser: (userId: string) => Promise<void>
  hydrateBook: (bookId: string) => Promise<void>
  clearActiveUser: () => void
  retrySync: () => Promise<void>
  patchGlobal: (operations: UiPreferenceOperation[]) => Promise<void>
  patchBook: (bookId: string, operations: UiPreferenceOperation[]) => Promise<void>
  setComplexityMode: (mode: ComplexityMode) => Promise<void>
  setDashboardToolVisibility: (toolId: string, visibility: ToolVisibility | boolean) => Promise<void>
  setBookPreset: (bookId: string, preset: BookPreset) => Promise<void>
  setBookToolHidden: (bookId: string, toolId: string, hidden: boolean) => Promise<void>
  setTimelineCollapsedSection: (bookId: string, sectionId: string, collapsed: boolean) => Promise<void>
  snoozeRecommendation: (id: string, fingerprint: string, hours?: number) => Promise<void>
  dismissRecommendation: (id: string, fingerprint: string) => Promise<void>
  dismissGuidance: (surface: string, fingerprint: string) => Promise<void>
  restartGuidance: () => Promise<void>
}

let accountGeneration = 0
let broadcastChannel: BroadcastChannel | null = null
const syncPromises = new Map<string, Promise<boolean>>()
const syncTimers = new Map<string, number>()

export function defaultUserUiPreference(mode: ComplexityMode = "standard"): UserUiPreference {
  return {
    schema_version: 1,
    revision: 1,
    complexity_mode: mode,
    dashboard_visibility: {},
    dashboard_order: [],
    public_tool_visibility: {},
    density: "comfortable",
    reader_toolbar_density: "standard",
    locked_tool_presentation: "compact",
    default_workspace_shell: "reader",
    mobile_actions: [],
    guidance_dismissals: {},
    recommendation_snoozes: {},
    updated_at: null,
  }
}

export function defaultBookUiPreference(
  bookId: string,
  mode: ComplexityMode = "focused",
): UserBookUiPreference {
  return {
    book_id: normalizeBookRouteId(bookId),
    schema_version: 1,
    revision: 1,
    book_preset: mode === "focused" ? "draft" : "all",
    advanced_tool_override: null,
    hidden_book_tools: [],
    overview_cards: {},
    reader_actions: [],
    mobile_actions: [],
    panel_state: {},
    timeline_collapsed_sections: {},
    updated_at: null,
  }
}

function cacheKey(userId: string) {
  return `${UI_PREFERENCES_CACHE_PREFIX}:${userId}`
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

function isOperation(value: unknown): value is UiPreferenceOperation {
  return isRecord(value)
    && (value.op === "set" || value.op === "unset")
    && typeof value.path === "string"
    && value.path.startsWith("/")
    && value.path.length <= 256
}

function safeOperations(value: unknown) {
  if (!Array.isArray(value)) return [] as UiPreferenceOperation[]
  return value.filter(isOperation).slice(-MAX_CACHED_OPERATIONS)
}

function safeStringArray(value: unknown) {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string").slice(0, 500)
    : []
}

function safeRecord(value: unknown) {
  return isRecord(value) ? value : {}
}

function parseUserPreference(value: unknown): UserUiPreference | null {
  if (!isRecord(value) || value.schema_version !== 1) return null
  const revision = typeof value.revision === "number" && value.revision >= 1 ? Math.floor(value.revision) : 1
  const mode = value.complexity_mode
  if (mode !== "focused" && mode !== "standard" && mode !== "power") return null
  return {
    ...defaultUserUiPreference(mode),
    ...value,
    schema_version: 1,
    revision,
    complexity_mode: mode,
    dashboard_visibility: safeRecord(value.dashboard_visibility) as UserUiPreference["dashboard_visibility"],
    dashboard_order: safeStringArray(value.dashboard_order),
    public_tool_visibility: safeRecord(value.public_tool_visibility) as UserUiPreference["public_tool_visibility"],
    mobile_actions: safeStringArray(value.mobile_actions),
    guidance_dismissals: safeRecord(value.guidance_dismissals),
    recommendation_snoozes: safeRecord(value.recommendation_snoozes),
  } as UserUiPreference
}

function parseBookPreference(value: unknown, fallbackBookId: string, mode: ComplexityMode): UserBookUiPreference | null {
  if (!isRecord(value) || value.schema_version !== 1) return null
  const bookId = normalizeBookRouteId(typeof value.book_id === "string" ? value.book_id : fallbackBookId)
  const preset = value.book_preset
  if (preset !== "draft" && preset !== "review" && preset !== "story_bible" && preset !== "share" && preset !== "all") {
    return null
  }
  return {
    ...defaultBookUiPreference(bookId, mode),
    ...value,
    book_id: bookId,
    schema_version: 1,
    revision: typeof value.revision === "number" && value.revision >= 1 ? Math.floor(value.revision) : 1,
    book_preset: preset,
    hidden_book_tools: safeStringArray(value.hidden_book_tools),
    overview_cards: safeRecord(value.overview_cards) as UserBookUiPreference["overview_cards"],
    reader_actions: safeStringArray(value.reader_actions),
    mobile_actions: safeStringArray(value.mobile_actions),
    panel_state: safeRecord(value.panel_state),
    timeline_collapsed_sections: Object.fromEntries(
      Object.entries(safeRecord(value.timeline_collapsed_sections))
        .filter((entry): entry is [string, boolean] => typeof entry[1] === "boolean"),
    ),
  } as UserBookUiPreference
}

export function parseUiPreferenceCache(raw: string | null): CachedUiPreferenceState | null {
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as unknown
    if (!isRecord(parsed)) return null
    const preferences = parseUserPreference(parsed.preferences)
    if (!preferences) return null
    const bookPreferences: Record<string, UserBookUiPreference> = {}
    if (isRecord(parsed.bookPreferences)) {
      for (const [rawBookId, value] of Object.entries(parsed.bookPreferences)) {
        const preference = parseBookPreference(value, rawBookId, preferences.complexity_mode)
        if (preference) bookPreferences[preference.book_id] = preference
      }
    }
    const pendingBookOperations: Record<string, UiPreferenceOperation[]> = {}
    if (isRecord(parsed.pendingBookOperations)) {
      for (const [rawBookId, value] of Object.entries(parsed.pendingBookOperations)) {
        const bookId = normalizeBookRouteId(rawBookId)
        const operations = safeOperations(value)
        if (operations.length) pendingBookOperations[bookId] = operations
      }
    }
    return {
      preferences,
      bookPreferences,
      pendingGlobalOperations: safeOperations(parsed.pendingGlobalOperations),
      pendingBookOperations,
    }
  } catch {
    return null
  }
}

function readCache(userId: string) {
  if (typeof window === "undefined") return null
  try {
    return parseUiPreferenceCache(window.localStorage.getItem(cacheKey(userId)))
  } catch {
    return null
  }
}

function writeCache(userId: string, state: CachedUiPreferenceState) {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(cacheKey(userId), JSON.stringify(state))
  } catch {
    // Storage failures do not block in-memory preferences.
  }
}

function getBroadcastChannel() {
  if (typeof window === "undefined" || typeof BroadcastChannel === "undefined") return null
  if (!broadcastChannel) broadcastChannel = new BroadcastChannel(UI_PREFERENCES_BROADCAST_CHANNEL)
  return broadcastChannel
}

function broadcastConfirmed(message: PreferenceBroadcast) {
  try {
    getBroadcastChannel()?.postMessage(message)
  } catch {
    // Cross-tab sync is best effort; server revision reconciliation remains authoritative.
  }
}

function currentCachedState(state: UiPreferencesStore): CachedUiPreferenceState {
  return {
    preferences: state.preferences,
    bookPreferences: state.bookPreferences,
    pendingGlobalOperations: state.pendingGlobalOperations,
    pendingBookOperations: state.pendingBookOperations,
  }
}

function persistForUser(userId: string, get: () => UiPreferencesStore) {
  if (get().activeUserId === userId) writeCache(userId, currentCachedState(get()))
}

function applyOperationToPreference<TPreference extends Record<string, unknown>>(
  preference: TPreference,
  operation: UiPreferenceOperation,
): TPreference {
  const parts = operation.path.split("/").filter(Boolean)
  if (parts.length === 0) return preference
  const next = { ...preference }
  const key = parts[0] as keyof TPreference
  if (parts.length === 1) {
    if (operation.op === "unset") delete next[key]
    else next[key] = operation.value as TPreference[keyof TPreference]
    return next
  }
  const parent = { ...((next[key] as Record<string, unknown> | undefined) ?? {}) }
  if (operation.op === "unset") delete parent[parts[1]]
  else parent[parts[1]] = operation.value
  next[key] = parent as TPreference[keyof TPreference]
  return next
}

export function applyUserPreferenceOperations(
  preference: UserUiPreference,
  operations: UiPreferenceOperation[],
): UserUiPreference {
  return operations.reduce(
    (current, operation) => applyOperationToPreference(
      current as unknown as Record<string, unknown>,
      operation,
    ) as unknown as UserUiPreference,
    preference,
  )
}

export function applyBookPreferenceOperations(
  preference: UserBookUiPreference,
  operations: UiPreferenceOperation[],
): UserBookUiPreference {
  return operations.reduce(
    (current, operation) => applyOperationToPreference(
      current as unknown as Record<string, unknown>,
      operation,
    ) as unknown as UserBookUiPreference,
    preference,
  )
}

function conflictPayload<TPreference>(error: unknown): PreferenceConflictResponse<TPreference> | null {
  if (!axios.isAxiosError(error) || error.response?.status !== 409) return null
  const data = error.response.data as Partial<PreferenceConflictResponse<TPreference>> | undefined
  if (!data?.latest || typeof data.latest_revision !== "number") return null
  return data as PreferenceConflictResponse<TPreference>
}

function clearScheduledSyncs() {
  for (const timer of syncTimers.values()) window.clearTimeout(timer)
  syncTimers.clear()
}

function scheduleSync(key: string, sync: () => Promise<boolean>) {
  if (typeof window === "undefined") return
  const previous = syncTimers.get(key)
  if (previous) window.clearTimeout(previous)
  syncTimers.set(key, window.setTimeout(() => {
    syncTimers.delete(key)
    void sync()
  }, WRITE_DEBOUNCE_MS))
}

async function runExclusive(key: string, job: () => Promise<boolean>) {
  const running = syncPromises.get(key)
  if (running) return running
  const promise = job().finally(() => {
    if (syncPromises.get(key) === promise) syncPromises.delete(key)
  })
  syncPromises.set(key, promise)
  return promise
}

export const useUiPreferencesStore = create<UiPreferencesStore>()((set, get) => {
  const accountIsCurrent = (userId: string, generation: number) =>
    get().activeUserId === userId && accountGeneration === generation

  const syncGlobalNow = async (userId: string, generation: number): Promise<boolean> => {
    const key = `${generation}:${userId}:global`
    return runExclusive(key, async () => {
      while (accountIsCurrent(userId, generation)) {
        const sent = get().pendingGlobalOperations
        if (!sent.length) return true
        const baseRevision = get().preferences.revision
        set({ syncState: "syncing", syncMessage: null })
        try {
          let saved: UserUiPreference
          try {
            saved = await uiPreferencesApi.patchGlobal(baseRevision, sent)
          } catch (error) {
            const conflict = conflictPayload<UserUiPreference>(error)
            if (!conflict) throw error
            saved = await uiPreferencesApi.patchGlobal(conflict.latest_revision, sent)
          }
          if (!accountIsCurrent(userId, generation)) return false
          const remaining = get().pendingGlobalOperations.slice(sent.length)
          set({
            preferences: applyUserPreferenceOperations(saved, remaining),
            pendingGlobalOperations: remaining,
            syncState: remaining.length ? "syncing" : "idle",
            syncMessage: null,
          })
          persistForUser(userId, get)
          broadcastConfirmed({ type: "ui-preferences-confirmed", userId, resource: "global", preference: saved })
        } catch {
          if (!accountIsCurrent(userId, generation)) return false
          set({ syncState: "sync_pending", syncMessage: "Saved on this device; sync pending" })
          persistForUser(userId, get)
          return false
        }
      }
      return false
    })
  }

  const syncBookNow = async (userId: string, generation: number, rawBookId: string): Promise<boolean> => {
    const bookId = normalizeBookRouteId(rawBookId)
    const key = `${generation}:${userId}:book:${bookId}`
    return runExclusive(key, async () => {
      while (accountIsCurrent(userId, generation)) {
        const sent = get().pendingBookOperations[bookId] ?? []
        if (!sent.length) return true
        const current = get().bookPreferences[bookId]
          ?? defaultBookUiPreference(bookId, get().preferences.complexity_mode)
        set({ syncState: "syncing", syncMessage: null })
        try {
          let saved: UserBookUiPreference
          try {
            saved = await uiPreferencesApi.patchBook(bookId, current.revision, sent)
          } catch (error) {
            const conflict = conflictPayload<UserBookUiPreference>(error)
            if (!conflict) throw error
            saved = await uiPreferencesApi.patchBook(bookId, conflict.latest_revision, sent)
          }
          if (!accountIsCurrent(userId, generation)) return false
          const remaining = (get().pendingBookOperations[bookId] ?? []).slice(sent.length)
          set((state) => ({
            bookPreferences: {
              ...state.bookPreferences,
              [bookId]: applyBookPreferenceOperations({ ...saved, book_id: bookId }, remaining),
            },
            pendingBookOperations: { ...state.pendingBookOperations, [bookId]: remaining },
            syncState: remaining.length ? "syncing" : "idle",
            syncMessage: null,
          }))
          persistForUser(userId, get)
          broadcastConfirmed({
            type: "ui-preferences-confirmed",
            userId,
            resource: "book",
            bookId,
            preference: { ...saved, book_id: bookId },
          })
        } catch {
          if (!accountIsCurrent(userId, generation)) return false
          set({ syncState: "sync_pending", syncMessage: "Saved on this device; sync pending" })
          persistForUser(userId, get)
          return false
        }
      }
      return false
    })
  }

  if (typeof window !== "undefined") {
    getBroadcastChannel()?.addEventListener("message", (event) => {
      const payload = event.data as PreferenceBroadcast
      if (payload?.type !== "ui-preferences-confirmed" || payload.userId !== get().activeUserId) return
      if (payload.resource === "global") {
        if (payload.preference.revision < get().preferences.revision) return
        set((state) => ({
          preferences: applyUserPreferenceOperations(payload.preference, state.pendingGlobalOperations),
        }))
      } else {
        const bookId = normalizeBookRouteId(payload.bookId)
        const current = get().bookPreferences[bookId]
        if (current && payload.preference.revision < current.revision) return
        set((state) => ({
          bookPreferences: {
            ...state.bookPreferences,
            [bookId]: applyBookPreferenceOperations(
              { ...payload.preference, book_id: bookId },
              state.pendingBookOperations[bookId] ?? [],
            ),
          },
        }))
      }
      const userId = get().activeUserId
      if (userId) persistForUser(userId, get)
    })
  }

  return {
    activeUserId: null,
    preferences: defaultUserUiPreference(),
    bookPreferences: {},
    syncState: "idle",
    syncMessage: null,
    pendingGlobalOperations: [],
    pendingBookOperations: {},

    hydrateForUser: async (userId) => {
      accountGeneration += 1
      clearScheduledSyncs()
      const generation = accountGeneration
      const cached = readCache(userId)
      set({
        activeUserId: userId,
        preferences: cached?.preferences ?? defaultUserUiPreference(),
        bookPreferences: cached?.bookPreferences ?? {},
        pendingGlobalOperations: cached?.pendingGlobalOperations ?? [],
        pendingBookOperations: cached?.pendingBookOperations ?? {},
        syncState: "loading",
        syncMessage: null,
      })
      try {
        const serverPreference = await uiPreferencesApi.getGlobal()
        if (!accountIsCurrent(userId, generation)) return
        set((state) => ({
          preferences: applyUserPreferenceOperations(serverPreference, state.pendingGlobalOperations),
          syncState: "idle",
          syncMessage: null,
        }))
        persistForUser(userId, get)
        if (
          get().pendingGlobalOperations.length
          || Object.values(get().pendingBookOperations).some((operations) => operations.length > 0)
        ) {
          await get().retrySync()
        }
      } catch {
        if (!accountIsCurrent(userId, generation)) return
        set({
          syncState: cached ? "sync_pending" : "api_unavailable",
          syncMessage: cached
            ? "Saved on this device; sync pending"
            : "Using the standard layout until preferences load.",
        })
      }
    },

    hydrateBook: async (rawBookId) => {
      const bookId = normalizeBookRouteId(rawBookId)
      const userId = get().activeUserId
      const generation = accountGeneration
      if (!userId) return
      if (!get().bookPreferences[bookId]) {
        set((state) => ({
          bookPreferences: {
            ...state.bookPreferences,
            [bookId]: defaultBookUiPreference(bookId, state.preferences.complexity_mode),
          },
        }))
      }
      try {
        const serverPreference = await uiPreferencesApi.getBook(bookId)
        if (!accountIsCurrent(userId, generation)) return
        set((state) => ({
          bookPreferences: {
            ...state.bookPreferences,
            [bookId]: applyBookPreferenceOperations(
              { ...serverPreference, book_id: bookId },
              state.pendingBookOperations[bookId] ?? [],
            ),
          },
          syncState: "idle",
          syncMessage: null,
        }))
        persistForUser(userId, get)
      } catch {
        if (!accountIsCurrent(userId, generation)) return
        set({ syncState: "sync_pending", syncMessage: "Saved on this device; sync pending" })
      }
    },

    clearActiveUser: () => {
      accountGeneration += 1
      clearScheduledSyncs()
      set({
        activeUserId: null,
        preferences: defaultUserUiPreference(),
        bookPreferences: {},
        syncState: "idle",
        syncMessage: null,
        pendingGlobalOperations: [],
        pendingBookOperations: {},
      })
    },

    retrySync: async () => {
      const userId = get().activeUserId
      const generation = accountGeneration
      if (!userId) return
      clearScheduledSyncs()
      const globalResult = await syncGlobalNow(userId, generation)
      const bookIds = Object.entries(get().pendingBookOperations)
        .filter(([, operations]) => operations.length > 0)
        .map(([bookId]) => bookId)
      const bookResults = await Promise.all(
        bookIds.map((bookId) => syncBookNow(userId, generation, bookId)),
      )
      if (!accountIsCurrent(userId, generation)) return
      const hasPending = get().pendingGlobalOperations.length > 0
        || Object.values(get().pendingBookOperations).some((operations) => operations.length > 0)
      set({
        syncState: globalResult && bookResults.every(Boolean) && !hasPending ? "idle" : "sync_pending",
        syncMessage: hasPending ? "Saved on this device; sync pending" : null,
      })
      persistForUser(userId, get)
    },

    patchGlobal: async (operations) => {
      const userId = get().activeUserId
      const generation = accountGeneration
      if (!userId || operations.length === 0) return
      set((state) => ({
        preferences: applyUserPreferenceOperations(state.preferences, operations),
        pendingGlobalOperations: [...state.pendingGlobalOperations, ...operations].slice(-MAX_CACHED_OPERATIONS),
        syncState: "syncing",
        syncMessage: null,
      }))
      persistForUser(userId, get)
      scheduleSync(`${generation}:${userId}:global`, () => syncGlobalNow(userId, generation))
    },

    patchBook: async (rawBookId, operations) => {
      const bookId = normalizeBookRouteId(rawBookId)
      const userId = get().activeUserId
      const generation = accountGeneration
      if (!userId || operations.length === 0) return
      set((state) => {
        const current = state.bookPreferences[bookId]
          ?? defaultBookUiPreference(bookId, state.preferences.complexity_mode)
        return {
          bookPreferences: {
            ...state.bookPreferences,
            [bookId]: applyBookPreferenceOperations(current, operations),
          },
          pendingBookOperations: {
            ...state.pendingBookOperations,
            [bookId]: [
              ...(state.pendingBookOperations[bookId] ?? []),
              ...operations,
            ].slice(-MAX_CACHED_OPERATIONS),
          },
          syncState: "syncing",
          syncMessage: null,
        }
      })
      persistForUser(userId, get)
      scheduleSync(
        `${generation}:${userId}:book:${bookId}`,
        () => syncBookNow(userId, generation, bookId),
      )
    },

    setComplexityMode: (mode) =>
      get().patchGlobal([{ op: "set", path: "/complexity_mode", value: mode }]),

    setDashboardToolVisibility: (toolId, visibility) =>
      get().patchGlobal([
        {
          op: "set",
          path: `/dashboard_visibility/${toolId}`,
          value: visibility === false || visibility === "user_hidden" ? "user_hidden" : "visible",
        },
      ]),

    setBookPreset: (bookId, preset) =>
      get().patchBook(bookId, [{ op: "set", path: "/book_preset", value: preset }]),

    setBookToolHidden: (rawBookId, toolId, hidden) => {
      const bookId = normalizeBookRouteId(rawBookId)
      const current = get().bookPreferences[bookId]
        ?? defaultBookUiPreference(bookId, get().preferences.complexity_mode)
      const nextHidden = hidden
        ? Array.from(new Set([...current.hidden_book_tools, toolId]))
        : current.hidden_book_tools.filter((id) => id !== toolId)
      return get().patchBook(bookId, [{ op: "set", path: "/hidden_book_tools", value: nextHidden }])
    },

    setTimelineCollapsedSection: (bookId, sectionId, collapsed) =>
      get().patchBook(bookId, [
        { op: "set", path: `/timeline_collapsed_sections/${sectionId}`, value: collapsed },
      ]),

    snoozeRecommendation: (id, fingerprint, hours = 24) =>
      get().patchGlobal([{
        op: "set",
        path: `/recommendation_snoozes/${id}`,
        value: {
          fingerprint,
          snoozed_until: new Date(Date.now() + hours * 60 * 60 * 1000).toISOString(),
        },
      }]),

    dismissRecommendation: (id, fingerprint) =>
      get().patchGlobal([{
        op: "set",
        path: `/recommendation_snoozes/${id}`,
        value: { fingerprint, dismissed_at: new Date().toISOString() },
      }]),

    dismissGuidance: (surface, fingerprint) =>
      get().patchGlobal([{
        op: "set",
        path: `/guidance_dismissals/${surface}`,
        value: { fingerprint, dismissed_at: new Date().toISOString() },
      }]),

    restartGuidance: () =>
      get().patchGlobal([{ op: "set", path: "/guidance_dismissals", value: {} }]),
  }
})
