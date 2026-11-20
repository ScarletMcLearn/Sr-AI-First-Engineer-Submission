import http from "node:http";

import { test } from "../e2e/fixtures";

import { API_URL, CONTROL_PORT, PREREQUISITES, SCENE_ORDER, SCENES, settings } from "./demo-config";
import { Demo, PresentationStage, mmss } from "./demo-helpers";
import { prepareMain, SCENE_RUNNERS } from "./scenes";
import { checkRunnable, nextScene } from "./session-state.mjs";

/**
 * MANUAL MODE — a persistent demonstration session (`pnpm demo:session`).
 *
 * This "test" owns both browsers and the seeded database for its whole life. It starts a tiny control
 * server on 127.0.0.1 and then waits. Each `pnpm demo:scene <id>` is a separate short-lived process that
 * asks this one to run exactly one scene; nothing else ever runs. The test only ends on `pnpm demo:stop`.
 */
test("assessment demonstration (manual session)", async () => {
  test.setTimeout(0);
  settings.pace *= settings.manualPace;
  const outDir = "test-results/demo-manual";

  const passed: string[] = [];
  const failed: string[] = [];
  const timings: { id: string; title: string; seconds: number; status: "PASS" | "FAIL" }[] = [];
  let running: string | null = null;

  const stage = await PresentationStage.create();
  stage.setActionTimeout(Number(process.env.DEMO_ACTION_TIMEOUT_MS ?? 15_000));
  const makeDemo = (emit: (line: string) => void) =>
    new Demo(stage, outDir, { manual: true, log: emit });

  await prepareMain(stage);
  console.log("\n[DEMO] Browser A is open (Casey Cho, Leadership). Database seeded.");

  const state = () => ({
    order: SCENE_ORDER,
    prerequisites: PREREQUISITES,
    passed,
    failed,
    running,
  });

  async function runScene(id: string, emit: (line: string) => void): Promise<number> {
    const verdict = checkRunnable(state(), id);
    if (!verdict.ok) {
      emit(verdict.message);
      return 409;
    }
    const runner = SCENE_RUNNERS[id as keyof typeof SCENE_RUNNERS];
    const config = SCENES[id];
    if (!config) return 404;
    running = id;
    const demo = makeDemo(emit);
    const started = Date.now();
    try {
      await runner(demo);
      const seconds = (Date.now() - started) / 1000;
      passed.push(id);
      timings.push({ id, title: config.title, seconds, status: "PASS" });
      const next = nextScene(SCENE_ORDER, passed);
      emit(`\n[PASS] ${config.title} demonstration completed in ${mmss(seconds)}.`);
      emit("\nBrowser remains open. Nothing else will run until you say so.");
      emit(
        next
          ? `Run the next scene whenever ready:\npnpm demo:scene ${next}`
          : "All nine scenes done. pnpm demo:stop when finished.",
      );
      return 200;
    } catch (error) {
      failed.push(id);
      timings.push({
        id,
        title: config.title,
        seconds: (Date.now() - started) / 1000,
        status: "FAIL",
      });
      const message = error instanceof Error ? error.message : String(error);
      emit(`\n[FAIL] ${config.title}\n${message}`);
      emit(`\nScreenshots: frontend/${outDir}/demo-failure-${id}-browser-*.png`);
      emit("Browsers left as they are for inspection. Restart from the beginning: pnpm demo:reset");
      return 500;
    } finally {
      running = null;
    }
  }

  async function reset(emit: (line: string) => void): Promise<number> {
    if (running) {
      emit(`Scene "${running}" is still running. Wait for it to finish.`);
      return 409;
    }
    try {
      await stage.closeSecond();
      const res = await fetch(`${API_URL}/api/__test__/reset`, { method: "POST" });
      if (!res.ok) throw new Error(`database reset failed (HTTP ${String(res.status)})`);
      await stage.layout("full");
      await prepareMain(stage);
      passed.length = 0;
      failed.length = 0;
      timings.length = 0;
      emit(
        "[DEMO] Reset: database re-seeded, Browser B closed, Browser A signed in at the Team Page.",
      );
      emit("Start with: pnpm demo:scene intro");
      return 200;
    } catch (error) {
      emit(`Reset failed: ${error instanceof Error ? error.message : String(error)}`);
      return 500;
    }
  }

  function statusText(): string {
    const lines = SCENE_ORDER.map((id) => {
      const t = timings.find((x) => x.id === id);
      const mark = failed.includes(id)
        ? "FAIL"
        : passed.includes(id)
          ? "PASS"
          : running === id
            ? "RUNNING"
            : "-";
      return `  ${id.padEnd(13)}${mark.padEnd(8)}${t ? mmss(t.seconds) : ""}`;
    });
    const next = nextScene(SCENE_ORDER, passed);
    const total = timings.reduce((sum, t) => sum + t.seconds, 0);
    return [
      "Demo session: running",
      `Browser B: ${stage.pages().length > 1 ? "open" : "closed"}`,
      ...lines,
      `Automated time so far: ${mmss(total)} (excludes your narration)`,
      failed.length
        ? "A scene failed. Restart with: pnpm demo:reset"
        : next
          ? `Next: pnpm demo:scene ${next}`
          : "Nothing left to run.",
    ].join("\n");
  }

  let stop!: () => void;
  const stopped = new Promise<void>((resolve) => {
    stop = resolve;
  });

  const server = http.createServer((req, res) => {
    const url = new URL(req.url ?? "/", "http://127.0.0.1");
    const send = (code: number, body: string) => {
      res.writeHead(code, { "content-type": "text/plain; charset=utf-8" });
      res.end(body);
    };
    if (req.method === "GET" && url.pathname === "/status") {
      send(200, statusText());
      return;
    }
    if (req.method === "POST" && url.pathname === "/stop") {
      send(200, "Stopping the demo session; closing both browsers.");
      stop();
      return;
    }
    if (req.method !== "POST") {
      send(404, "not found");
      return;
    }
    // Long-running actions stream their output line by line, then the status code goes in a trailer line.
    res.writeHead(200, { "content-type": "text/plain; charset=utf-8", "x-accel-buffering": "no" });
    const emit = (line: string) => {
      console.log(line);
      res.write(`${line}\n`);
    };
    const finish = (code: number) => res.end(`\n::exit ${String(code)}\n`);
    if (url.pathname === "/reset") void reset(emit).then(finish);
    else if (url.pathname.startsWith("/scene/")) {
      void runScene(decodeURIComponent(url.pathname.slice(7)), emit).then(finish);
    } else finish(404);
  });
  await new Promise<void>((resolve, reject) => {
    server.once("error", reject);
    server.listen(CONTROL_PORT, "127.0.0.1", resolve);
  });

  console.log(`\n[DEMO] Ready. Control server on 127.0.0.1:${String(CONTROL_PORT)}.`);
  console.log("In another terminal:  pnpm demo:scene intro\n");

  try {
    await stopped;
  } finally {
    server.close();
    await stage.dispose();
  }
});
