import { defineConfig } from "@playwright/test"

delete process.env.NO_COLOR

process.env.ADMIN_E2E_TEST_SECRET ??= "codex-e2e-admin-secret"
const e2ePort = process.env.E2E_PORT ?? "3001"
const e2eOrigin = process.env.E2E_APP_ORIGIN ?? `http://localhost:${e2ePort}`
const webServerEnv = { ...process.env }
delete webServerEnv.NO_COLOR
const reporter =
  process.platform === "win32"
    ? [["list"], ["./e2e/support/windowsExitReporter.mjs"]]
    : "list"

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  timeout: 60_000,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  expect: {
    timeout: 10_000,
  },
  reporter,
  use: {
    baseURL: e2eOrigin,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    browserName: "chromium",
    headless: true,
  },
  webServer: {
    command: "node scripts/start-e2e-dev.mjs",
    env: {
      ...webServerEnv,
      ADMIN_E2E_TEST_SECRET: process.env.ADMIN_E2E_TEST_SECRET,
      E2E_APP_ORIGIN: e2eOrigin,
      E2E_PORT: e2ePort,
      NEXT_PUBLIC_E2E_MOCK_API: "1",
    },
    url: e2eOrigin,
    reuseExistingServer: false,
    timeout: 120_000,
  },
})
