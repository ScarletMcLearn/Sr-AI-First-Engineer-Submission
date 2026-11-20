// Readiness + process-lifecycle logic for stack.mjs, with injectable dependencies so it is unit-testable.
import { performance } from "node:perf_hooks";

const defaultSleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * @param {object} o
 * @param {{name: string, port?: number}[]} o.services  start order = report order
 * @param {(service) => import("node:events").EventEmitter & {pid?: number}} o.spawnService
 * @param {(service) => Promise<{ok: boolean, detail: string}>} o.probe
 * @param {(child) => void} o.killTree
 * @param {(code: number) => void} o.exit
 * @param {number} o.timeoutMs
 */
export function createStack({
  services,
  spawnService,
  probe,
  killTree,
  exit,
  timeoutMs,
  pollMs = 1000,
  now = () => performance.now(), // monotonic
  sleep = defaultSleep,
  log = console.log,
  error = console.error,
}) {
  const children = [];
  let stopping = false;

  function shutdown(code) {
    if (stopping) return; // repeated signals and cascading child exits run this once
    stopping = true;
    for (const child of children) {
      try {
        killTree(child);
      } catch {
        /* already gone */
      }
    }
    exit(code);
  }

  function handleSignal() {
    if (stopping) return;
    log("\n[demo-stack] Stopping demo services...");
    shutdown(0);
  }

  async function start() {
    const state = new Map(services.map((s) => [s.name, { ready: false, last: "no response yet" }]));
    for (const service of services) {
      log(`[demo-stack] Starting ${service.name}${service.port ? ` on :${service.port}` : ""}`);
      let child;
      try {
        child = spawnService(service);
      } catch (err) {
        error(`[demo-stack] ERROR: could not start ${service.name}: ${err.message}`);
        shutdown(1);
        return false;
      }
      children.push(child);
      child.on("error", (err) => {
        if (stopping) return;
        error(`[demo-stack] ERROR: ${service.name} failed to spawn: ${err.message}`);
        shutdown(1);
      });
      child.on("exit", (code, signal) => {
        if (stopping) return;
        error(
          `[demo-stack] ERROR: ${service.name} exited unexpectedly (${signal ?? `code ${code}`}).`,
        );
        error("Stopping demo services...\nDemo stack startup FAILED.");
        shutdown(1);
      });
    }

    const deadline = now() + timeoutMs;
    while (!stopping) {
      await Promise.all(
        services.map(async (service) => {
          const s = state.get(service.name);
          if (s.ready) return;
          let result;
          try {
            result = await probe(service);
          } catch (err) {
            result = { ok: false, detail: String(err?.message ?? err) };
          }
          s.last = result.detail;
          if (result.ok && !stopping) {
            s.ready = true;
            log(`[demo-stack] ${service.name} ready`);
          }
        }),
      );
      if (stopping) return false;
      if ([...state.values()].every((s) => s.ready)) {
        log(
          "\nDemo stack is READY.\n\nRun in another terminal:\npnpm demo   (Ctrl+C here to stop)\n",
        );
        return true;
      }
      if (now() >= deadline) {
        error(
          `\n[demo-stack] ERROR: Startup timed out after ${Math.round(timeoutMs / 1000)} seconds.\n`,
        );
        for (const service of services) {
          const s = state.get(service.name);
          error(`${service.name}: ${s.ready ? "READY" : `NOT READY (last check: ${s.last})`}`);
        }
        error("\nStopping demo services...\nDemo stack startup FAILED.");
        shutdown(1);
        return false;
      }
      await sleep(pollMs);
    }
    return false;
  }

  return { start, shutdown, handleSignal };
}
