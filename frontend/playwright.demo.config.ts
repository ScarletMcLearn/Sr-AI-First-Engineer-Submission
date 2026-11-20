import { defineConfig } from "@playwright/test";

import base from "./playwright.config";

/**
 * Assessment demonstration. Reuses the isolated e2e stack of playwright.config.ts (database `l10_e2e`,
 * API :8100, web :3100) and only changes what is run. Servers that are already running are reused,
 * so `pnpm demo:stack` can pre-build everything before the recording starts.
 */
export default defineConfig({
  ...base,
  testDir: "./demo",
  timeout: 12 * 60_000,
  reporter: [["list"]],
  outputDir: "test-results/demo",
  use: { baseURL: "http://localhost:3100", trace: "off", screenshot: "off", video: "off" },
  projects: [
    { name: "presentation", testMatch: /assessment-demo\.spec\.ts/ },
    { name: "validation", testMatch: /assessment-demo-validation\.spec\.ts/ },
    // Manual, scene-by-scene mode: `pnpm demo:session` + `pnpm demo:scene <id>`.
    { name: "session", testMatch: /assessment-demo-session\.spec\.ts/ },
  ],
  webServer: Array.isArray(base.webServer)
    ? base.webServer.map((server) => ({ ...server, reuseExistingServer: true }))
    : base.webServer,
});
