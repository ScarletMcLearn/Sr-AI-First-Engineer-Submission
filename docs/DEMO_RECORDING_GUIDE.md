# Demo recording guide (automated Playwright demonstration)

`pnpm demo` drives the whole assessment walkthrough by itself: two real Chromium windows side by side, two seeded
users, real SSE updates, reconnect, ratings, summary. You only record the screen and read
[DEMO_NARRATION_SCRIPT.md](DEMO_NARRATION_SCRIPT.md). It replaces the manual flow in [DEMO_SCRIPT.md](DEMO_SCRIPT.md).

> Playwright's per-page video recording is **not** used: it produces two separate files, not one synchronized
> side-by-side video. Use a desktop recorder (OBS) so both windows are captured together.

> **Prefer to control each scene yourself?** Use the manual mode: `pnpm demo:session`, then `pnpm demo:scene <id>`
> one scene at a time; the browsers stay put between commands. See
> [DEMO_MANUAL_RECORDING_SCRIPT.md](DEMO_MANUAL_RECORDING_SCRIPT.md). Commands: `demo:session`, `demo:scene`,
> `demo:status`, `demo:reset`, `demo:stop` (Pixi: `pixi run demo-session`). Pacing: `DEMO_MANUAL_PACE` (default 0.4).

## What runs and where

| Piece | How it starts | Notes |
|-------|---------------|-------|
| PostgreSQL | **You**: `docker compose up -d --wait db` (or `pixi run db-up`) | `l10_e2e` database must exist (created by `docker/postgres-init.sql` on a fresh volume). |
| API (:8100) + web (:3100) | **Automatic** (Playwright `webServer`), or pre-started with `pnpm demo:stack` | Isolated e2e stack; your normal :3000/:8000 app and `l10` database are never touched. |
| Demo data | **Automatic**: seed reset before every run | See "Deterministic data" below. |
| Browsers | **Automatic** | Two separate headed Chromium processes. |
| Recording | **You** (OBS or any desktop recorder) | Not automated. OBS is not installed on the development machine. |

## Prerequisites

- Docker Desktop (PostgreSQL container), Node 24.22.3 + pnpm 12.22.0 (or Pixi, which pins them), `uv`.
- One-time: `cd frontend && pnpm install --frozen-lockfile && pnpm exec playwright install chromium`
  (or `pixi run install`).
- A monitor of at least 1920×1080 (the demo detects the screen size; override with `DEMO_SCREEN=1920x1080`).
- Optional: `gh` CLI signed in; the architecture slide then shows the real CI status of the current commit.

## Run instructions (Windows, PowerShell or Git Bash)

```powershell
# 1. Database
docker compose up -d --wait db

# 2. (recommended) Pre-build the demo stack so the recording does not include a 1-2 minute build.
#    Terminal A, leave running; wait for ">>> Demo stack is READY".
cd frontend
pnpm demo:stack

# 3. Fast regression check of every scene (headless, ~10 s once the stack is up)
pnpm demo:validate

# 4. Start OBS recording, then in Terminal B:
pnpm demo
#    ...wait for the timing table in the terminal, then stop OBS.
```

Pixi equivalents: `pixi run demo-validate` and `pixi run demo` (they start the database for you).
Without `pnpm demo:stack`, `pnpm demo` builds and starts the stack itself (about 1–2 extra minutes of dead time at the
start of the recording; trim it, or use the stack command to avoid it).

`pnpm demo` waits `DEMO_START_DELAY` seconds (default 5) after the first window is ready, so the recording can settle.
Trim that lead-in and the closing seconds in your video editor if you like.

Environment knobs: `DEMO_PACE` (pause multiplier, e.g. `0.9`), `DEMO_START_DELAY`, `DEMO_SCREEN`, `DEMO_CI_STATUS`.

## Recording settings

- Screen 1920×1080, display scaling 100% (125% also works; the demo uses the detected CSS-pixel size).
- OBS: *Settings → Video*: base and output 1920×1080, 30 FPS. *Output → Recording*: MKV or MP4, CRF 20 (or
  fragmented MP4). Source: **Display Capture** of the monitor that holds the browsers (not Window Capture: there are
  two windows and Display Capture records both).
- Audio: add your microphone as *Audio Input Capture*, disable desktop audio, speak the narration live.
- Browser zoom: leave at 100%. Each window is half the screen (960 px wide) in the meeting scenes.
- Put the terminal on a second monitor, or minimise it after `pnpm demo` has opened the browser: the terminal prints
  scene cues (a teleprompter) but must not be in the recording.
- Turn on Do Not Disturb. Nothing private is shown: only seeded users (Casey Cho, Blake Brooks) and local URLs.

Recording procedure: start OBS → `pnpm demo` → wait for it to finish by itself → stop OBS. The videos are saved in the
OBS output folder (*Settings → Output → Recording Path*; default `C:\Users\<you>\Videos`).

## Deterministic data

The demo uses the **isolated e2e stack**: database `l10_e2e`, API :8100 with `ENABLE_TEST_ENDPOINTS=true`, web :3100,
business clock frozen by `APP_NOW=2026-11-11T15:00:00Z` (meeting timers use real time). Before each run the existing
guarded endpoint `POST /api/__test__/reset` truncates and re-seeds. `backend/app/testing.py` refuses any database
whose name does not end in `_test` or `_e2e`, so the development `l10` database and anything else can never be wiped.
No production code was changed and no demo-only backdoor was added. Every run therefore starts from the same seed and
can be repeated back to back.

## Timing

The presentation prints a table with each scene's measured duration and the total, and writes
`frontend/test-results/demo-report-presentation.json`. The test fails if the total reaches 7:00 and flags a total above
6:30. If a run is slow, look at which scene exceeds its target; use `DEMO_PACE=0.9` to shorten all pauses.

## Stack readiness timeout

`pnpm demo:stack` (`pixi run demo-stack`) starts the backend (:8100) and frontend (:3100) and polls both health
endpoints. When both are healthy it prints `Demo stack is READY` and keeps running (Ctrl+C stops it cleanly).

* Deadline: `DEMO_STACK_TIMEOUT_SECONDS` (default 180, enough for a fresh Next.js build), e.g.
  `DEMO_STACK_TIMEOUT_SECONDS=300 pnpm demo:stack`.
* If a service is not healthy by the deadline, it prints which service is NOT READY with the last check result
  (HTTP status or connection error), stops both child processes and exits with code 1.
* If either process exits during startup it fails immediately (exit 1) without waiting for the deadline.

## Validation without recording

`pixi run demo-validate` (or `pnpm demo:validate`) runs every scene headlessly with assertions. CI runs it too.
Do not run it at the same time as `pixi run test-e2e` or another suite: both reset the `l10_e2e` database.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Browser opens off-screen / on the wrong monitor | Windows are placed with CDP `Browser.setWindowBounds` at the primary monitor's top-left. Make the monitor you record the primary display, or set `DEMO_SCREEN`. |
| Windows overlap or are not half-width | Re-run; check Windows display scaling. Set `DEMO_SCREEN=1920x1080` to force the geometry. |
| Wrong user shown | Each browser is its own process and is signed in through `POST /api/auth/login` (u3 Casey Cho, u2 Blake Brooks). Close stray Chromium windows left by a killed run. |
| Session conflicts | Impossible by design (separate processes, no shared profile). If you see one, kill all `chrome.exe` started by Playwright and re-run. |
| "A meeting is already active" | The reset runs automatically at the start; if you killed a run mid-way just run `pnpm demo` again. |
| Stale seeded state | `pnpm demo` always re-seeds. Manual: `curl -X POST http://localhost:8100/api/__test__/reset`. |
| PostgreSQL not reachable | `docker compose up -d --wait db`. |
| SSE / sync assertion fails | Failure screenshots are in `frontend/test-results/demo-failure-*.png`; check the API log in the terminal. |
| Reload/reconnect scene fails | Same artifacts; the scene waits up to 20 s for recovery. A VPN or proxy that intercepts `localhost` can interfere. |
| Video exceeds seven minutes | Check the timing table. Trim the 5 s lead-in, use `DEMO_PACE=0.9`, or stop the recording right after the summary/architecture scene. |

## Limitations

- OBS is not driven automatically; start and stop it by hand.
- Side-by-side layout is verified by the `Browser.setWindowBounds` calls succeeding and by the tests; you should
  glance at your own screen once (run `pnpm demo` without recording) to confirm the geometry on your monitor.
- The architecture scene shows a generated evidence slide built from `docs/TEST_RESULTS.md`, `rules_report.json` and
  the CI status; it is not a live test run.
