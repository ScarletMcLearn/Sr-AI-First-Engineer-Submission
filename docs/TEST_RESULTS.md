# Verification results

Produced by the final verification run on branch `feature/l10-meetings-app` (Windows 11, Docker Desktop, Pixi-pinned
toolchain: Python 3.13.18, Node 24.22.3, pnpm 12.22.0, uv 0.13.9). Command: `pixi run check` (exit code 0), plus the
manual Docker checks below. Nothing here is estimated.

| Check | Command | Result |
|-------|---------|--------|
| Ruff (`select = ["ALL"]`) | `pixi run lint-backend` | All checks passed |
| ESLint (flat config, type-aware strict + a11y) | `pixi run lint-frontend` | 0 problems |
| Formatting | `pixi run format-check` | Ruff format and Prettier clean |
| mypy (`strict`) | `pixi run typecheck-backend` | Success: no issues found in 35 source files |
| TypeScript (`strict`, `noUncheckedIndexedAccess`) | `pixi run typecheck-frontend` | 0 errors |
| Backend tests (unit + seed/report + API + authorization + meetings + concurrency + real-time) | `pixi run test-backend` | **204 passed**, 0 failed, ~49 s; coverage 93% (rules.py 99%, seed.py 99%, services/meetings.py 95%, auth.py 98%) |
| Playwright e2e (Chromium, two browser contexts) | `pixi run test-e2e` | **6 passed**, 37 s |
| Production build | `pixi run build` | Next.js build compiled successfully |

Backend breakdown: `test_rules.py` 88 · `test_api_authz.py` 34 · `test_api_team.py` 27 · `test_api_meetings.py` 20 · `test_meeting_summary_race.py` 9 ·
`test_seed_report.py` 17 · `test_concurrency_realtime.py` 9 (4 concurrency + 5 real-time).
Concurrency + real-time suite (`-m "concurrency or realtime"`, 18 tests) was run 10 times in a row: 10/10 passed, no flakes.

Playwright: `meeting-sync.spec.ts` (full two-browser meeting; observer/outsider) · `team-page.spec.ts` (journey; read-only
and switcher; admin & redirect; axe accessibility).

## Docker verification (manual)

* `docker compose down -v && docker compose up -d --wait`: db healthy → `init` exited 0 (migrations + seed) → backend
  healthy → frontend healthy; `http://localhost:3000/login` returned 200 and `http://localhost:8000/docs` 200.
* Second run of the seed (`docker compose run --rm -T backend python -m app.cli seed`) inserted 0 rows in every table.
* `docker compose run --rm -T backend python -m app.cli rules-report` is byte-identical to the committed
  `rules_report.json`; with `-e APP_NOW=2026-11-18T15:00:00Z` the window moves to end at 2026-11-16 and the overdue list
  becomes `[t12, t30, t31, t32]`.
* After the last code change, `docker compose up --build -d --wait` rebuilt both images and the stack came up healthy.

## Latest remediation pass (meeting-summary race, Conclude-only ratings, Pixi format tasks)

* `pixi run format`, `format-check`, `lint`, `typecheck`, `test`, `build` and `check` all exit 0 locally.
* New race tests fail against the previous code (6/6 interleaving cases) and pass with the `FOR SHARE`/`FOR UPDATE` fix.
* Fresh `docker compose down -v && up --build -d --wait`: all services healthy; regenerated rules report is
  byte-identical to the committed `rules_report.json`.
* Previous CI run (before this pass) passed both jobs:
  (run 44726403469 in the private development repository; see this repository's Actions tab for public runs)
* CI for remediation commit `c3cc4b8`: **passed** (both jobs: "Lint, types, tests, build" and "docker compose up smoke test"):
  (run 44728925286 in the private development repository; see this repository's Actions tab for public runs)

## Demo validation in CI and stack lifecycle (verified locally)

* New CI step **"Validate automated assessment demo"** runs `pixi run demo-validate` after `pixi run test` in the
  `verify` job (sequential, so nothing else uses the `l10_e2e` database). Headless, no OBS/display; the six-minute
  presentation mode is not run. Locally: all nine scenes PASS (two independent browser contexts, live sync,
  reconnection, ratings and summary), total about 5 s of scenes, exit code 0.
* Database safety is unchanged: `/api/__test__/reset` exists only with `ENABLE_TEST_ENDPOINTS=true` and
  `assert_safe_database` refuses any database name not ending in `_test` or `_e2e`.
* `demo/stack.mjs` readiness now has a deadline (`DEMO_STACK_TIMEOUT_SECONDS`, default 180). Verified with a real
  run at 4 s: backend READY, frontend NOT READY (`ECONNREFUSED`), children killed, exit 1, ports 8100/3100 freed.
* `pixi run test-stack` (`node --test demo/stack-lib.test.mjs`, 8 tests, part of `pixi run test`): both ready,
  backend/frontend/both timeout, backend/frontend crash during startup, Ctrl+C, repeated signals, nonzero exit.
* Also passing locally: format-check, lint, typecheck, `pixi run test` (204 backend tests, 6 Playwright tests,
  8 stack tests), build, `docker compose up --build -d --wait`.

## Not verified

* Non-Chromium browsers.
* The demo video was not recorded (out of scope for this pass).
