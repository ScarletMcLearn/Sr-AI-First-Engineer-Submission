import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests run against a dedicated stack that never touches the development database:
 *   - PostgreSQL database `l10_e2e` (created by docker/postgres-init.sql)
 *   - FastAPI on :8100 with the test-only reset endpoint enabled (refused for non-test databases)
 *   - Next.js production build on :3100, built for that API URL
 * Business time is the frozen default APP_NOW (2026-11-11T15:00:00Z); meeting timers use real time.
 */
const API_PORT = 8100;
const WEB_PORT = 3100;
const API_URL = `http://localhost:${String(API_PORT)}`;
const WEB_URL = `http://localhost:${String(WEB_PORT)}`;
const DATABASE_URL =
  process.env.E2E_DATABASE_URL ?? "postgresql+psycopg://l10:l10@localhost:5432/l10_e2e";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1, // tests share one seeded database and reset it before each test
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 7_000 },
  reporter: [["list"], ["html", { open: "never" }]],
  outputDir: "test-results",
  use: {
    baseURL: WEB_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command:
        "uv run --frozen python -m app.cli migrate && uv run --frozen uvicorn app.main:app --port 8100",
      cwd: "../backend",
      url: `${API_URL}/api/health`,
      reuseExistingServer: false,
      timeout: 60_000,
      env: {
        DATABASE_URL,
        ENABLE_TEST_ENDPOINTS: "true",
        CORS_ORIGINS: WEB_URL,
        APP_NOW: "2026-11-11T15:00:00Z",
      },
    },
    {
      command: `pnpm exec next build && pnpm exec next start -p ${String(WEB_PORT)}`,
      url: WEB_URL,
      reuseExistingServer: false,
      timeout: 240_000,
      env: { NEXT_PUBLIC_API_URL: API_URL, NEXT_DIST_DIR: ".next-e2e" },
    },
  ],
});
