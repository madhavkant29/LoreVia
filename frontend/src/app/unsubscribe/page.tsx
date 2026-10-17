"use client"

import Link from "next/link"
import { Suspense, useEffect, useMemo, useState } from "react"
import { useSearchParams } from "next/navigation"

import { emailApi } from "@/lib/api/email"
import { ThemeBrandImage } from "@/components/layout/ThemeBrandImage"
import type { EmailUnsubscribeResponse } from "@/types/email"

type UnsubscribeState = "missing-token" | "submitting" | "success" | "error"

const unsubscribeRequests = new Map<string, Promise<EmailUnsubscribeResponse>>()

function submitUnsubscribeToken(token: string) {
  const existing = unsubscribeRequests.get(token)
  if (existing) {
    return existing
  }

  const request = emailApi.unsubscribe(token).finally(() => {
    unsubscribeRequests.delete(token)
  })
  unsubscribeRequests.set(token, request)
  return request
}

export default function UnsubscribePage() {
  return (
    <Suspense>
      <UnsubscribeInner />
    </Suspense>
  )
}

function UnsubscribeInner() {
  const searchParams = useSearchParams()
  const token = useMemo(() => searchParams.get("token")?.trim() ?? "", [searchParams])
  const [state, setState] = useState<UnsubscribeState>(token ? "submitting" : "missing-token")
  const [email, setEmail] = useState<string | null>(null)

  useEffect(() => {
    if (!token) {
      setState("missing-token")
      return
    }

    let active = true
    setState("submitting")
    setEmail(null)
    void submitUnsubscribeToken(token)
      .then((result) => {
        if (!active) return
        setEmail(result.email)
        setState("success")
      })
      .catch(() => {
        if (!active) return
        setState("error")
      })

    return () => {
      active = false
    }
  }, [token])

  const title =
    state === "success"
      ? "You are unsubscribed"
      : state === "submitting"
        ? "Unsubscribing"
        : "We could not unsubscribe you"
  const body =
    state === "success"
      ? `${email ?? "This email address"} will no longer receive LoreVia product updates or marketing emails. Security, password reset, verification, and billing emails can still be sent.`
      : state === "submitting"
        ? "We are updating your LoreVia email preferences."
        : state === "missing-token"
          ? "This unsubscribe link is missing a token. Open the unsubscribe link from the email again."
          : "This unsubscribe link may be expired or already used. You can still manage email preferences from Settings after signing in."

  return (
    <main className="min-h-[100dvh] bg-[#f8f4ee] px-4 py-8 text-stone-950 sm:px-6 lg:px-8">
      <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-2xl flex-col justify-center">
        <div className="mb-8 border-b border-stone-300 pb-5">
          <Link href="/" aria-label="LoreVia home" className="inline-flex">
            <ThemeBrandImage variant="icon" mode="light" alt="LoreVia" className="h-9 w-9 object-contain" priority />
          </Link>
        </div>

        <section className="border-y border-stone-300 py-8" aria-live="polite">
          <p className="text-sm font-semibold text-[#21615e]">Email preferences</p>
          <h1 className="mt-4 text-3xl font-semibold leading-tight text-[#111827] sm:text-4xl">{title}</h1>
          <p className="mt-4 text-sm leading-6 text-slate-600">{body}</p>

          {state !== "submitting" ? (
            <Link href={state === "success" ? "/" : "/settings#emails"} className="app-button-primary mt-8">
              {state === "success" ? "Return to LoreVia" : "Manage preferences"}
            </Link>
          ) : <p className="mt-6 text-sm text-stone-500">Please wait&hellip;</p>}
        </section>
      </div>
    </main>
  )
}
