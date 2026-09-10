import { defineConfig, devices } from "@playwright/test";

/**
 * T-602 E2E harness. Chromium only (D-032), 1920×1080 projector viewport,
 * UTC/en-IN pinned. Backend + frontend boot via webServer; the corpus is
 * ingested in globalSetup (real generated dataset, documented ingest flow).
 * Oracle rule (PLAYWRIGHT_STRATEGY §2): rendered text is compared against
 * the API payload formatted with the imported shared formatter — never
 * against literals, never against test-computed numbers.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  globalSetup: "./tests/e2e/global-setup.ts",
  timeout: 180000,
  expect: { timeout: 20000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  outputDir: "test-results",
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
    video: "retain-on-failure",
    viewport: { width: 1920, height: 1080 },
    timezoneId: "UTC",
    locale: "en-IN",
    colorScheme: "light",
    reducedMotion: "reduce",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000",
      cwd: "../",
      url: "http://127.0.0.1:8000/api/v1/healthz",
      reuseExistingServer: true,
      timeout: 120000,
    },
    {
      command: "npm run dev",
      url: "http://localhost:5173/",
      reuseExistingServer: true,
      timeout: 120000,
    },
  ],
});
