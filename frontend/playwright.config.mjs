import { defineConfig } from "@playwright/test"

process.env.ADMIN_E2E_TEST_SECRET ??= "codex-e2e-admin-secret"

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  timeout: 30_000,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  expect: {
    timeout: 10_000,
  },
  reporter: "list",
  use: {
    baseURL: "http://localhost:3001",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    browserName: "chromium",
    headless: true,
  },
  webServer: {
    command: "npm run dev:e2e",
    env: {
      ...process.env,
      ADMIN_E2E_TEST_SECRET: process.env.ADMIN_E2E_TEST_SECRET,
    },
    url: "http://localhost:3001",
    reuseExistingServer: false,
    timeout: 120_000,
  },
})
