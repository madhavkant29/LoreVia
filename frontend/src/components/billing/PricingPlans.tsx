"use client"

import Script from "next/script"
import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"

import { billingApi } from "@/lib/api/billing"
import {
  getBillingConfirmationTokenFromCheckoutUrl,
  buildPaddleCheckoutSettings,
  getPaddleClientToken,
  getPaddleEnvironment,
  getTransactionIdFromCheckoutUrl,
  PADDLE_SCRIPT_SRC,
} from "@/lib/billing/paddle"
import {
  pricingTierAccessLabel,
  pricingTierAnnualSavings,
  pricingTierGuestCtaLabel,
  pricingTierPrice,
  pricingTierPriceSuffix,
  pricingTiers,
  type BillingCycle,
  type PricingTier,
} from "@/lib/billing/catalog"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

type PricingPlansProps = {
  nonce?: string
  surface?: "public" | "app"
}

export function PricingPlans({ nonce, surface = "public" }: PricingPlansProps) {
  const router = useRouter()
  const { user } = useAuthStore()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const paddleToken = getPaddleClientToken()
  const paddleEnvironment = getPaddleEnvironment(paddleToken)
  const [billingCycle, setBillingCycle] = useState<BillingCycle>("monthly")
  const [busyPlan, setBusyPlan] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [paddleReady, setPaddleReady] = useState(false)
  const pendingConfirmationTokenRef = useRef<string | null>(null)

  function redirectToSuccess(transactionId: string, confirmationToken: string | null) {
    const params = new URLSearchParams({ txn: transactionId })
    if (confirmationToken) {
      params.set("confirmation_token", confirmationToken)
    }
    window.location.replace(`/checkout/success?${params.toString()}`)
  }

  useEffect(() => {
    if (!paddleReady || !paddleToken || !paddleEnvironment || typeof window === "undefined") {
      return
    }

    const paddle = window.Paddle
    if (!paddle || paddle.Initialized) {
      return
    }

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
        if (event.name === "checkout.completed") {
          const transactionId = typeof event.data?.transaction_id === "string" ? event.data.transaction_id : null
          if (transactionId) {
            redirectToSuccess(transactionId, pendingConfirmationTokenRef.current)
          }
        }
      },
    })
  }, [paddleEnvironment, paddleReady, paddleToken])

  async function handlePlanClick(tier: PricingTier) {
    if (tier.access === "free") {
      if (!user) {
        router.push("/register")
        return
      }

      setMessage("Free is included with every account. Paid checkout only applies to Author and Architect.")
      return
    }

    if (!user) {
      router.push("/register")
      return
    }

    const selectedPlanCode = billingCycle === "annual" ? tier.annualCode : tier.monthlyCode
    if (!selectedPlanCode) {
      setMessage(tier.message ?? `${tier.name} cannot be started from this page yet.`)
      return
    }

    setBusyPlan(selectedPlanCode)
    setMessage(null)
    try {
      const result = await billingApi.checkout(selectedPlanCode)
      if (!result.billing_enabled || !result.checkout_url) {
        setMessage(result.message ?? "Billing is not configured in this environment yet.")
        return
      }
      const transactionId = getTransactionIdFromCheckoutUrl(result.checkout_url)
      const confirmationToken = getBillingConfirmationTokenFromCheckoutUrl(result.checkout_url)
      pendingConfirmationTokenRef.current = confirmationToken
      if (paddleReady && paddleToken && paddleEnvironment && transactionId && window.Paddle?.Initialized) {
        window.Paddle.Checkout.open({
          settings: buildPaddleCheckoutSettings(),
          transactionId,
        })
        return
      }
      window.location.href = result.checkout_url
    } catch {
      setMessage("We could not start checkout right now. Please try again in a moment.")
    } finally {
      setBusyPlan(null)
    }
  }

  const helperCopy = user
    ? "Free is already included in your account. Only Author and Architect start paid checkout from this screen."
    : surface === "public"
      ? "Free is included with every account. Sign in to upgrade to a paid plan."
      : "Free is included with every account. Sign in to upgrade to a paid plan."

  const sectionTitleClass = isDark ? "text-[#73b1a7]" : "text-[#1f615d]"
  const bodyCopyClass = isDark ? "text-slate-300" : "text-stone-600"
  const shellCardClass = isDark ? "border-white/[0.08] bg-[#151c23]" : "border-[#d9e1e6] bg-white"
  const noticeClass = isDark ? "border-white/[0.12] bg-white/[0.02] text-slate-200" : "border-[#d9e1e6] bg-white text-stone-800"
  const toggleShellClass = isDark ? "border-white/[0.12] bg-[#141a21]" : "border-[#d9e1e6] bg-white"
  const messageClass = isDark ? "border-[#4a6f6b] bg-[#173431] text-[#d4f1ec]" : "border-teal-800/20 bg-teal-800/6 text-teal-900"

  return (
    <>
      <Script
        src={PADDLE_SCRIPT_SRC}
        strategy="afterInteractive"
        nonce={nonce}
        onLoad={() => setPaddleReady(true)}
      />

      <section className={surface === "public" ? "" : undefined}>
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <h2 className={`font-display text-[2rem] tracking-[-0.03em] ${sectionTitleClass}`}>
              Plans for fiction authors and complex story worlds
            </h2>
            <p className={`mt-2 text-[1rem] leading-7 ${bodyCopyClass}`}>{helperCopy}</p>
          </div>

          <div className="flex flex-col items-start gap-3 lg:items-end">
            <div className={`inline-flex w-fit items-center rounded-full border p-1.5 ${toggleShellClass}`}>
              {(["monthly", "annual"] as const).map((cycle) => (
                <button
                  key={cycle}
                  type="button"
                  onClick={() => setBillingCycle(cycle)}
                  className={`rounded-full px-6 py-2.5 text-sm font-semibold transition ${
                    billingCycle === cycle
                      ? isDark
                        ? "bg-[#1f615d] text-white"
                        : "bg-[#1f615d] text-white"
                      : isDark
                        ? "text-slate-300 hover:text-white"
                        : "text-stone-500 hover:text-stone-950"
                  }`}
                >
                  {cycle === "annual" ? "Yearly" : "Monthly"}
                </button>
              ))}
            </div>
            {billingCycle === "annual" ? (
              <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Save more with yearly billing.</p>
            ) : (
              <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Cancel anytime.</p>
            )}
          </div>
        </div>

        <div className={`mt-7 rounded-[1.1rem] border px-5 py-4 ${noticeClass}`}>
          <div className="flex items-start gap-3">
            <span className={`mt-0.5 ${isDark ? "text-slate-300" : "text-[#1f615d]"}`} aria-hidden="true">
              <InfoIcon />
            </span>
            <div>
              <p className="text-sm font-semibold">Every new account starts with 10 days of Author access and no credit card.</p>
              <p className={`mt-1 text-sm leading-7 ${isDark ? "text-slate-400" : "text-stone-600"}`}>
                After that, you keep the Free plan unless you choose a paid subscription for ongoing continuity and manuscript work.
              </p>
            </div>
          </div>
        </div>

        {message ? (
          <div className={`mt-6 rounded-[1rem] border px-4 py-3 text-sm leading-6 ${messageClass}`}>
            {message}
          </div>
        ) : null}

        <div className="mt-6 grid gap-4 xl:grid-cols-3">
          {pricingTiers.map((tier) => {
            const price = pricingTierPrice(tier, billingCycle)
            const unit = pricingTierPriceSuffix(tier, billingCycle)
            const savings = billingCycle === "annual" ? pricingTierAnnualSavings(tier) : 0
            const selectedPlanCode = billingCycle === "annual" ? tier.annualCode : tier.monthlyCode
            const isBusy = selectedPlanCode ? busyPlan === selectedPlanCode : false
            const buttonLabel = user ? tier.cta : pricingTierGuestCtaLabel(tier)

            const cardClass = isDark ? "border-white/[0.12] bg-[#131920]" : "border-[#d9e1e6] bg-white"
            const highlightClass = tier.highlight
              ? isDark
                ? "border-[#4ba391] shadow-[0_0_0_1px_rgba(75,163,145,0.28)]"
                : "border-[#2b7a73] shadow-[0_0_0_1px_rgba(43,122,115,0.18)]"
              : ""
            const priceCopyClass = isDark ? "text-white" : "text-stone-950"
            const textCopyClass = isDark ? "text-slate-300" : "text-stone-700"
            const subCopyClass = isDark ? "text-slate-400" : "text-stone-500"
            const buttonClass = tier.highlight
              ? "border-transparent bg-[linear-gradient(90deg,#5cb89d,#78d6be)] text-slate-950 hover:opacity-95"
              : isDark
                ? "border-white/[0.18] bg-transparent text-white hover:bg-white/[0.05]"
                : "border-[#2b7a73] bg-white text-[#1f615d] hover:bg-[#f5fbfa]"

            return (
              <article
                key={tier.name}
                className={`relative flex min-h-[42rem] flex-col rounded-[1.35rem] border p-6 ${cardClass} ${highlightClass}`.trim()}
              >
                {tier.highlight ? (
                  <div className="absolute inset-x-0 -top-0.5 flex justify-center">
                    <span className={`rounded-b-xl px-5 py-1.5 text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "bg-[#24544d] text-[#d3f2ec]" : "bg-[#1f615d] text-white"}`}>
                      Recommended
                    </span>
                  </div>
                ) : null}

                <div className={`flex items-start justify-between gap-4 ${tier.highlight ? "pt-4" : ""}`}>
                  <div>
                    <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-[#7ec8b7]" : "text-[#1f615d]"}`}>{tier.badge}</p>
                    <h3 className={`mt-4 font-display text-[2.15rem] tracking-[-0.04em] ${priceCopyClass}`}>{tier.name}</h3>
                  </div>
                  {tier.highlight ? (
                    <span className={`pt-7 text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-[#7ec8b7]" : "text-[#1f615d]"}`}>
                      Core plan
                    </span>
                  ) : null}
                </div>

                <p className={`mt-4 text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-[#7ec8b7]" : "text-[#1f615d]"}`}>
                  {pricingTierAccessLabel(tier)}
                </p>

                <div className="mt-4 min-h-[7.25rem]">
                  <p className={`text-[1rem] leading-8 ${textCopyClass}`}>{tier.subtitle}.</p>
                </div>

                <div className={`mt-2 border-t pt-6 ${isDark ? "border-white/[0.12]" : "border-[#e4e7eb]"}`}>
                  <div className="flex items-end gap-2">
                    <span className={`font-display text-[4rem] leading-none tracking-[-0.06em] ${priceCopyClass}`}>
                      {tier.name === "Free" ? "$0" : `$${price}`}
                    </span>
                    {unit ? <span className={`pb-2 text-base ${subCopyClass}`}>{unit}</span> : null}
                  </div>
                  {savings > 0 ? (
                    <p className={`mt-2 text-sm ${isDark ? "text-[#7ec8b7]" : "text-[#1f615d]"}`}>Save ${savings} with yearly billing</p>
                  ) : (
                    <div className="mt-2 h-5" aria-hidden="true" />
                  )}
                </div>

                <ul className={`mt-6 flex-1 space-y-3 text-[0.98rem] leading-7 ${textCopyClass}`}>
                  {tier.bullets.map((bullet) => (
                    <li key={bullet} className="flex items-start gap-3">
                      <span className={`mt-[5px] ${isDark ? "text-[#7ec8b7]" : "text-[#1f615d]"}`} aria-hidden="true">
                        <CheckIcon />
                      </span>
                      <span className={bullet.startsWith("Everything in") ? subCopyClass : undefined}>{bullet}</span>
                    </li>
                  ))}
                </ul>

                <div className="mt-8">
                  <button
                    type="button"
                    onClick={() => void handlePlanClick(tier)}
                    disabled={isBusy}
                    className={`inline-flex w-full items-center justify-center rounded-[0.9rem] border px-4 py-3.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${buttonClass}`}
                  >
                    {isBusy ? "Opening checkout..." : buttonLabel}
                  </button>
                  {tier.access === "paid" ? (
                    <p className={`mt-3 text-center text-sm ${subCopyClass}`}>
                      {billingCycle === "annual" ? `Billed yearly at $${price}/yr` : `10 days free, then $${price}/mo`}
                    </p>
                  ) : null}
                </div>
              </article>
            )
          })}
        </div>

        <div className="mt-8 text-center">
          <p className={`text-[0.98rem] leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
            Only Author and Architect are paid subscriptions. Free stays available without checkout.
          </p>
          <p className={`mt-2 text-[0.98rem] leading-7 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
            Worldbuilding manuscripts count as uploads on every tier. On Author, a series-linked worldbuilding manuscript counts once per book in that series. Architect remains unlimited.
          </p>
        </div>
      </section>
    </>
  )
}

function InfoIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <circle cx="12" cy="12" r="9" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 10v5M12 7.25h.01" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 12.5l4.2 4.2L19 7.5" />
    </svg>
  )
}
