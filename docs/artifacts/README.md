# Failure artifact

`meeting-sync-offline-regression-trace.zip` (+ `meeting-sync-offline-regression.png`) is a **genuine Playwright
failure** of `e2e/meeting-sync.spec.ts › two browsers stay in sync…`.

* **What failed:** at the "temporary disconnection" step the second browser (set offline with
  `context.setOffline(true)`) still received the facilitator's change to *Conclude* — the failing assertion expected
  it to still show *IDS* while offline. Chromium's offline emulation does not tear down an already-open
  Server-Sent-Events stream, so the client was not actually disconnected and the test could not verify recovery.
* **How it was found:** this is the real failure hit during development. The fix is the client's network awareness in
  `frontend/src/features/meeting/use-meeting.ts` (close the stream on the browser `offline` event, reconnect and take a
  fresh authoritative state on `online`). The committed suite passes with that fix.
* **How this artifact was produced:** the trace was re-captured by temporarily disabling the `offline` listener
  (reproducing the original failure), then restoring the code. The code in the repository is the fixed version.
* **Open it:** `cd frontend && pnpm exec playwright show-trace ../docs/artifacts/meeting-sync-offline-regression-trace.zip`
  (or drag the zip into https://trace.playwright.dev).
* **Sanitization:** contains only localhost URLs, seeded-user test data and the development-only session cookie
  (signed with the public dev default `SESSION_SECRET`); no real secrets or personal data.
