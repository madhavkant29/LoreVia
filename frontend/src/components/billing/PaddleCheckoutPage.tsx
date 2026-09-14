"use client"

import Link from "next/link"
import Script from "next/script"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useSearchParams } from "next/navigation"

import { capture } from "@/lib/analytics/posthog"
import { billingApi } from "@/lib/api/billing"
import {
  buildPaddleCheckoutSettings,
  getBillingConfirmationToken,
  getPaddleClientToken,
  getPaddleEnvironment,
  getPaddleTransactionId,
  PADDLE_SCRIPT_SRC,
  shouldAbandonClosedCheckout,
  type PaddleCheckoutEvent,
} from "@/lib/billing/paddle"

export function PaddleCheckoutPage({ nonce }: { nonce?: string }) {
  const searchParams = useSearchParams()
  const paddleToken = getPaddleClientToken()
  const paddleEnvironment = getPaddleEnvironment(paddleToken)
  const transactionId = useMemo(() => getPaddleTransactionId(searchParams), [searchParams])
  const confirmationToken = useMemo(() => getBillingConfirmationToken(searchParams), [searchParams])
  const [scriptReady, setScriptReady] = useState(false)
  const [openedTransactionId, setOpenedTransactionId] = useState<string | null>(null)
  const [checkoutAbandoned, setCheckoutAbandoned] = useState(false)
  const [message, setMessage] = useState("Preparing secure checkout...")
  const completedTransactionIdRef = useRef<string | null>(null)

  const openCheckout = useCallback(() => {
    if (checkoutAbandoned) {
      setMessage("This checkout was closed. Return to pricing to review current payment details and start a new checkout.")
      return
    }

    if (!transactionId) {
      capture("checkout_failed", { surface: "checkout_page", reason: "missing_transaction" })
      setMessage("This checkout link is missing its Paddle transaction reference.")
      return
    }

    const paddle = window.Paddle
    if (!paddle) {
      capture("checkout_failed", { surface: "checkout_page", reason: "paddle_unavailable" })
      setMessage("Paddle checkout did not load correctly. Refresh and try again.")
      return
    }

    try {
      completedTransactionIdRef.current = null
      capture("checkout_started", {
        surface: "checkout_page",
        transaction_id: transactionId,
      })
      paddle.Checkout.open({
        settings: buildPaddleCheckoutSettings(),
        transactionId,
      })
      setOpenedTransactionId(transactionId)
      setMessage("Secure checkout is open. Complete payment in the modal to continue.")
    } catch {
      capture("checkout_failed", {
        surface: "checkout_page",
        reason: "overlay_open_failed",
        transaction_id: transactionId,
      })
      setMessage("We could not open secure checkout right now. Refresh and try again.")
    }
  }, [checkoutAbandoned, transactionId])

  useEffect(() => {
    if (!scriptReady) return

    if (!paddleToken || !paddleEnvironment) {
      setMessage("Paddle checkout is not configured for this environment yet.")
      return
    }

    const paddle = window.Paddle
    if (!paddle) {
      setMessage("Paddle checkout did not load correctly. Refresh and try again.")
      return
    }

    const eventCallback = (event: PaddleCheckoutEvent) => {
      if (event.name === "checkout.closed") {
        const closedTransactionId =
          typeof event.data?.transaction_id === "string" ? event.data.transaction_id : transactionId
        capture("checkout_closed", {
          surface: "checkout_page",
          transaction_id: closedTransactionId,
        })
        setMessage("Checkout was closed. Use the button below to reopen it if you still want to continue.")
        if (
          confirmationToken &&
          shouldAbandonClosedCheckout(closedTransactionId, completedTransactionIdRef.current)
        ) {
          void billingApi
            .abandonCheckout(closedTransactionId)
            .then(() => {
              setCheckoutAbandoned(true)
              setMessage(
                "Checkout was closed and the pending payment was canceled. Return to pricing to review current payment details before starting again.",
              )
            })
            .catch(() => {
              capture("checkout_abandon_failed", {
                surface: "checkout_page",
                transaction_id: closedTransactionId,
              })
              setMessage(
                "Checkout was closed, but we could not confirm that the pending payment was canceled. Wait a moment or return to pricing before trying again.",
              )
            })
        }
      }
      if (event.name === "checkout.completed") {
        const checkoutTransactionId =
          typeof event.data?.transaction_id === "string" ? event.data.transaction_id : transactionId
        capture("checkout_completed", {
          surface: "checkout_page",
          transaction_id: checkoutTransactionId,
        })
        if (checkoutTransactionId && typeof window !== "undefined") {
          completedTransactionIdRef.current = checkoutTransactionId
          const params = new URLSearchParams({ txn: checkoutTransactionId })
          if (confirmationToken) {
            params.set("confirmation_token", confirmationToken)
          }
          window.location.replace(`/checkout/success?${params.toString()}`)
          return
        }
        setMessage("Payment complete. LoreVia will finish access updates after the Paddle webhook is processed.")
      }
    }

    if (paddle.Initialized) {
      paddle.Update?.({ eventCallback })
    } else {
      if (paddleEnvironment === "sandbox") {
        paddle.Environment.set("sandbox")
      }

      paddle.Initialize({
        token: paddleToken,
        pwCustomer: {},
        checkout: {
          settings: buildPaddleCheckoutSettings(),
        },
        eventCallback,
      })
    }

    if (openedTransactionId !== transactionId) {
      openCheckout()
    }
  }, [
    checkoutAbandoned,
    confirmationToken,
    openedTransactionId,
    openCheckout,
    paddleEnvironment,
    paddleToken,
    scriptReady,
    transactionId,
  ])

  return (
    <>
      <Script
        src={PADDLE_SCRIPT_SRC}
        strategy="afterInteractive"
        nonce={nonce}
        onLoad={() => setScriptReady(true)}
        onError={() => setMessage("Paddle checkout could not be loaded. Refresh and try again.")}
      />
      <section className="mx-auto flex min-h-[70vh] w-full max-w-3xl flex-col justify-center px-6 py-16">
        <div className="rounded-lg border border-white/[0.08] bg-[#0B0F14] p-8 text-[#F2F4F7]">
          <p className="text-3xs font-semibold uppercase tracking-[0.28em] text-[#C9A86A]">Secure billing</p>
          <h1 className="mt-4 text-3xl font-semibold tracking-[-0.03em]">
            LoreVia checkout opens here for payment links, invoice links, and payment-method updates.
          </h1>
          <p className="mt-4 text-base leading-7 text-[#A8B0BA]">
            This page is the approved Paddle landing page for hosted checkout actions. If a valid transaction was passed in the link, the checkout overlay opens automatically.
          </p>

          <div className="mt-6 rounded-md border border-[#C9A86A]/30 bg-[#111720] px-5 py-4 text-sm leading-6 text-[#E7D3A8]">
            {message}
          </div>

          <div className="mt-8 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={openCheckout}
              disabled={checkoutAbandoned}
              className="inline-flex items-center justify-center rounded-lg border border-[#D2B47A] bg-[#D2B47A] px-5 py-3 text-sm font-semibold text-[#05070A] transition hover:bg-[#E5CA91]"
            >
              {checkoutAbandoned ? "Checkout closed" : "Open checkout again"}
            </button>
            <Link
              href="/pricing"
              className="inline-flex items-center justify-center rounded-lg border border-white/[0.12] px-5 py-3 text-sm font-semibold text-[#F2F4F7] transition hover:border-[#C9A86A]/45"
            >
              View pricing
            </Link>
          </div>
        </div>
      </section>
    </>
  )
}
