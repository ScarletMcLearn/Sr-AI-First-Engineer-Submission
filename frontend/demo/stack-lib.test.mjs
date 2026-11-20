// Run: node --test demo/stack-lib.test.mjs   (built-in runner, no dependencies, no real servers)
import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import test from "node:test";

import { createStack } from "./stack-lib.mjs";

const services = [
  { name: "backend", port: 1 },
  { name: "frontend", port: 2 },
];

function harness({ health = {}, timeoutMs = 50 } = {}) {
  const h = { children: {}, killed: [], exits: [], out: [], err: [] };
  h.stack = createStack({
    services,
    timeoutMs,
    pollMs: 1,
    spawnService: (s) => (h.children[s.name] = Object.assign(new EventEmitter(), { pid: 1 })),
    killTree: (c) => h.killed.push(c),
    exit: (code) => h.exits.push(code),
    probe: async (s) =>
      health[s.name] === true
        ? { ok: true, detail: "HTTP 200" }
        : { ok: false, detail: health[s.name] ?? "connection refused" },
    log: (m) => h.out.push(m),
    error: (m) => h.err.push(m),
  });
  return h;
}

test("both ready: success, nothing killed, no exit", async () => {
  const h = harness({ health: { backend: true, frontend: true } });
  assert.equal(await h.stack.start(), true);
  assert.deepEqual(h.exits, []);
  assert.equal(h.killed.length, 0);
  assert.match(h.out.join("\n"), /READY/);
});

test("backend timeout: names backend, kills all, exit 1", async () => {
  const h = harness({ health: { frontend: true, backend: "HTTP 503" } });
  assert.equal(await h.stack.start(), false);
  assert.deepEqual(h.exits, [1]);
  assert.equal(h.killed.length, 2);
  const err = h.err.join("\n");
  assert.match(err, /backend: NOT READY \(last check: HTTP 503\)/);
  assert.match(err, /frontend: READY/);
});

test("frontend timeout", async () => {
  const h = harness({ health: { backend: true } });
  assert.equal(await h.stack.start(), false);
  assert.deepEqual(h.exits, [1]);
  const err = h.err.join("\n");
  assert.match(err, /frontend: NOT READY \(last check: connection refused\)/);
  assert.match(err, /backend: READY/);
});

test("both timeout: both reported", async () => {
  const h = harness();
  await h.stack.start();
  const err = h.err.join("\n");
  assert.match(err, /backend: NOT READY/);
  assert.match(err, /frontend: NOT READY/);
  assert.deepEqual(h.exits, [1]);
});

for (const name of ["backend", "frontend"]) {
  test(`${name} crashes during startup: fails fast, kills all, exit 1`, async () => {
    const h = harness({ timeoutMs: 60_000 });
    const started = h.stack.start();
    await new Promise((r) => setTimeout(r, 10));
    h.children[name].emit("exit", 3, null);
    assert.equal(await started, false);
    assert.deepEqual(h.exits, [1]);
    assert.equal(h.killed.length, 2);
    assert.match(h.err.join("\n"), new RegExp(`${name} exited unexpectedly`));
  });
}

test("Ctrl+C after ready: clean shutdown, exit 0; repeated signals run once", async () => {
  const h = harness({ health: { backend: true, frontend: true } });
  await h.stack.start();
  h.stack.handleSignal();
  h.stack.handleSignal();
  h.stack.handleSignal();
  assert.deepEqual(h.exits, [0]);
  assert.equal(h.killed.length, 2);
  h.children.backend.emit("exit", null, "SIGTERM"); // caused by our own kill: not an error
  assert.deepEqual(h.exits, [0]);
  assert.equal(h.err.length, 0);
});

test("Ctrl+C during startup stops polling", async () => {
  const h = harness({ timeoutMs: 60_000 });
  const started = h.stack.start();
  await new Promise((r) => setTimeout(r, 10));
  h.stack.handleSignal();
  assert.equal(await started, false);
  assert.deepEqual(h.exits, [0]);
});
