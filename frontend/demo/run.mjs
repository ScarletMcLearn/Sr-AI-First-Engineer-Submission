// Entry point for `pnpm demo` / `pnpm demo:validate`: checks prerequisites, then runs Playwright.
import { spawn, spawnSync } from "node:child_process";
import net from "node:net";

const mode = process.argv[2] === "validation" ? "validation" : "presentation";

function portOpen(port) {
  return new Promise((resolve) => {
    const socket = net.connect({ port, host: "127.0.0.1" }, () => {
      socket.destroy();
      resolve(true);
    });
    socket.on("error", () => resolve(false));
    socket.setTimeout(1500, () => {
      socket.destroy();
      resolve(false);
    });
  });
}

if (!(await portOpen(5432))) {
  console.error(
    "PostgreSQL is not reachable on localhost:5432.\n" +
      "Start it first:  docker compose up -d --wait db   (or: pixi run db-up)",
  );
  process.exit(2);
}

const env = { ...process.env };
if (mode === "presentation" && !env.DEMO_CI_STATUS) {
  // Best effort: ask GitHub for the CI result of the current commit. Never fails the demo.
  try {
    const sha = spawnSync("git", ["rev-parse", "HEAD"], { encoding: "utf8" }).stdout.trim();
    const out = spawnSync(
      "gh",
      ["run", "list", "--commit", sha, "--limit", "1", "--json", "conclusion,status"],
      { encoding: "utf8", timeout: 15000 },
    );
    const run = JSON.parse(out.stdout || "[]")[0];
    env.DEMO_CI_STATUS = run ? run.conclusion || run.status : "no run for this commit";
    env.DEMO_CI_SHA = sha;
  } catch {
    env.DEMO_CI_STATUS = "unknown";
  }
}

const child = spawn(
  "pnpm",
  ["exec", "playwright", "test", "-c", "playwright.demo.config.ts", `--project=${mode}`],
  { stdio: "inherit", shell: true, env },
);
child.on("exit", (code) => process.exit(code ?? 1));
