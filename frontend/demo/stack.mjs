// `pnpm demo:stack`: start (and pre-build) the isolated demo stack so `pnpm demo` starts instantly.
// Same servers/ports/database as playwright.config.ts: l10_e2e DB, API :8100, web :3100.
// Env: DEMO_STACK_TIMEOUT_SECONDS (default 180) = max time for both services to become healthy.
import { spawn, spawnSync } from "node:child_process";

import { createStack } from "./stack-lib.mjs";

const WEB = "http://localhost:3100";
const API = "http://localhost:8100";
const isWin = process.platform === "win32";

const parsed = Number(process.env.DEMO_STACK_TIMEOUT_SECONDS ?? 180);
const timeoutSeconds = Number.isFinite(parsed) && parsed > 0 ? parsed : 180;

const services = [
  {
    name: "backend",
    port: 8100,
    url: `${API}/api/health`,
    cwd: "../backend",
    command:
      "uv run --frozen python -m app.cli migrate && uv run --frozen uvicorn app.main:app --port 8100",
    env: {
      DATABASE_URL:
        process.env.E2E_DATABASE_URL ?? "postgresql+psycopg://l10:l10@localhost:5432/l10_e2e",
      ENABLE_TEST_ENDPOINTS: "true",
      CORS_ORIGINS: WEB,
      APP_NOW: "2026-11-11T15:00:00Z",
    },
  },
  {
    name: "frontend",
    port: 3100,
    url: WEB,
    cwd: ".",
    command: "pnpm exec next build && pnpm exec next start -p 3100",
    env: { NEXT_PUBLIC_API_URL: API, NEXT_DIST_DIR: ".next-e2e" },
  },
];

const stack = createStack({
  services,
  timeoutMs: timeoutSeconds * 1000,
  spawnService: (s) =>
    spawn(s.command, {
      cwd: s.cwd,
      shell: true,
      stdio: "inherit",
      detached: !isWin, // own process group on POSIX so the whole tree can be signalled
      env: { ...process.env, ...s.env },
    }),
  killTree: (child) => {
    if (child.pid === undefined || child.exitCode !== null) return;
    if (isWin) spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"]);
    else process.kill(-child.pid, "SIGTERM");
  },
  probe: async (s) => {
    try {
      const res = await fetch(s.url, { signal: AbortSignal.timeout(3000) });
      return { ok: res.ok, detail: `HTTP ${res.status}` };
    } catch (err) {
      return { ok: false, detail: err.cause?.code ?? err.message };
    }
  },
  exit: (code) => process.exit(code),
});

process.on("SIGINT", stack.handleSignal);
process.on("SIGTERM", stack.handleSignal);

if (await stack.start()) await new Promise(() => undefined); // keep running; children hold the loop
