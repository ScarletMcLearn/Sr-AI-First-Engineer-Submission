// Pure rules for the manually controlled demo: which scene may run next. No browser, no I/O, so it is
// unit-testable (node --test demo/session-state.test.mjs).

/**
 * @param {object} o
 * @param {readonly string[]} o.order       scene ids in demonstration order
 * @param {Record<string, readonly string[]>} o.prerequisites  scene id -> scenes that must have passed
 * @param {readonly string[]} o.passed      scenes that have passed in this session
 * @param {readonly string[]} o.failed      scenes that have failed in this session
 * @param {string | null} o.running         scene currently running, if any
 * @param {string} id
 * @returns {{ ok: true } | { ok: false, message: string }}
 */
export function checkRunnable({ order, prerequisites, passed, failed, running }, id) {
  if (!order.includes(id)) {
    return { ok: false, message: `Unknown scene "${id}".\nScenes: ${order.join(", ")}` };
  }
  if (running) {
    return { ok: false, message: `Scene "${running}" is still running. Wait for it to finish.` };
  }
  if (failed.length > 0) {
    return {
      ok: false,
      message:
        `Scene "${failed[failed.length - 1]}" failed earlier, so the browsers may be mid-scene.\n` +
        "Restart the demonstration from the beginning:\npnpm demo:reset",
    };
  }
  if (passed.includes(id)) {
    return {
      ok: false,
      message: `Scene "${id}" has already run in this session.\nStart over with: pnpm demo:reset`,
    };
  }
  const index = order.indexOf(id);
  const later = order.slice(index + 1).find((s) => passed.includes(s));
  if (later) {
    return {
      ok: false,
      message: `Cannot run ${id} now: the later scene "${later}" has already run.\nStart over with: pnpm demo:reset`,
    };
  }
  const missing = (prerequisites[id] ?? []).filter((s) => !passed.includes(s));
  if (missing.length > 0) {
    return {
      ok: false,
      message: `Cannot run ${id} yet.\nRequired scene${missing.length > 1 ? "s" : ""}: ${missing.join(", ")}`,
    };
  }
  return { ok: true };
}

/** The scene that normally comes next (first one not yet passed after the last passed scene). */
export function nextScene(order, passed) {
  const last = Math.max(-1, ...passed.map((s) => order.indexOf(s)));
  return order[last + 1] ?? null;
}
