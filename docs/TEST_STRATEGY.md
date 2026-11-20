# Test strategy

## One command

```bash
pixi run test        # starts PostgreSQL (docker), runs pytest (+coverage), then the Playwright suite
```

It prepares everything itself: `db-up` (health-checked PostgreSQL container with the `l10_test` and `l10_e2e`
databases), schema via the real Alembic migration, seed via the real seed loader, browsers via
`install-browsers`. No manual data setup. Individual suites:

| Command | Scope |
|---------|-------|
| `pixi run test-rules` | pure rule tests + seed + rules report |
| `pixi run test-api` | API/authorization/meeting tests against PostgreSQL |
| `pixi run test-concurrency` | real concurrent HTTP requests and SSE real-time tests (`-m 'concurrency or realtime'`) |
| `pixi run test-e2e` | Playwright (two browser contexts) against a real stack |
| `pixi run test-backend` | everything in pytest, with coverage |

## Layers

| Layer | Files | What it proves |
|-------|-------|----------------|
| Rule unit tests | `backend/tests/test_rules.py` | every rule in 2.6, boundaries, DST, quarters, rounding |
| Seed & report | `test_seed_report.py` | counts/ids preserved, idempotent seed, report shape, independent oracle for trap cases, alternative `APP_NOW`, CLI stdout is only JSON |
| API & authorization | `test_api_authz.py`, `test_api_team.py`, `test_api_meetings.py` | real PostgreSQL, role/team boundaries, validation, DB constraints |
| Concurrency | `test_concurrency_realtime.py` | 12 threads × real HTTP × real DB: one Issue, one active meeting, no double advance |
| Lock coordination | `test_meeting_summary_race.py` | Two real DB sessions in threads; a hook pauses one transaction while it holds its lock, the test waits (bounded, polling `pg_stat_activity` for a lock wait) until the other is blocked, then releases. Covers both interleavings of meeting end vs. attributed To-Do / solve / Issue. No sleeps decide outcomes |
| Real time | same file (`realtime` marker) | SSE delivery < 1 s, join/rating/data events, reconnect snapshot, stream auth |
| End-to-end | `frontend/e2e/*.spec.ts` | two independent browser contexts; full journey; a11y (axe) |

## Fixtures and database isolation

* Tests only ever touch `l10_test` (pytest) or `l10_e2e` (Playwright). `app.testing.assert_safe_database` raises
  unless the database name ends in `_test`/`_e2e`; the test-only `POST /api/__test__/reset` endpoint is only mounted
  when `ENABLE_TEST_ENDPOINTS=true` **and** the database passes that check, so the development database cannot be
  wiped by the suite.
* The schema is rebuilt once per pytest session from the real migrations; **before every test** all tables are
  `TRUNCATE … RESTART IDENTITY` and the seed is reloaded (`conftest._fresh_seed`, Playwright `resetDb` auto-fixture).
  Tests are therefore order-independent.
* `login(user_id)` returns an independent `TestClient` (own cookie jar) per user. `live_server` runs a real uvicorn
  server (with the LISTEN/NOTIFY hub) on a free port for concurrency and SSE tests.

## Clock strategy

Two injected clocks (`app/clock.py`):

* **business clock** — frozen at the seed's `APP_NOW` = `2026-11-11T15:00:00Z` for every test (week/quarter/overdue/
  due-date logic and record timestamps are therefore deterministic);
* **timer clock** — a `FrozenClock` in pytest that tests advance explicitly (`clocks.timer.advance(...)`), so section
  timers and overtime are asserted without sleeping. In Playwright the real clock is used (the timer visibly ticks)
  and assertions compare two browsers' elapsed times within a tolerance.

Rule functions in `app/rules.py` take `now`/dates as arguments and never read a clock, so alternative dates are tested
by simply passing other instants (also through the report builder and the CLI with `APP_NOW=…`).

## Playwright

`frontend/playwright.config.ts` starts the backend (port 8100, DB `l10_e2e`) and a production Next.js build (port 3100,
built for that API URL) itself, `workers: 1`, role-based locators (`getByRole`, labels) with a few `data-testid`s for
live-updating regions. Synchronisation uses web-first assertions with timeouts (no sleeps). The disconnection test uses
`context.setOffline()` and verifies the browser catches up after going back online.

## Failure artifacts

Config: `trace: retain-on-failure`, `screenshot: only-on-failure`, `video: retain-on-failure`; output in
`frontend/test-results/`, HTML report in `frontend/playwright-report/`. Inspect with
`pnpm exec playwright show-trace <trace.zip>` (in `frontend/`) or `pnpm exec playwright show-report`.

A genuine failure artifact from development is committed at `docs/artifacts/` (see its README: it is the trace of
the real failure I hit when the browser went offline while the event stream stayed open — the bug that led to the
client's network-aware reconnect).

## Coverage

`pixi run test-backend` prints a coverage table and writes `coverage.xml`. Latest run: see `TEST_CASES.md`
(results section). Business rules, authorization, meeting transitions and report generation are ≥ 95%.
Coverage is a by-product, not a goal; the oracle tests assert behaviour.

## How each rule is verified

| Rule | Where |
|------|-------|
| Time / weeks / quarters / DST | `test_rules.py` (week/quarter/DST parametrized), `TC-RULE-01..04` |
| Measurable status | `test_rules.py::test_measurable_status_goal_types_and_inclusive_boundaries` + missing-score tests; API `test_scorecard_shape_and_statuses`; report oracle |
| To-Do completion | `test_t28…`, `test_t29…`, exact-90, 89.5%, DST, zero-due; API + report oracle |
| Overdue | `test_overdue_rules`; API flags; e2e |
| Rock status/progress | `test_rock_status`, `test_rock_progress`; API `test_rocks_current_quarter` |
| Issue order | `test_issue_order_*`; API `test_issue_order_matches_rule`; e2e |
| Meeting rating | `test_average_rating`, half-up rounding tests; API summary tests |
| No duplicate Issues | `test_concurrent_make_it_an_issue_creates_exactly_one_issue` and sequential API tests |

## Known gaps

* No visual-regression tests; accessibility is checked with axe on two pages and manual keyboard review.
* The e2e suite runs on Chromium only.
* The meeting UI's overtime styling is covered by the API timer test and manual review, not by a (slow) e2e wait.
