// Run: node --test demo/session-state.test.mjs   (no browser, no servers)
import assert from "node:assert/strict";
import test from "node:test";

import { checkRunnable, nextScene } from "./session-state.mjs";

const order = ["a", "b", "c", "d"];
const prerequisites = { c: ["b"], d: ["c"] };
const base = { order, prerequisites, passed: [], failed: [], running: null };

test("a scene without prerequisites may run first, and may skip others", () => {
  assert.deepEqual(checkRunnable(base, "a"), { ok: true });
  assert.deepEqual(checkRunnable(base, "b"), { ok: true });
});

test("missing prerequisite is reported and nothing is run implicitly", () => {
  const r = checkRunnable({ ...base, passed: ["a"] }, "c");
  assert.equal(r.ok, false);
  assert.match(r.message, /Cannot run c yet\.\nRequired scene: b/);
});

test("unknown scene lists the valid ones", () => {
  const r = checkRunnable(base, "zzz");
  assert.equal(r.ok, false);
  assert.match(r.message, /Unknown scene "zzz"[\s\S]*a, b, c, d/);
});

test("a scene cannot run twice or after a later scene", () => {
  assert.match(checkRunnable({ ...base, passed: ["a"] }, "a").message, /already run/);
  assert.match(checkRunnable({ ...base, passed: ["b"] }, "a").message, /later scene "b"/);
});

test("nothing runs while another scene runs or after a failure", () => {
  assert.match(checkRunnable({ ...base, running: "a" }, "b").message, /still running/);
  assert.match(checkRunnable({ ...base, failed: ["b"] }, "c").message, /pnpm demo:reset/);
});

test("nextScene follows the last passed scene", () => {
  assert.equal(nextScene(order, []), "a");
  assert.equal(nextScene(order, ["a", "c"]), "d");
  assert.equal(nextScene(order, ["d"]), null);
});
