"use client"

import Image from "next/image"
import Link from "next/link"
import { Suspense, useEffect, useMemo, useState } from "react"
import { useSearchParams } from "next/navigation"

import { emailApi } from "@/lib/api/email"
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
    <main className="min-h-screen bg-[#f3f4f6] px-4 py-8 text-[#111827] sm:px-6 lg:px-8">
      <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-2xl flex-col justify-center">
        <div className="mb-8">
          <Link href="/" aria-label="LoreVia home" className="inline-flex">
            <Image src="/logoandtext.png" alt="LoreVia" width={152} height={43} priority />
          </Link>
        </div>

        <section className="rounded-lg border border-slate-200 bg-white/92 p-6 shadow-sm sm:p-8" aria-live="polite">
          <p className="text-xs font-bold uppercase tracking-[0.22em] text-[#21615e]">Email preferences</p>
          <h1 className="mt-4 text-3xl font-semibold leading-tight text-[#111827] sm:text-4xl">{title}</h1>
          <p className="mt-4 text-sm leading-6 text-slate-600">{body}</p>

          {state === "submitting" ? (
            <div className="mt-6 h-2 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full w-1/2 rounded-full bg-[#21615e]" />
            </div>
          ) : null}

          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link href="/settings#emails" className="app-button-primary">
              Manage preferences
            </Link>
            <Link href="/" className="app-button-secondary">
              Back to LoreVia
            </Link>
          </div>
        </section>
      </div>
    </main>
  )
}
