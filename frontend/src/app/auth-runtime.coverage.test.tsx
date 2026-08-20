// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { renderToStaticMarkup } from "react-dom/server"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const routerMock = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(),
}))
const authApiMock = vi.hoisted(() => ({
  forgotPassword: vi.fn(),
  login: vi.fn(),
  loginWithSupabaseToken: vi.fn(),
  me: vi.fn(),
  register: vi.fn(),
  resetPassword: vi.fn(),
  setUsername: vi.fn(),
}))
const supabaseMock = vi.hoisted(() => ({
  auth: {
    exchangeCodeForSession: vi.fn(),
    getSession: vi.fn(),
  },
}))
const authState = vi.hoisted(() => ({
  user: null as { username?: string | null } | null,
  setUser: vi.fn(),
  logout: vi.fn(),
}))
const searchParamsState = vi.hoisted(() => ({ value: "token=reset-token" }))

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
}))

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
  useSearchParams: () => new URLSearchParams(searchParamsState.value),
}))

vi.mock("@/components/auth/AuthLink", () => ({
  AuthLink: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
}))

vi.mock("@/components/auth/GoogleOAuthButton", () => ({
  GoogleOAuthButton: () => <button type="button">Continue with Google</button>,
}))

vi.mock("@/lib/api/auth", () => ({
  authApi: authApiMock,
}))

vi.mock("@/lib/supabase", () => ({
  supabase: supabaseMock,
}))

vi.mock("@/lib/stores/authStore", () => {
  const useAuthStore = (selector: (state: typeof authState) => unknown) => selector(authState)
  useAuthStore.getState = () => authState
  return { useAuthStore }
})

vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: () => ({ theme: "light" }),
}))

vi.mock("@/lib/utils/device", () => ({
  getOrCreateDeviceId: () => "device-1",
}))

import GlobalError from "./error"
import robots from "./robots"
import CompleteUsernamePage from "./(auth)/complete-username/page"
import ForgotPasswordPage from "./(auth)/forgot-password/page"
import LoginPage from "./(auth)/login/page"
import RegisterPage from "./(auth)/register/page"
import ResetPasswordPage from "./(auth)/reset-password/page"
import AuthCallbackPage from "./auth/callback/page"

let root: Root | null = null
let container: HTMLDivElement | null = null

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

async function renderElement(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  await act(async () => {
    root?.render(element)
    await Promise.resolve()
  })
}

beforeEach(() => {
  authState.user = null
  authState.setUser.mockReset()
  authState.logout.mockReset()
  for (const mock of Object.values(routerMock)) mock.mockReset()
  for (const mock of Object.values(authApiMock)) mock.mockReset()
  supabaseMock.auth.exchangeCodeForSession.mockReset()
  supabaseMock.auth.getSession.mockReset()
  authApiMock.me.mockResolvedValue(null)
  authApiMock.loginWithSupabaseToken.mockResolvedValue({
    id: "user-1",
    email: "mira@example.com",
    username: "mira",
  })
  supabaseMock.auth.getSession.mockResolvedValue({
    data: {
      session: {
        access_token: "supabase-token-1234567890",
        user: { email: "mira@example.com" },
      },
    },
  })
  supabaseMock.auth.exchangeCodeForSession.mockResolvedValue({
    data: { session: null },
    error: null,
  })
  window.sessionStorage.clear()
  window.history.replaceState({}, "", "/")
  searchParamsState.value = "token=reset-token"
})

afterEach(() => {
  if (root) {
    act(() => {
      root?.unmount()
    })
  }
  container?.remove()
  root = null
  container = null
  document.body.innerHTML = ""
})

describe("auth and root runtime pages", () => {
  it("returns the crawler rules used by the app", () => {
    const config = robots()

    expect(config.host).toContain("lorevia")
    const rules = Array.isArray(config.rules) ? config.rules : [config.rules]
    expect(rules[0]?.disallow).toContain("/auth/")
    expect(rules[0]?.disallow).toContain("/review/")
  })

  it("renders the global error recovery surface", async () => {
    const reset = vi.fn()

    const markup = renderToStaticMarkup(<GlobalError error={new Error("hidden")} reset={reset} />)

    expect(markup).toContain("This screen hit a problem.")
    expect(markup).toContain("Contact support")
  })

  it.each([
    ["login", <LoginPage key="login" />, "Sign in"],
    ["register", <RegisterPage key="register" />, "Create account"],
    ["forgot password", <ForgotPasswordPage key="forgot-password" />, "Reset your password"],
    ["reset password", <ResetPasswordPage key="reset-password" />, "Choose a new password"],
  ])("renders the %s page", async (_name, element, expectedText) => {
    await renderElement(element)

    expect(container?.textContent).toContain(expectedText)
  })

  it("renders the complete username page for OAuth users without a username", async () => {
    authState.user = { username: null }

    await renderElement(<CompleteUsernamePage />)

    expect(container?.textContent).toContain("Choose a username")
    expect(routerMock.replace).not.toHaveBeenCalledWith("/login")
  })

  it("completes the OAuth callback and redirects known users to the library", async () => {
    window.history.replaceState({}, "", "/auth/callback?code=oauth-code")
    window.sessionStorage.setItem("lorevia-oauth-accepted-terms", "true")

    await renderElement(<AuthCallbackPage />)
    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 0))
      await Promise.resolve()
    })

    expect(authApiMock.loginWithSupabaseToken).toHaveBeenCalledWith("supabase-token-1234567890", "device-1", true)
    expect(authState.setUser).toHaveBeenCalledWith(expect.objectContaining({ username: "mira" }))
    expect(window.sessionStorage.getItem("lorevia-oauth-accepted-terms")).toBeNull()
    expect(routerMock.replace).toHaveBeenCalledWith("/library")
  })

  it("stores pending OAuth users without usernames and redirects to username completion", async () => {
    authApiMock.loginWithSupabaseToken.mockResolvedValueOnce({
      id: "user-2",
      email: "new@example.com",
      username: null,
    })
    window.history.replaceState({}, "", "/auth/callback?code=oauth-code")

    await renderElement(<AuthCallbackPage />)
    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 0))
      await Promise.resolve()
    })

    expect(window.sessionStorage.getItem("lorevia-pending-oauth-user")).toContain("new@example.com")
    expect(routerMock.replace).toHaveBeenCalledWith("/complete-username")
  })

  it("redirects OAuth callback errors back to login", async () => {
    window.history.replaceState({}, "", "/auth/callback?error=access_denied")

    await renderElement(<AuthCallbackPage />)
    await act(async () => {
      await Promise.resolve()
    })

    expect(routerMock.replace).toHaveBeenCalledWith(
      `/login?error=${encodeURIComponent("Google sign-in failed. Please try again.")}`,
    )
  })

  it("submits login credentials, stores the user, and follows a safe next route", async () => {
    searchParamsState.value = "next=%2Fstats"
    authApiMock.login.mockResolvedValue({ id: "user-1", email: "mira@example.com", username: "mira" })
    await renderElement(<LoginPage />)
    const email = container?.querySelector('input[type="email"]') as HTMLInputElement
    const password = container?.querySelector('input[type="password"]') as HTMLInputElement
    await changeField(email, "mira@example.com")
    await changeField(password, "SafePass123!")
    await submitForm()

    expect(authApiMock.login).toHaveBeenCalledWith("mira@example.com", "SafePass123!", "device-1")
    expect(authState.setUser).toHaveBeenCalledWith(expect.objectContaining({ username: "mira" }))
    expect(routerMock.push).toHaveBeenCalledWith("/stats")
  })

  it("shows a recoverable login error when the API returns no user", async () => {
    authApiMock.login.mockResolvedValue(null)
    await renderElement(<LoginPage />)
    await changeField(container?.querySelector('input[type="email"]') as HTMLInputElement, "mira@example.com")
    await changeField(container?.querySelector('input[type="password"]') as HTMLInputElement, "SafePass123!")
    await submitForm()
    expect(container?.textContent).toContain("Could not load your account")
  })

  it("validates existing login sessions and clears stale cached users", async () => {
    authState.user = { username: "mira" }
    authApiMock.me.mockResolvedValueOnce({ id: "user-1" })
    await renderElement(<LoginPage />)
    expect(container?.textContent).toContain("Checking session...")
    await flushUi()
    expect(routerMock.replace).toHaveBeenCalledWith("/library")

    act(() => root?.unmount())
    container?.remove()
    root = null
    container = null
    routerMock.replace.mockReset()
    authApiMock.me.mockRejectedValueOnce(new Error("expired"))
    await renderElement(<LoginPage />)
    await flushUi()
    expect(authState.logout).toHaveBeenCalled()
    expect((container as HTMLDivElement | null)?.textContent).toContain("Sign in")
  })

  it("validates registration fields, generates a password, and creates an account", async () => {
    Object.defineProperty(globalThis.crypto, "getRandomValues", {
      configurable: true,
      value: (buffer: Uint32Array) => buffer.fill(7),
    })
    authApiMock.register.mockResolvedValue({ email: "new@example.com" })
    await renderElement(<RegisterPage />)

    const inputs = Array.from(container?.querySelectorAll("input") ?? []) as HTMLInputElement[]
    const email = inputs.find((input) => input.type === "email") as HTMLInputElement
    const username = inputs.find((input) => input.autocomplete === "username") as HTMLInputElement
    const password = inputs.find((input) => input.autocomplete === "new-password") as HTMLInputElement
    const terms = inputs.find((input) => input.type === "checkbox") as HTMLInputElement

    await changeField(email, "new@example.com")
    await changeField(username, "x")
    await changeField(password, "short")
    await submitForm()
    expect(container?.textContent).toContain("Username")

    await changeField(username, "new_writer")
    await clickButton("Generate strong password")
    expect(password.value).toHaveLength(20)
    await changeField(password, "StrongPass123!Safe")
    await clickButton("Show")
    expect(password.type).toBe("text")
    await submitForm()
    expect(container?.textContent).toContain("Please accept")

    await act(async () => {
      terms.click()
      await Promise.resolve()
    })
    await submitForm()
    expect(authApiMock.register).toHaveBeenCalledWith(
      "new@example.com", "new_writer", password.value, true, "device-1",
    )
    expect(routerMock.push).toHaveBeenCalledWith("/verify-email?email=new%40example.com")
  })
})

async function flushUi() {
  await act(async () => {
    await Promise.resolve()
    await new Promise((resolve) => setTimeout(resolve, 0))
  })
}

async function changeField(field: HTMLInputElement, value: string) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(field, value)
    field.dispatchEvent(new Event("input", { bubbles: true }))
    await Promise.resolve()
  })
}

async function submitForm() {
  const form = container?.querySelector("form")
  expect(form).toBeTruthy()
  await act(async () => {
    form?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }))
    await Promise.resolve()
  })
}

async function clickButton(label: string) {
  const button = Array.from(container?.querySelectorAll("button") ?? []).find((item) => item.textContent?.trim() === label)
  expect(button).toBeTruthy()
  await act(async () => {
    button?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await Promise.resolve()
  })
}
