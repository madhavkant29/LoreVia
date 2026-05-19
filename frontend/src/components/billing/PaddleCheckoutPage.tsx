"use client"

import Link from "next/link"
import Script from "next/script"
import { useEffect, useMemo, useState } from "react"
import { useSearchParams } from "next/navigation"

import {
  buildPaddleCheckoutSettings,
  getBillingConfirmationToken,
  getPaddleClientToken,
  getPaddleEnvironment,
  getPaddleTransactionId,
  PADDLE_SCRIPT_SRC,
} from "@/lib/billing/paddle"

export function PaddleCheckoutPage() {
  const searchParams = useSearchParams()
  const paddleToken = getPaddleClientToken()
  const paddleEnvironment = getPaddleEnvironment(paddleToken)
  const transactionId = useMemo(() => getPaddleTransactionId(searchParams), [searchParams])
  const confirmationToken = useMemo(() => getBillingConfirmationToken(searchParams), [searchParams])
  const [scriptReady, setScriptReady] = useState(false)
  const [openedTransactionId, setOpenedTransactionId] = useState<string | null>(null)
  const [message, setMessage] = useState("Preparing secure checkout...")

  const openCheckout = () => {
    if (!transactionId) {
      setMessage("This checkout link is missing its Paddle transaction reference.")
      return
    }

    const paddle = window.Paddle
    if (!paddle) {
      setMessage("Paddle checkout did not load correctly. Refresh and try again.")
      return
    }

    try {
      paddle.Checkout.open({
        settings: buildPaddleCheckoutSettings(),
        transactionId,
      })
      setOpenedTransactionId(transactionId)
      setMessage("Secure checkout is open. Complete payment in the modal to continue.")
    } catch {
      setMessage("We could not open secure checkout right now. Refresh and try again.")
    }
  }

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

    if (!paddle.Initialized) {
      if (paddleEnvironment === "sandbox") {
        paddle.Environment.set("sandbox")
      }

      paddle.Initialize({
        token: paddleToken,
        pwCustomer: {},
        checkout: {
          settings: buildPaddleCheckoutSettings(),
        },
        eventCallback: (event) => {
          if (event.name === "checkout.closed") {
            setMessage("Checkout was closed. Use the button below to reopen it if you still want to continue.")
          }
          if (event.name === "checkout.completed") {
            const checkoutTransactionId =
              typeof event.data?.transaction_id === "string" ? event.data.transaction_id : transactionId
            if (checkoutTransactionId && typeof window !== "undefined") {
              const params = new URLSearchParams({ txn: checkoutTransactionId })
              if (confirmationToken) {
                params.set("confirmation_token", confirmationToken)
              }
              window.location.replace(`/checkout/success?${params.toString()}`)
              return
            }
            setMessage("Payment complete. LoreVia will finish access updates after the Paddle webhook is processed.")
          }
        },
      })
    }

    if (openedTransactionId !== transactionId) {
      openCheckout()
    }
  }, [confirmationToken, openedTransactionId, paddleEnvironment, paddleToken, scriptReady, transactionId])

  return (
    <>
      <Script
        src={PADDLE_SCRIPT_SRC}
        strategy="afterInteractive"
        onLoad={() => setScriptReady(true)}
        onError={() => setMessage("Paddle checkout could not be loaded. Refresh and try again.")}
      />
      <section className="mx-auto flex min-h-[70vh] w-full max-w-3xl flex-col justify-center px-6 py-16">
        <div className="rounded-[2rem] border border-white/[0.08] bg-[#0B0F14] p-8 text-[#F2F4F7] shadow-[0_30px_120px_rgba(0,0,0,0.35)]">
          <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-[#C9A86A]">Secure billing</p>
          <h1 className="mt-4 text-3xl font-semibold tracking-[-0.03em]">
            LoreVia checkout opens here for payment links, invoice links, and payment-method updates.
          </h1>
          <p className="mt-4 text-base leading-7 text-[#A8B0BA]">
            This page is the approved Paddle landing page for hosted checkout actions. If a valid transaction was passed in the link, the checkout overlay opens automatically.
          </p>

          <div className="mt-6 rounded-2xl border border-[#C9A86A]/30 bg-[#111720] px-5 py-4 text-sm leading-6 text-[#E7D3A8]">
            {message}
          </div>

          <div className="mt-8 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={openCheckout}
              className="inline-flex items-center justify-center rounded-lg border border-[#D2B47A] bg-[#D2B47A] px-5 py-3 text-sm font-semibold text-[#05070A] transition hover:bg-[#E5CA91]"
            >
              Open checkout again
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
