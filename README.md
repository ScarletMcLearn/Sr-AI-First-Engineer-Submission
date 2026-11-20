# Level 10 meetings — Senior AI-First Software Engineer assessment

A weekly leadership-team product (EOS "Level 10"): **Scorecard** (Measurables), **Rocks**, **To-Dos**, **Issues** and a
live, multi-browser **Level 10 Meeting** (Scorecard 5 min → IDS 60 min → Conclude 10 min, server-owned timer, ratings,
persisted summaries). The brief is `assessment-brief.docx` (the starter text calls it a PDF).

* **Stack:** Next.js 16 + TypeScript + React 19 + Tailwind 4 + shadcn/ui-style components + TanStack Query ·
  FastAPI + Pydantic + SQLAlchemy · PostgreSQL 17 + Alembic · Docker Compose · Pixi/pnpm/uv.
* **Architecture in one paragraph:** the REST API is the only write path; PostgreSQL owns all state and integrity
  (CHECK/FK/partial-unique/trigger constraints). Meeting changes are pushed to browsers over **Server-Sent Events**; each
  backend worker `LISTEN`s to Postgres `NOTIFY`, so workers stay consistent. Business rules are pure functions
  (`backend/app/rules.py`) driven by an injected clock (`APP_NOW`). Details: `docs/ARCHITECTURE.md`, decisions and trade-offs:
  `docs/DECISIONS.md`.

## Assessment Demonstration

Watch the complete application demonstration:

[▶ Watch Demo Video](Demo.mp4)

## Run it

Prerequisite: **Docker** (Compose v2). Nothing else is needed to run the app.

```bash
docker compose up --build          # db → migrations → idempotent seed → API → web
```

| URL | What |
|-----|------|
| http://localhost:3000 | web app (pick a seeded user on `/login`) |
| http://localhost:8000/docs | OpenAPI / Swagger UI (`/openapi.json`) |
| http://localhost:8000/api/health | health check |

Seed users: `u1` Avery Admin · `u2` Blake, `u3` Casey, `u4` Dana, `u6` Finley, `u8` Harper, `u9` Indy (Team Members) ·
`u5` Ellis, `u7` Gray (Observers). `APP_NOW` (default `2026-11-11T15:00:00Z`) can be overridden:
`APP_NOW=2026-11-18T15:00:00Z docker compose up`. The seed never resets existing data; `docker compose down -v` does.

## Rules report

```bash
docker compose run --rm -T backend python -m app.cli rules-report > rules_report.json
# or, with the Pixi environment:  pixi run rules-report
```
Prints only JSON to stdout (logs go to stderr), computed from the database and `APP_NOW`; works at any date
(`docker compose run --rm -T -e APP_NOW=2026-11-18T15:00:00Z backend python -m app.cli rules-report`). The committed `rules_report.json` was generated on a
freshly seeded Docker database.

## Tests and quality (Pixi-managed, pinned toolchain)

```bash
pixi install --locked        # Python 3.13.18, Node 24.22.3, pnpm 12.22.0, uv 0.13.9 (exact, from pixi.lock)
pixi run install             # uv sync --frozen, pnpm install --frozen-lockfile, Playwright Chromium
pixi run test                # ONE unattended command: starts Postgres, pytest (+coverage), Playwright (two browsers)
pixi run check               # lint + format-check + typecheck + test + build
```
Also: `pixi run lint | format-check | typecheck | build | test-rules | test-api | test-concurrency | test-e2e`.
Tests use isolated databases (`l10_test`, `l10_e2e`), a frozen business clock, and reseed before every test — see
`docs/TEST_STRATEGY.md`. Test inventory: `docs/TEST_CASES.md`; traceability: `docs/REQUIREMENTS.md`,
`docs/REQUIREMENT_TEST_MATRIX.md`; latest results: `docs/TEST_RESULTS.md`. A real Playwright failure trace is in
`docs/artifacts/`. CI: `.github/workflows/ci.yml` (same Pixi tasks + a `docker compose up` smoke job).

## Assumptions and decisions on ambiguities

* Admins may own items in any team; Team Members only in their own teams; Observers never (DB trigger + API).
* Ratings: only in the Conclude section (enforced by the API: 409 earlier); attending Admins/Team Members, changeable until the meeting ends.
* `rules_report.rocks` lists all of a team's Rocks; the Team page shows the current quarter's.
* Business time is the **frozen** `APP_NOW` (deterministic); meeting timers use real UTC time because elapsed time can't be
  measured by a frozen clock (`docs/ARCHITECTURE.md`). Records created via the UI therefore carry the `APP_NOW` instant.
* Make it an Issue is allowed only for off-track cells (422 otherwise). Past meeting statuses are evaluated as of the
  meeting's start and stored as a snapshot.

## Known limitations

* Login has no passwords (assessment shortcut); anyone can pick any seeded user.
* Not implemented bonuses: Make it an Issue from a Rock / overdue To-Do, full audit trail (only a meeting event log);
  implemented: lost-update protection for scores and Issue priority (`expected_version`), 1,000-company note in `DECISIONS.md`.
* No meeting-history page (out of scope); no manual facilitator handoff (not required).
* E2E runs on Chromium only; accessibility checked with axe on two pages plus manual keyboard review.
* Verified on Windows 11 (Docker Desktop). GitHub Actions results for the latest push are recorded in `docs/TEST_RESULTS.md`.

## AI tools used

Claude Code (Claude Sonnet 5.5) was used to generate the boiler plate code.

