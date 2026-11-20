# Implementation plan

Dependency-ordered phases. Each phase was verified before the next began. Status reflects the final state of this
branch (`feature/l10-meetings-app`).

| # | Phase | Status |
|---|-------|--------|
| 1 | Analysis (requirements, seed traps) | Done |
| 2 | Environment (Pixi, pnpm, uv, linters, Docker) | Done |
| 3 | Database & backend | Done |
| 4 | Rules correctness & report | Done |
| 5 | Frontend (team page) | Done |
| 6 | Meetings (lifecycle, timer, real-time) | Done |
| 7 | Testing (unit, API, concurrency, real-time, e2e) | Done |
| 8 | Quality, CI & documentation | Done (video not recorded — see README) |

## Phase 1 — Analysis
- **Objective:** extract every requirement and seed trap. **Files:** `docs/REQUIREMENTS.md`.
- **Tasks:** unzip the DOCX and read paragraphs/tables/diagram text; read `seed.json` (timestamps near week
  boundaries, `m5` gap, `t28`/`t29`, `ms2`, `r2`, `r3`).
- **Requirements:** all. **Acceptance:** matrix covers every requirement. **Verify:** review.

## Phase 2 — Environment
- **Objective:** reproducible, pinned toolchain. **Files:** `pixi.toml`/`pixi.lock`, `backend/pyproject.toml`/`uv.lock`,
  `frontend/package.json`/`pnpm-lock.yaml`, `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`.
- **Tasks:** pin Python 3.13.18, Node 24.22.3, pnpm 12.22.0, uv 0.13.9 via Pixi; exact versions (`==`, no `^`/`~`) for
  all direct dependencies; Ruff `select = ["ALL"]`, mypy strict; ESLint flat config (type-aware strict + a11y), Prettier;
  Docker images pinned by digest.
- **Acceptance:** `uv sync --frozen`, `pnpm install --frozen-lockfile` succeed. **Verify:** `pixi run install`.

## Phase 3 — Database & backend
- **Objective:** normalized schema with DB-enforced integrity; REST API. **Files:** `backend/migrations/`,
  `backend/app/{models,seed,auth,schemas,routes,services}`.
- **Tasks:** migration with CHECK/FK/partial-unique/trigger constraints; idempotent seed preserving ids; clock
  abstraction; cookie auth + server-side authorization; Team page endpoints; meeting endpoints.
- **Requirements:** R-DATA-*, R-SEC-*, R-TEAM-*, R-MTG-*. **Verify:** `pixi run test-api`.

## Phase 4 — Rules correctness
- **Objective:** exact business rules + report. **Files:** `app/rules.py`, `app/summary.py`, `app/services/report.py`,
  `app/cli.py`, `rules_report.json`.
- **Acceptance:** all rule tests and report oracle tests pass; report valid at alternative `APP_NOW`.
  **Verify:** `pixi run test-rules`, `pixi run rules-report`.

## Phase 5 — Frontend
- **Objective:** responsive, accessible Team page. **Files:** `frontend/src/{app,components,features,lib}`.
- **Tasks:** generated typed API client (OpenAPI → `schema.d.ts`), TanStack Query hooks, Scorecard, Issues, To-Dos,
  Rocks, user/team switchers, toasts, dialogs. **Verify:** `pixi run lint typecheck build`, e2e team-page spec.

## Phase 6 — Meetings
- **Objective:** synchronized Level 10 meeting. **Files:** `app/services/meetings.py`, `app/realtime.py`,
  `app/routes/meetings.py`, `features/meeting/*`.
- **Tasks:** row-locked transitions with monotonic `version`; SSE + LISTEN/NOTIFY; client timer from server elapsed;
  offline/online reconnect; ratings; persisted summary snapshot.
- **Verify:** `pixi run test-concurrency`, e2e meeting-sync spec.

## Phase 7 — Testing
- Unit (88), API (≈100), concurrency/real-time (9), Playwright (6). **Verify:** `pixi run test`.

## Phase 8 — Quality, CI, docs
- `pixi run check`; `.github/workflows/ci.yml`; README, ARCHITECTURE, DECISIONS, TEST_*, DEMO_SCRIPT.
