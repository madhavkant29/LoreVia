"use client"

import Script from "next/script"
import { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"

import { Dialog } from "@/components/ui/Dialog"
import { billingApi, type BillingCheckoutPreview, type BillingSubscription } from "@/lib/api/billing"
import { capture } from "@/lib/analytics/posthog"
import {
  getBillingConfirmationTokenFromCheckoutUrl,
  buildPaddleCheckoutSettings,
  getPaddleClientToken,
  getPaddleEnvironment,
  getTransactionIdFromCheckoutUrl,
  PADDLE_SCRIPT_SRC,
  shouldAbandonClosedCheckout,
  type PaddleCheckoutEvent,
} from "@/lib/billing/paddle"
import {
  pricingTierAnnualSavings,
  pricingTierGuestCtaLabel,
  pricingTierPrice,
  pricingTierPriceSuffix,
  pricingTiers,
  type BillingCycle,
  type PricingTier,
} from "@/lib/billing/catalog"
import { SUPPORT_EMAIL } from "@/lib/constants/contact"
import { tierLabel } from "@/lib/billing/plans"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { getApiErrorDetail } from "@/lib/utils/apiErrors"

type PricingPlansProps = {
  nonce?: string
  surface?: "public" | "app"
}

export function PricingPageIntro() {
  return (
    <div className="max-w-3xl">
      <p className="text-xs font-semibold text-[#1f615d]">Plans and billing</p>
      <h1 className="mt-3 font-display text-[2.75rem] leading-[0.98] tracking-[-0.045em] text-foreground sm:text-[3.75rem]">
        Choose the plan that matches your work
      </h1>
    </div>
  )
}

export function PricingPlans({ nonce, surface = "public" }: PricingPlansProps) {
  const router = useRouter()
  const { user, hydrated: authHydrated } = useAuthStore()
  // Keep the first render identical on the server and client. The auth store
  // can have a cached browser user before the session has been confirmed.
  const stableUser = authHydrated ? user : null
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const paddleToken = getPaddleClientToken()
  const paddleEnvironment = getPaddleEnvironment(paddleToken)
  const [billingCycle, setBillingCycle] = useState<BillingCycle>("monthly")
  const [busyPlan, setBusyPlan] = useState<string | null>(null)
  const [billingPortalBusy, setBillingPortalBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [paddleReady, setPaddleReady] = useState(false)
  const [checkoutPreview, setCheckoutPreview] = useState<BillingCheckoutPreview | null>(null)
  const [chargeConfirmed, setChargeConfirmed] = useState(false)
  const [checkoutError, setCheckoutError] = useState<string | null>(null)
  const [subscriptionState, setSubscriptionState] = useState<BillingSubscription | null>(null)
  const pendingConfirmationTokenRef = useRef<string | null>(null)
  const pendingTransactionIdRef = useRef<string | null>(null)
  const completedTransactionIdRef = useRef<string | null>(null)
  const promptViewedRef = useRef(false)
  const checkoutCancelRef = useRef<HTMLButtonElement | null>(null)

  useEffect(() => {
    if (promptViewedRef.current) return
    promptViewedRef.current = true
    capture("upgrade_prompt_viewed", { surface })
  }, [surface])

  useEffect(() => {
    if (!stableUser) {
      setSubscriptionState(null)
      return
    }
    let cancelled = false
    void billingApi
      .subscription()
      .then((state) => {
        if (!cancelled) setSubscriptionState(state)
      })
      .catch(() => {
        if (!cancelled) setSubscriptionState(null)
      })
    return () => {
      cancelled = true
    }
  }, [stableUser])

  function redirectToSuccess(transactionId: string, confirmationToken: string | null) {
    const params = new URLSearchParams({ txn: transactionId })
    if (confirmationToken) {
      params.set("confirmation_token", confirmationToken)
    }
    window.location.replace(`/checkout/success?${params.toString()}`)
  }

  function closeCheckoutPreview() {
    const returnToLibrary = Boolean(checkoutPreview?.trial_active)
    setCheckoutPreview(null)
    setChargeConfirmed(false)
    setCheckoutError(null)
    if (returnToLibrary) router.push("/library")
  }

  useEffect(() => {
    if (!paddleReady || !paddleToken || !paddleEnvironment || typeof window === "undefined") {
      return
    }

    const paddle = window.Paddle
    if (!paddle) return

    const eventCallback = (event: PaddleCheckoutEvent) => {
      if (event.name === "checkout.closed") {
        capture("checkout_closed", { surface, billing_cycle: billingCycle })
        const transactionId =
          typeof event.data?.transaction_id === "string"
            ? event.data.transaction_id
            : pendingTransactionIdRef.current
        if (shouldAbandonClosedCheckout(transactionId, completedTransactionIdRef.current)) {
          void billingApi.abandonCheckout(transactionId).catch(() => {
            capture("checkout_abandon_failed", { surface, transaction_id: transactionId })
          })
        }
        pendingTransactionIdRef.current = null
        pendingConfirmationTokenRef.current = null
      }
      if (event.name === "checkout.completed") {
        const transactionId = typeof event.data?.transaction_id === "string" ? event.data.transaction_id : null
        capture("checkout_completed", {
          surface,
          billing_cycle: billingCycle,
          transaction_id: transactionId,
        })
        if (transactionId) {
          completedTransactionIdRef.current = transactionId
          redirectToSuccess(transactionId, pendingConfirmationTokenRef.current)
        }
      }
    }

    if (paddle.Initialized) {
      paddle.Update?.({ eventCallback })
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
      eventCallback,
    })
  }, [billingCycle, paddleEnvironment, paddleReady, paddleToken, surface])

  async function handlePlanClick(tier: PricingTier) {
    if (tier.access === "free") {
      if (!stableUser) {
        router.push("/register")
        return
      }

      setMessage("Free is included with every account. Paid checkout only applies to Author and Architect.")
      return
    }

    if (!stableUser) {
      capture("upgrade_prompt_clicked", {
        surface,
        plan: tier.key,
        billing_cycle: billingCycle,
        destination: "register",
      })
      router.push("/register")
      return
    }

    if (isPaidSubscriber) {
      await openBillingPortal()
      return
    }

    capture("upgrade_prompt_clicked", {
      surface,
      plan: tier.key,
      billing_cycle: billingCycle,
      destination: "checkout",
    })
    const selectedPlanCode = billingCycle === "annual" ? tier.annualCode : tier.monthlyCode
    capture("pricing_plan_selected", {
      surface,
      plan: tier.key,
      billing_cycle: billingCycle,
      plan_code: selectedPlanCode,
    })
    if (!selectedPlanCode) {
      setMessage(tier.message ?? `${tier.name} cannot be started from this page yet.`)
      return
    }

    setBusyPlan(selectedPlanCode)
    setMessage(null)
    setCheckoutError(null)
    try {
      const preview = await billingApi.checkoutPreview(selectedPlanCode)
      if (!preview.billing_enabled) {
        capture("checkout_failed", {
          surface,
          plan: tier.key,
          billing_cycle: billingCycle,
          reason: "billing_unavailable",
        })
        setMessage(preview.message ?? "Billing is not configured in this environment yet.")
        return
      }
      setChargeConfirmed(false)
      setCheckoutError(null)
      setCheckoutPreview(preview)
    } catch (error) {
      capture("checkout_failed", {
        surface,
        plan: tier.key,
        billing_cycle: billingCycle,
        reason: "checkout_preview_failed",
      })
      setMessage(getApiErrorDetail(error) ?? "We could not verify your billing status right now. Please try again in a moment.")
    } finally {
      setBusyPlan(null)
    }
  }

  async function openBillingPortal() {
    setBillingPortalBusy(true)
    setMessage(null)
    try {
      const result = await billingApi.portal()
      if (!result.billing_enabled || !result.portal_url) {
        setMessage(result.message ?? "Billing is not configured in this environment yet.")
        return
      }
      window.location.href = result.portal_url
    } catch (error) {
      setMessage(getApiErrorDetail(error) ?? "We could not open the billing portal right now. Please try again in a moment.")
    } finally {
      setBillingPortalBusy(false)
    }
  }

  async function confirmPaidCheckout() {
    if (!checkoutPreview) return
    if (checkoutPreview.confirmation_required && !chargeConfirmed) return

    setBusyPlan(checkoutPreview.plan)
    setCheckoutError(null)
    capture("checkout_started", {
      surface,
      plan: checkoutPreview.display_name.toLowerCase(),
      billing_cycle: checkoutPreview.billing_interval,
      plan_code: checkoutPreview.plan,
      immediate_charge_confirmed: chargeConfirmed,
    })
    try {
      const result = await billingApi.checkout(
        checkoutPreview.plan,
        chargeConfirmed,
        checkoutPreview.quote_token,
      )
      if (!result.billing_enabled || !result.checkout_url) {
        capture("checkout_failed", {
          surface,
          plan: checkoutPreview.display_name.toLowerCase(),
          billing_cycle: checkoutPreview.billing_interval,
          reason: "billing_unavailable",
        })
        setCheckoutError(result.message ?? "Billing is not configured in this environment yet.")
        return
      }
      const transactionId = getTransactionIdFromCheckoutUrl(result.checkout_url)
      const confirmationToken = getBillingConfirmationTokenFromCheckoutUrl(result.checkout_url)
      pendingConfirmationTokenRef.current = confirmationToken
      pendingTransactionIdRef.current = transactionId
      completedTransactionIdRef.current = null
      if (paddleReady && paddleToken && paddleEnvironment && transactionId && window.Paddle?.Initialized) {
        window.Paddle.Checkout.open({
          settings: buildPaddleCheckoutSettings(),
          transactionId,
        })
        setCheckoutPreview(null)
        return
      }
      setCheckoutPreview(null)
      window.location.href = result.checkout_url
    } catch (error) {
      capture("checkout_failed", {
        surface,
        plan: checkoutPreview.display_name.toLowerCase(),
        billing_cycle: checkoutPreview.billing_interval,
        reason: "checkout_request_failed",
      })
      setCheckoutError(getApiErrorDetail(error) ?? "We could not start checkout right now. Please try again in a moment.")
    } finally {
      setBusyPlan(null)
    }
  }

  const helperCopy = stableUser
    ? stableUser.trial_active
      ? "Your free trial is already active. It does not require payment and will not turn into a paid subscription automatically."
      : "Free is included with your account. Upgrade to Author or Architect to unlock more."
    : surface === "public"
      ? "Free is included with every account. Sign in to upgrade to a paid plan."
      : "Free is included with every account. Sign in to upgrade to a paid plan."

  const isPaidSubscriber = Boolean(
    stableUser && !stableUser.trial_active && (stableUser.plan_tier === "author" || stableUser.plan_tier === "architect"),
  )
  const activePlanLabel = stableUser?.trial_active
    ? "Author — temporary trial access"
    : stableUser
      ? tierLabel(stableUser.plan_tier)
      : null
  const subscriptionDisplayState = subscriptionState?.display_state
  const subscriptionPlanLabel = tierLabel(subscriptionState?.plan_tier ?? stableUser?.plan_tier)
  const subscriptionPriceLabel = subscriptionState
    ? `$${subscriptionState.price.amount}${subscriptionState.price.interval === "year" ? "/year" : "/month"}`
    : null
  const subscriptionRenewalLabel = subscriptionState?.next_charge_at
    ? formatBillingDate(subscriptionState.next_charge_at)
    : null
  const subscriptionEndLabel = subscriptionState?.current_period_end
    ? formatBillingDate(subscriptionState.current_period_end)
    : null
  const paidSubscriptionCopy =
    subscriptionDisplayState === "cancellation_scheduled"
      ? `Cancellation scheduled. Your ${subscriptionPlanLabel} plan remains active until ${subscriptionEndLabel ?? "the end of the current billing period"}. You won't be charged again.`
      : subscriptionDisplayState === "past_due"
        ? "Payment issue. Update your billing details in the portal to keep your plan active. Paddle may retry the payment automatically."
        : subscriptionRenewalLabel && subscriptionPriceLabel
          ? `${subscriptionPlanLabel} — ${subscriptionPriceLabel}. Next renewal ${subscriptionRenewalLabel}. Your subscription renews automatically until canceled.`
          : "Manage cancellation, payment details, invoices, and plan changes in the billing portal. Refund requests are reviewed by support."
  const refundRequestHref = `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent("LoreVia refund request")}`

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
            <p className={`mt-2 text-[1rem] leading-7 ${bodyCopyClass}`}>{helperCopy}</p>
          </div>

          <div className="flex flex-col items-start gap-3 lg:items-end">
            <div
              className={`inline-flex w-fit items-center rounded-md border p-1 ${toggleShellClass}`}
              role="group"
              aria-label="Billing cadence"
            >
              {(["monthly", "annual"] as const).map((cycle) => (
                <button
                  key={cycle}
                  type="button"
                  aria-pressed={billingCycle === cycle}
                  onClick={() => {
                    setBillingCycle(cycle)
                    capture("billing_cadence_selected", { surface, billing_cycle: cycle })
                  }}
                  className={`rounded-sm px-6 py-2.5 text-sm font-semibold transition ${
                    billingCycle === cycle
                      ? isDark
                        ? "bg-[#1f615d] text-white"
                        : "bg-[#1f615d] text-white"
                      : isDark
                        ? "text-slate-300 hover:text-white"
                        : "text-stone-600 hover:text-stone-950"
                  }`}
                >
                  {cycle === "annual" ? "Yearly" : "Monthly"}
                </button>
              ))}
            </div>
            {billingCycle === "annual" ? (
              <p className={`text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>Get two months free with yearly billing.</p>
            ) : (
              <p className={`text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>Cancel anytime.</p>
            )}
          </div>
        </div>

        <div className={`mt-7 border-y px-1 py-4 ${noticeClass}`}>
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

        {stableUser?.trial_active ? (
          <div className={`mt-4 border-y px-1 py-4 ${messageClass}`} role="status">
            <p className="text-sm font-semibold">Your free trial is already active.</p>
            <p className="mt-1 text-sm leading-7">
              {stableUser.trial_ends_at
                ? `It ends on ${formatTrialEndDate(stableUser.trial_ends_at)}. No payment is scheduled when it ends.`
                : "No payment is scheduled when it ends."}
            </p>
            <button
              type="button"
              onClick={() => router.push("/library")}
              className="mt-3 rounded-sm bg-[#1f615d] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#174c49]"
            >
              Continue free trial
            </button>
          </div>
        ) : null}

        {stableUser && activePlanLabel ? (
          <section
            aria-labelledby="current-plan-heading"
            className={`mt-4 border-y px-1 py-4 ${noticeClass}`}
          >
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-[#7ec8b7]" : "text-[#1f615d]"}`}>
                  Your current plan
                </p>
                <h3 id="current-plan-heading" className={`mt-2 text-lg font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>
                  {activePlanLabel}
                </h3>
                {stableUser.trial_active ? (
                  <p className={`mt-1 text-sm leading-6 ${bodyCopyClass}`}>
                    This is temporary Author access. A payment method is not required for the trial, and there is no subscription to cancel or refund.
                  </p>
                ) : isPaidSubscriber ? (
                  <p className={`mt-1 text-sm leading-6 ${bodyCopyClass}`}>
                    {paidSubscriptionCopy}
                  </p>
                ) : (
                  <p className={`mt-1 text-sm leading-6 ${bodyCopyClass}`}>
                    Free is included with your account. Choose a paid plan only when you are ready to subscribe.
                  </p>
                )}
              </div>

              {isPaidSubscriber ? (
                <div className="flex flex-wrap items-center gap-3 lg:justify-end">
                  <button
                    type="button"
                    onClick={() => void openBillingPortal()}
                    disabled={billingPortalBusy}
                    className="rounded-sm bg-[#1f615d] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#174c49] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {billingPortalBusy ? "Opening billing..." : "Manage subscription"}
                  </button>
                  <a href="/refund" className={`text-sm font-semibold underline underline-offset-4 ${isDark ? "text-[#9ed9cf]" : "text-[#1f615d]"}`}>
                    Refund policy
                  </a>
                  <a href={refundRequestHref} className={`text-sm font-semibold underline underline-offset-4 ${isDark ? "text-[#9ed9cf]" : "text-[#1f615d]"}`}>
                    Request a refund
                  </a>
                </div>
              ) : null}
            </div>
          </section>
        ) : null}

        {message ? (
          <div className={`mt-6 border-y px-1 py-3 text-sm leading-6 ${messageClass}`}>
            {message}
          </div>
        ) : null}

        <div className={`mt-6 grid overflow-hidden border xl:grid-cols-3 ${isDark ? "border-white/[0.12]" : "border-[#d9e1e6]"}`}>
          {pricingTiers.map((tier) => {
            const price = pricingTierPrice(tier, billingCycle)
            const unit = pricingTierPriceSuffix(tier, billingCycle)
            const savings = billingCycle === "annual" ? pricingTierAnnualSavings(tier) : 0
            const selectedPlanCode = billingCycle === "annual" ? tier.annualCode : tier.monthlyCode
            const isBusy = selectedPlanCode ? busyPlan === selectedPlanCode : false
            const buttonLabel = stableUser
              ? isPaidSubscriber && tier.access === "paid"
                ? tier.key === stableUser.plan_tier
                  ? "Current plan — manage"
                  : "Manage subscription"
                : stableUser.trial_active && tier.access === "paid"
                ? "View payment details"
                : tier.cta
              : pricingTierGuestCtaLabel(tier)

            const cardClass = isDark ? "border-white/[0.12] bg-[#131920]" : "border-[#d9e1e6] bg-white"
            const highlightClass = tier.highlight
              ? isDark
                ? "border-[#4ba391]"
                : "border-[#2b7a73]"
              : ""
            const priceCopyClass = isDark ? "text-white" : "text-stone-950"
            const textCopyClass = isDark ? "text-slate-300" : "text-stone-700"
            const subCopyClass = isDark ? "text-slate-400" : "text-stone-500"
            const planMarker = isPaidSubscriber && tier.key === stableUser?.plan_tier
              ? "Current plan"
              : tier.highlight
                ? "Recommended"
                : null
            const buttonClass = tier.highlight
              ? "border-transparent bg-[#1f615d] text-white hover:bg-[#174c49]"
              : isDark
                ? "border-white/[0.18] bg-transparent text-white hover:bg-white/[0.05]"
                : "border-[#2b7a73] bg-white text-[#1f615d] hover:bg-[#f5fbfa]"

            return (
              <article
                key={tier.name}
                className={`relative flex min-w-0 flex-col border-b p-6 last:border-b-0 xl:border-b-0 xl:border-r xl:last:border-r-0 ${cardClass} ${highlightClass}`.trim()}
              >
                <div className="flex min-h-12 items-start justify-between gap-4">
                  <h3 className={`font-display text-[2.15rem] tracking-[-0.04em] ${priceCopyClass}`}>{tier.name}</h3>
                  {planMarker ? (
                    <span className={`border px-2.5 py-1 text-xs font-semibold ${isDark ? "border-[#4ba391] text-[#9ed9cf]" : "border-[#2b7a73] text-[#1f615d]"}`}>
                      {planMarker}
                    </span>
                  ) : null}
                </div>

                <div className="mt-3 min-h-[6.5rem]">
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

                <ul className={`mt-6 flex-1 divide-y text-[0.94rem] leading-6 ${isDark ? "divide-white/[0.08]" : "divide-[#e4e7eb]"} ${textCopyClass}`}>
                  {tier.bullets.map((bullet) => (
                    <li key={bullet} className="flex items-start gap-3 py-2.5 first:pt-0">
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
                    disabled={isBusy || billingPortalBusy}
                    className={`inline-flex w-full items-center justify-center rounded-sm border px-4 py-3.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${buttonClass}`}
                  >
                    {isBusy ? "Opening checkout..." : billingPortalBusy && isPaidSubscriber && tier.access === "paid" ? "Opening billing..." : buttonLabel}
                  </button>
                  {tier.access === "paid" ? (
                    <p className={`mt-3 text-center text-sm ${subCopyClass}`}>
                      {stableUser?.trial_active
                        ? `Choosing this paid plan charges $${price} now. Your free trial does not auto-convert.`
                        : `Paid checkout charges $${price} now, then ${billingCycle === "annual" ? `$${price}/year` : `$${price}/mo`} until canceled.`}
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
          <p className={`mt-2 text-[0.98rem] leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
            Worldbuilding manuscripts count as uploads on every tier. On Author, a series-linked worldbuilding manuscript counts once per book in that series. Architect remains unlimited.
          </p>
        </div>
      </section>

      {checkoutPreview ? (
        <Dialog
          open
          onClose={closeCheckoutPreview}
          title="Review today's charge"
          eyebrow="Before Paddle checkout"
          initialFocusRef={checkoutCancelRef}
          className={shellCardClass}
          titleClassName={`font-display text-3xl ${isDark ? "text-white" : "text-stone-950"}`}
          footer={(
            <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              <button
                ref={checkoutCancelRef}
                type="button"
                onClick={closeCheckoutPreview}
                className={`rounded-sm border px-4 py-3 text-sm font-semibold ${checkoutPreview.trial_active ? "border-transparent bg-[#1f615d] text-white" : noticeClass}`}
              >
                {checkoutPreview.default_action_label ?? "Cancel"}
              </button>
              <button
                type="button"
                onClick={() => void confirmPaidCheckout()}
                disabled={
                  Boolean(busyPlan)
                  || !checkoutPreview.quote_token
                  || (checkoutPreview.confirmation_required && !chargeConfirmed)
                }
                className="rounded-sm border border-[#2b7a73] px-4 py-3 text-sm font-semibold text-[#1f615d] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busyPlan ? "Opening checkout..." : checkoutPreview.checkout_button_label}
              </button>
            </div>
          )}
        >
            <div className={`mt-5 space-y-3 rounded-md border p-4 text-sm ${noticeClass}`}>
              <DisclosureRow label="Trial status" value={checkoutPreview.trial_active ? "Active — already started" : "Expired"} />
              <DisclosureRow
                label="Trial end date"
                value={checkoutPreview.trial_ends_at ? formatTrialEndDate(checkoutPreview.trial_ends_at) : "Unavailable"}
              />
              <DisclosureRow label="Amount charged today" value={checkoutPreview.charge_today} />
              <DisclosureRow label="Recurring price" value={`${checkoutPreview.recurring_price} until canceled`} />
            </div>

            {checkoutPreview.trial_active ? (
              <p className={`mt-4 text-sm leading-6 ${bodyCopyClass}`}>
                Your LoreVia trial is separate from Paddle. Paying now starts the selected paid subscription immediately; waiting keeps the free trial active with no scheduled charge.
              </p>
            ) : null}

            {checkoutPreview.confirmation_required && checkoutPreview.confirmation_text ? (
              <label className={`mt-5 flex cursor-pointer items-start gap-3 rounded-md border p-4 text-sm leading-6 ${noticeClass}`}>
                <input
                  type="checkbox"
                  checked={chargeConfirmed}
                  onChange={(event) => setChargeConfirmed(event.target.checked)}
                  className="mt-1 h-4 w-4"
                />
                <span>{checkoutPreview.confirmation_text}</span>
              </label>
            ) : null}

            {checkoutError ? (
              <div className="mt-4 rounded-md border border-red-700/30 bg-red-700/10 px-4 py-3 text-sm leading-6 text-red-700" role="alert">
                {checkoutError}
              </div>
            ) : null}

        </Dialog>
      ) : null}
    </>
  )
}

function DisclosureRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <span className="text-left opacity-75">{label}</span>
      <strong className="text-right font-semibold">{value}</strong>
    </div>
  )
}

function formatTrialEndDate(value: string) {
  return new Intl.DateTimeFormat("en-US", { dateStyle: "long", timeStyle: "short" }).format(new Date(value))
}

function formatBillingDate(value: string) {
  return new Intl.DateTimeFormat("en-US", { dateStyle: "long", timeZone: "UTC" }).format(new Date(value))
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
