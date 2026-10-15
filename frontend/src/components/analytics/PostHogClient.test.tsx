import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const pathnameMock = vi.hoisted(() => vi.fn(() => "/library"))
const initMock = vi.hoisted(() => vi.fn())
const optInMock = vi.hoisted(() => vi.fn())
const optOutMock = vi.hoisted(() => vi.fn())

vi.mock("next/navigation", () => ({ usePathname: pathnameMock }))
vi.mock("next/web-vitals", () => ({ useReportWebVitals: vi.fn() }))
vi.mock("posthog-js", () => ({ default: { init: initMock, opt_in_capturing: optInMock, opt_out_capturing: optOutMock } }))
vi.mock("next/dynamic", () => ({
  default: () => function ConsentMock(props: {
    children: React.ReactNode
    onAccept: () => void
    onDecline: () => void
    buttonStyle: { borderRadius: string }
    declineButtonStyle: { borderRadius: string }
    containerClasses: string
    style: { maxWidth: string; width: string; zIndex: string }
  }) {
    return (
      <div
        data-testid="consent"
        data-accept-radius={props.buttonStyle.borderRadius}
        data-decline-radius={props.declineButtonStyle.borderRadius}
        data-container-class={props.containerClasses}
        data-max-width={props.style.maxWidth}
        data-width={props.style.width}
        data-z-index={props.style.zIndex}
      >
        {props.children}
        <button onClick={props.onAccept}>Accept analytics</button>
        <button onClick={props.onDecline}>Decline analytics</button>
      </div>
    )
  },
}))

import { PostHogClient, PostHogClientProvider } from "./PostHogClient"
import { writeAnalyticsConsentCookie } from "@/lib/analytics/posthogConsent"

describe("PostHogClient", () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_KEY", "ph_test")
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_HOST", "https://analytics.example.test")
    pathnameMock.mockReturnValue("/library")
    initMock.mockReset()
    optInMock.mockClear()
    optOutMock.mockClear()
    document.cookie = "lorevia_analytics_consent=; Max-Age=0; Path=/"
    container = document.createElement("div")
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
    vi.unstubAllEnvs()
  })

  it("shows consent, initializes analytics on accept, and renders provider children", async () => {
    await act(async () => {
      root.render(<PostHogClientProvider><span>Application body</span></PostHogClientProvider>)
      await Promise.resolve()
    })
    expect(container.textContent).toContain("Application body")
    expect(container.textContent).toContain("Want to allow cookies")
    expect(container.querySelector<HTMLElement>('[data-testid="consent"]')?.dataset).toMatchObject({
      containerClass: "lorevia-cookie-consent",
      maxWidth: "34rem",
      width: "calc(100% - 2rem)",
      zIndex: "60",
    })

    await act(async () => {
      findButton(container, "Accept analytics").click()
      await Promise.resolve()
    })
    expect(document.cookie).toContain("lorevia_analytics_consent=true")
    expect(initMock).toHaveBeenCalledWith("ph_test", expect.objectContaining({ api_host: "https://analytics.example.test" }))
    expect(window.__loreviaPosthog).toBeDefined()
  })

  it("uses square public-page controls and persists decline", async () => {
    pathnameMock.mockReturnValue("/blog/runtime-coverage")
    await act(async () => {
      root.render(<PostHogClient />)
      await Promise.resolve()
    })
    const banner = container.querySelector<HTMLElement>('[data-testid="consent"]')
    expect(banner?.dataset.acceptRadius).toBe("0")
    expect(banner?.dataset.declineRadius).toBe("0")
    act(() => findButton(container, "Decline analytics").click())
    expect(document.cookie).toContain("lorevia_analytics_consent=false")
  })

  it("does not render a banner when analytics is disabled", async () => {
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_KEY", "")
    await act(async () => {
      root.render(<PostHogClient />)
      await Promise.resolve()
    })
    expect(container.querySelector('[data-testid="consent"]')).toBeNull()
  })

  it("applies settings consent changes to the running SDK and can re-enable it", async () => {
    await act(async () => { root.render(<PostHogClient />) })
    await act(async () => { writeAnalyticsConsentCookie("true") })
    expect(optInMock).toHaveBeenCalledWith({ captureEventName: false })
    expect(window.__loreviaPosthog).toBeDefined()
    await act(async () => { writeAnalyticsConsentCookie("false") })
    expect(optOutMock).toHaveBeenCalled()
    expect(window.__loreviaPosthog).toBeUndefined()
    await act(async () => { writeAnalyticsConsentCookie("true") })
    expect(window.__loreviaPosthog).toBeDefined()
    expect(container.querySelector('[data-testid="consent"]')).toBeNull()
  })

  it("does not restore analytics when consent is withdrawn before initialization finishes", async () => {
    await act(async () => { root.render(<PostHogClient />) })
    await act(async () => { writeAnalyticsConsentCookie("true"); writeAnalyticsConsentCookie("false") })
    expect(window.__loreviaPosthog).toBeUndefined()
    expect(document.cookie).toContain("lorevia_analytics_consent=false")
  })
})

function findButton(container: HTMLElement, label: string) {
  const button = Array.from(container.querySelectorAll("button")).find((candidate) => candidate.textContent === label)
  if (!button) throw new Error(`Missing button: ${label}`)
  return button
}
