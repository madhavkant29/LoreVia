import "server-only"

import { headers } from "next/headers"
import { notFound } from "next/navigation"

import { resolveApiOrigin } from "@/lib/constants"
import type { AdminScope, AdminSession } from "@/types/admin"

const ADMIN_TEST_SESSION_COOKIE = "lorevia_admin_test_session"
const ADMIN_SESSION_API_PATH = "/api/v1/admin/session"

function buildDevAdminSession(mode: string | null): AdminSession | null {
  switch ((mode || "").trim().toLowerCase()) {
    case "owner":
      return {
        is_admin: true,
        scopes: ["moderation_admin", "billing_admin", "super_admin"],
        is_owner: true,
        requires_step_up: false,
        session_expires_at: null,
      }
    case "billing":
      return {
        is_admin: true,
        scopes: ["billing_admin"],
        is_owner: false,
        requires_step_up: true,
        session_expires_at: null,
      }
    case "moderation":
      return {
        is_admin: true,
        scopes: ["moderation_admin"],
        is_owner: false,
        requires_step_up: true,
        session_expires_at: null,
      }
    case "super":
      return {
        is_admin: true,
        scopes: ["super_admin"],
        is_owner: false,
        requires_step_up: true,
        session_expires_at: null,
      }
    case "none":
    case "guest":
      return null
    default:
      return null
  }
}

function normalizeScopes(value: unknown): AdminScope[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter((scope): scope is AdminScope => (
    scope === "moderation_admin" || scope === "billing_admin" || scope === "super_admin"
  ))
}

function readCookieValue(cookieHeader: string | null, name: string): string | null {
  const headerValue = cookieHeader || ""
  for (const part of headerValue.split(";")) {
    const [rawName, ...rawValueParts] = part.trim().split("=")
    if (rawName !== name) {
      continue
    }
    const rawValue = rawValueParts.join("=")
    if (!rawValue) {
      return null
    }
    try {
      return decodeURIComponent(rawValue)
    } catch {
      return rawValue
    }
  }
  return null
}

function resolveDevAdminSessionOverride(cookieHeader: string | null): { matched: boolean, session: AdminSession | null } {
  if (process.env.NODE_ENV === "production") {
    return { matched: false, session: null }
  }
  const secret = (process.env.ADMIN_E2E_TEST_SECRET || "codex-e2e-admin-secret").trim()
  if (!secret) {
    return { matched: false, session: null }
  }

  const cookieValue = readCookieValue(cookieHeader, ADMIN_TEST_SESSION_COOKIE)
  if (!cookieValue) {
    return { matched: false, session: null }
  }

  const separatorIndex = cookieValue.indexOf(":")
  if (separatorIndex <= 0) {
    return { matched: false, session: null }
  }

  const mode = cookieValue.slice(0, separatorIndex)
  const providedSecret = cookieValue.slice(separatorIndex + 1)
  if (providedSecret !== secret) {
    return { matched: false, session: null }
  }

  return { matched: true, session: buildDevAdminSession(mode) }
}

export async function getAdminSessionServer(): Promise<AdminSession> {
  const headerStore = await headers()
  const cookieHeader = headerStore.get("cookie")
  const devOverride = resolveDevAdminSessionOverride(cookieHeader)
  if (devOverride.matched) {
    if (devOverride.session) {
      return devOverride.session
    }
    notFound()
  }

  const response = await fetch(`${resolveApiOrigin()}${ADMIN_SESSION_API_PATH}`, {
    cache: "no-store",
    headers: cookieHeader ? { cookie: cookieHeader } : undefined,
  })

  if ([401, 403, 404].includes(response.status)) {
    notFound()
  }
  if (!response.ok) {
    throw new Error(`Admin session request failed with status ${response.status}`)
  }

  const payload = await response.json() as Record<string, unknown>
  return {
    is_admin: payload.is_admin === true,
    scopes: normalizeScopes(payload.scopes),
    is_owner: payload.is_owner === true,
    requires_step_up: payload.requires_step_up !== false,
    session_expires_at: typeof payload.session_expires_at === "string" ? payload.session_expires_at : null,
  }
}
